"""
Pipeline Service - Model Loading & Generation Logic
"""
import torch
import os
import gc
import time
import asyncio
import json
from pathlib import Path
from typing import Optional, Callable, Awaitable, Dict
from diffusers import (
    StableDiffusionPipeline,
    StableDiffusionImg2ImgPipeline,
    EulerAncestralDiscreteScheduler
)
from huggingface_hub import snapshot_download, HfApi
from src.utils.logger import create_logger
from src.core.exceptions import ModelDownloadError, AuthenticationError, DiskSpaceError
from src.core.memory_manager import memory_manager, clear_cache
from src.core.config import Config

logger = create_logger("PipelineService")


def load_model_configs() -> Dict:
    """
    Load model configurations from JSON file.
    Filters out disabled models (models with "disabled": true or keys starting with "_").
    
    Returns:
        Dict containing active model configurations
    
    Raises:
        FileNotFoundError: If models.json is not found
        json.JSONDecodeError: If JSON is invalid
    """
    config_path = Path(__file__).parent.parent.parent.parent / "static" / "config" / "models.json"
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Filter out disabled models
            all_models = data['models']
            active_models = {
                key: config 
                for key, config in all_models.items() 
                if not key.startswith('_') and not config.get('disabled', False)
            }
            
            disabled_count = len(all_models) - len(active_models)
            logger.info(f"Loaded {len(active_models)} active model configurations from {config_path}")
            if disabled_count > 0:
                logger.info(f"Skipped {disabled_count} disabled model(s)")
            
            return active_models
    except FileNotFoundError:
        logger.error(f"Model configuration file not found: {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in model configuration: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load model configurations: {e}")
        raise


# Load model configurations from JSON
MODEL_CONFIGS = load_model_configs()


class PipelineService:
    """Manages AI model pipelines"""
    
    def __init__(self):
        self.pipe = None
        self.img2img_pipe = None
        self.device = None
        self.forced_device = None  # User-forced device (None = auto)
        self.dtype = torch.float32
        self.current_model = None
        self.upscaler = None
        
        # VAE caching for faster multi-image generation
        self._vae_cache = None
        self._vae_cache_dtype = None
        
        # DRAM Extension Configuration
        self.dram_config = {
            "enabled": False,
            "vram_threshold_gb": 6,
            "max_dram_gb": 16
        }
        
        # Download state tracking for concurrent download prevention
        self._download_locks: Dict[str, asyncio.Lock] = {}
        self._download_states: Dict[str, str] = {}  # model_name -> 'downloading' | 'completed' | 'failed'
    
    def _detect_amd_gpu(self, gpu_name: str) -> bool:
        """
        Detect if GPU is AMD Radeon.
        
        Args:
            gpu_name: GPU name from torch.cuda.get_device_name()
        
        Returns:
            True if AMD GPU, False otherwise
        """
        gpu_name_upper = gpu_name.upper()
        is_amd = "AMD" in gpu_name_upper or "RADEON" in gpu_name_upper
        
        if is_amd:
            logger.info(f"AMD GPU detected: {gpu_name}")
        
        return is_amd
    
    def _detect_rdna_architecture(self, gpu_name: str) -> str:
        """
        Detect RDNA architecture generation.
        
        Args:
            gpu_name: GPU name string
        
        Returns:
            "RDNA1", "RDNA2", "RDNA3", "RDNA4", "RDNA_PRO", or "Unknown"
        """
        gpu_name_upper = gpu_name.upper()
        
        # Check for Radeon Pro first (professional GPUs)
        if "RADEON PRO" in gpu_name_upper:
            architecture = "RDNA_PRO"
        # Check for RDNA generations by RX series
        # Note: Must check for 4-digit series (RX 5700, 5600, 5500) to avoid matching older 3-digit series (RX 580, 570)
        elif "RX 9" in gpu_name_upper:
            architecture = "RDNA4"
        elif "RX 7" in gpu_name_upper:
            architecture = "RDNA3"
        elif "RX 6" in gpu_name_upper:
            architecture = "RDNA2"
        elif "RX 57" in gpu_name_upper or "RX 56" in gpu_name_upper or "RX 55" in gpu_name_upper:
            # RDNA1: RX 5700, 5600, 5500 series
            architecture = "RDNA1"
        else:
            architecture = "Unknown"
        
        logger.info(f"Detected AMD GPU architecture: {architecture}")
        return architecture
    
    def _select_amd_precision(self, architecture: str) -> torch.dtype:
        """
        Select appropriate precision for AMD GPU.
        
        Args:
            architecture: RDNA architecture string
        
        Returns:
            torch.float16 for RDNA1+, torch.float32 for older/unknown
        """
        # Check for ROCM_FORCE_FLOAT32 configuration override
        from src.core.config import Config
        if hasattr(Config, 'ROCM_FORCE_FLOAT32') and Config.ROCM_FORCE_FLOAT32:
            logger.info("ROCM_FORCE_FLOAT32 enabled, using float32")
            return torch.float32
        
        # RDNA1+ supports float16 for better performance
        if architecture in ["RDNA1", "RDNA2", "RDNA3", "RDNA4", "RDNA_PRO"]:
            if architecture in ["RDNA3", "RDNA4"]:
                logger.success(f"AMD {architecture} detected with Matrix Cores! Using float16")
            else:
                logger.success(f"AMD {architecture} detected! Using float16")
            return torch.float16
        else:
            logger.info(f"AMD GPU architecture {architecture}: Using float32 for compatibility")
            return torch.float32
    
    def detect_device(self, force_device: str = None):
        """Detect and configure the best available device"""
        # If user forced a specific device
        if force_device:
            self.forced_device = force_device
            if force_device == "cpu":
                self.device = "cpu"
                self.dtype = torch.float32
                logger.info("Forced CPU mode by user")
                return self.device
            elif force_device == "cuda" and torch.cuda.is_available():
                self.forced_device = "cuda"
                # Continue with CUDA detection below
            elif force_device == "mps" and torch.backends.mps.is_available():
                self.device = "mps"
                self.dtype = torch.float32
                logger.success("Forced Apple Silicon mode")
                return self.device
            elif force_device == "xpu" and hasattr(torch, 'xpu') and torch.xpu.is_available():
                self.device = "xpu"
                self.dtype = torch.float32
                logger.success("Forced Intel Arc mode")
                return self.device
            elif force_device == "privateuseone":
                # DirectML device
                self.device = "privateuseone"
                self.dtype = torch.float32
                logger.success("Forced DirectML mode")
                return self.device
        
        # Check for DirectML (AMD/Intel GPUs on Windows)
        try:
            import torch_directml
            if torch_directml.is_available():
                self.device = torch_directml.device()
                
                # Try to get GPU name from Windows
                try:
                    import subprocess
                    result = subprocess.run(
                        ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    gpu_lines = [line.strip() for line in result.stdout.split('\n') if line.strip() and line.strip() != 'Name']
                    if gpu_lines:
                        gpu_name = gpu_lines[0]
                        is_amd = self._detect_amd_gpu(gpu_name)
                        vendor = "AMD" if is_amd else "Intel/Other"
                        logger.success(f"{vendor} GPU detected via DirectML: {gpu_name}")
                        
                        # Detect AMD architecture for optimization hints
                        if is_amd:
                            architecture = self._detect_rdna_architecture(gpu_name)
                            logger.info(f"AMD Architecture: {architecture}")
                            # RDNA3/RDNA4 support float16
                            self.dtype = self._select_amd_precision(architecture)
                        else:
                            self.dtype = torch.float32
                    else:
                        logger.success("DirectML GPU detected")
                        self.dtype = torch.float32
                except Exception as e:
                    logger.success("DirectML GPU detected")
                    self.dtype = torch.float32
                    logger.debug(f"Could not get GPU name: {e}")
                
                return self.device
        except ImportError:
            pass  # DirectML not installed
        
        # CUDA covers both NVIDIA and AMD ROCm
        if torch.cuda.is_available() and self.forced_device != "cpu":
            self.device = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            
            # Detect GPU vendor using new AMD detection method
            is_amd = self._detect_amd_gpu(gpu_name)
            vendor = "AMD" if is_amd else "NVIDIA"
            
            logger.success(f"{vendor} GPU detected: {gpu_name}")
            
            vram_total_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"VRAM: {vram_total_gb:.1f}GB")
            
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
            
            if vram_total_gb <= self.dram_config["vram_threshold_gb"]:
                logger.info(f"Auto-enabling DRAM Extension for {vram_total_gb:.1f}GB VRAM card")
                self.dram_config["enabled"] = True
            
            # AMD GPU: Use new architecture detection and precision selection
            if is_amd:
                architecture = self._detect_rdna_architecture(gpu_name)
                self.dtype = self._select_amd_precision(architecture)
            # NVIDIA GPU: Check for tensor cores
            else:
                has_tensor_cores = any(arch in gpu_name.upper() for arch in ["RTX", "A100", "V100", "T4", "A10", "A40"])
                if has_tensor_cores:
                    logger.success("Tensor Cores detected! Using float16")
                    self.dtype = torch.float16
                else:
                    logger.warning("No Tensor Cores detected. Using float32")
                    self.dtype = torch.float32
                
        elif torch.backends.mps.is_available():
            self.device = "mps"
            self.dtype = torch.float32  # MPS works best with float32
            logger.success("Apple Silicon detected (Metal Performance Shaders)")
            
        elif hasattr(torch, 'xpu') and torch.xpu.is_available():
            self.device = "xpu"
            self.dtype = torch.float32
            try:
                xpu_name = torch.xpu.get_device_name(0)
                logger.success(f"Intel Arc GPU detected: {xpu_name}")
            except:
                logger.success("Intel Arc GPU detected")
            
        else:
            self.device = "cpu"
            self.dtype = torch.float32
            logger.info("Running in CPU mode")
        
        return self.device
    
    async def switch_device(self, target_device: str):
        """Switch between GPU and CPU mode"""
        valid_devices = ["cuda", "cpu", "mps", "xpu", "auto"]
        if target_device not in valid_devices:
            raise ValueError(f"Invalid device: {target_device}. Valid: {valid_devices}")
        
        # Check if target device is available
        if target_device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA/ROCm is not available on this system")
        if target_device == "mps" and not torch.backends.mps.is_available():
            raise ValueError("MPS (Apple Silicon) is not available on this system")
        if target_device == "xpu":
            if not (hasattr(torch, 'xpu') and torch.xpu.is_available()):
                raise ValueError("Intel XPU is not available. Install intel-extension-for-pytorch")
        
        old_device = self.device
        old_model = self.current_model
        
        logger.info(f"Switching device from {old_device} to {target_device}...")
        
        # Cleanup current pipeline
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
        if self.img2img_pipe is not None:
            del self.img2img_pipe
            self.img2img_pipe = None
        
        # Use centralized memory cleanup
        clear_cache("all", synchronize=True)
        
        # Re-detect device with forced setting
        if target_device == "auto":
            self.forced_device = None
            self.detect_device()
        else:
            self.detect_device(force_device=target_device)
        
        # Reload model if one was loaded
        if old_model:
            await self.load_model(old_model)
        
        logger.success(f"Device switched to {self.device}")
        return {
            "success": True,
            "old_device": old_device,
            "new_device": self.device,
            "model_reloaded": old_model is not None
        }
    
    def get_model_cache_path(self, model_id: str):
        """
        Get the expected cache path for a HuggingFace model.
        Checks both HUGGINGFACE_MODELS_PATH and HF_HOME locations.
        Returns the actual model directory (including snapshot path if needed).
        
        Args:
            model_id: HuggingFace model ID (e.g., "Ojimi/anime-kawai-diffusion")
        
        Returns:
            Path object pointing to the actual model directory with model files
        """
        from pathlib import Path
        from src.core.config import Config
        
        # HuggingFace uses format: hub/models--{org}--{model}
        # Replace "/" with "--" to match HuggingFace cache conventions
        safe_model_id = model_id.replace("/", "--")
        model_dir_name = f"models--{safe_model_id}"
        
        def get_actual_model_path(base_path: Path) -> Path:
            """Get the actual model path, checking for snapshots subdirectory"""
            # Check if snapshots directory exists (HF cache structure)
            snapshots_dir = base_path / "snapshots"
            if snapshots_dir.exists():
                # Get the latest snapshot (most recently modified)
                try:
                    snapshots = sorted(
                        snapshots_dir.iterdir(), 
                        key=lambda p: p.stat().st_mtime, 
                        reverse=True
                    )
                    if snapshots:
                        latest_snapshot = snapshots[0]
                        # Log relative path
                        try:
                            rel_path = latest_snapshot.relative_to(Config.BASE_DIR)
                            logger.debug(f"Using snapshot path: {rel_path}")
                        except ValueError:
                            logger.debug(f"Using snapshot path: {latest_snapshot}")
                        return latest_snapshot
                except (OSError, PermissionError) as e:
                    logger.warning(f"Could not access snapshots: {e}")
            
            # No snapshots, use base path
            return base_path
        
        def log_relative_path(path: Path, description: str):
            """Log path relative to BASE_DIR for cross-platform compatibility"""
            try:
                rel_path = path.relative_to(Config.BASE_DIR)
                logger.debug(f"{description}: {rel_path}")
            except ValueError:
                # Path is outside BASE_DIR, log as-is
                logger.debug(f"{description}: {path}")
        
        # Priority 1: Check HUGGINGFACE_MODELS_PATH/hub (project-local models)
        huggingface_path = Path(Config.HUGGINGFACE_MODELS_PATH)
        project_model_path = huggingface_path / "hub" / model_dir_name
        if project_model_path.exists():
            actual_path = get_actual_model_path(project_model_path)
            log_relative_path(actual_path, "Found model at project path")
            return actual_path
        
        # Priority 2: Check HUGGINGFACE_MODELS_PATH directly (legacy)
        legacy_project_path = huggingface_path / model_dir_name
        if legacy_project_path.exists():
            actual_path = get_actual_model_path(legacy_project_path)
            log_relative_path(actual_path, "Found model at legacy project path")
            return actual_path
        
        # Priority 3: Fall back to HF_HOME cache (global HuggingFace cache)
        cache_dir = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        hf_cache_path = Path(cache_dir) / "hub" / model_dir_name
        
        # Even for HF_HOME, check if it exists and return actual path
        if hf_cache_path.exists():
            actual_path = get_actual_model_path(hf_cache_path)
            log_relative_path(actual_path, "Found model at HF_HOME path")
            return actual_path
        
        # Model doesn't exist anywhere, return expected HF_HOME path
        logger.debug(f"Model not found, returning expected HF_HOME path: {hf_cache_path}")
        return hf_cache_path
    
    def verify_model_files(self, model_path):
        """
        Verify that essential model files exist in the cache directory.
        Supports two directory structures:
        1. Standard HF structure: models--org--name/snapshots/hash/files
        2. Direct structure: models--org--name/files (used by some models like FLUX)
        
        Args:
            model_path: Path object pointing to the model cache directory
        
        Returns:
            bool: True if required files exist, False otherwise
        """
        from pathlib import Path
        
        # List of files that indicate a valid model
        required_files = [
            "model_index.json",  # Standard SD models
            "config.json",  # Some models
            "flux1-schnell.safetensors",  # FLUX specific
            "model.safetensors.index.json",  # Large models with sharded weights
        ]
        
        # Check for snapshots directory (standard HF structure)
        snapshots_dir = model_path / "snapshots"
        if snapshots_dir.exists():
            # Get the latest snapshot (most recent directory)
            try:
                snapshots = sorted(
                    snapshots_dir.iterdir(), 
                    key=lambda p: p.stat().st_mtime, 
                    reverse=True
                )
            except (OSError, PermissionError):
                return False
            
            if not snapshots:
                return False
            
            latest_snapshot = snapshots[0]
            
            # Check if any required file exists in snapshot
            has_required_file = any((latest_snapshot / f).exists() for f in required_files)
            
            # Also check for safetensors files (model weights)
            if not has_required_file:
                safetensors_files = list(latest_snapshot.glob("*.safetensors"))
                if safetensors_files:
                    logger.debug(f"Found {len(safetensors_files)} safetensors files in {latest_snapshot}")
                    return True
            
            return has_required_file
        
        # Check for direct structure (files directly in model directory)
        # This is used by some models like FLUX
        else:
            logger.debug(f"No snapshots directory found, checking direct structure in {model_path}")
            
            # Check if any required file exists directly in model_path
            has_required_file = any((model_path / f).exists() for f in required_files)
            
            if has_required_file:
                logger.debug(f"Found required files in direct structure at {model_path}")
                return True
            
            # Also check for safetensors files
            safetensors_files = list(model_path.glob("*.safetensors"))
            if safetensors_files:
                logger.debug(f"Found {len(safetensors_files)} safetensors files in direct structure at {model_path}")
                return True
            
            logger.debug(f"No valid model files found in {model_path}")
            return False
    
    def is_model_downloaded(self, model_name: str) -> bool:
        """
        Check if a model is downloaded locally.
        
        Args:
            model_name: Key from MODEL_CONFIGS (e.g., "anime_kawai", "animagine_xl_4")
        
        Returns:
            bool: True if model exists locally and has required files, False otherwise
        
        Raises:
            ValueError: If model_name is not found in MODEL_CONFIGS
        """
        # Validate model name
        if model_name not in MODEL_CONFIGS:
            raise ValueError(f"Unknown model: {model_name}. Available models: {list(MODEL_CONFIGS.keys())}")
        
        # Get the HuggingFace model ID from config
        model_id = MODEL_CONFIGS[model_name]["id"]
        
        # Get the expected cache path for this model
        model_cache_path = self.get_model_cache_path(model_id)
        
        # Check if the cache directory exists
        if not model_cache_path.exists():
            logger.debug(f"Model {model_name} not found: cache directory does not exist at {model_cache_path}")
            return False
        
        # Verify that required model files exist
        if not self.verify_model_files(model_cache_path):
            logger.debug(f"Model {model_name} incomplete: required files missing in {model_cache_path}")
            return False
        
        logger.debug(f"Model {model_name} is downloaded and verified at {model_cache_path}")
        return True
    
    def _check_disk_space(self, model_name: str):
        """
        Check if sufficient disk space is available for model download.
        
        Args:
            model_name: Key from MODEL_CONFIGS (e.g., "anime_kawai", "animagine_xl_4")
        
        Raises:
            DiskSpaceError: If insufficient disk space is available
            ValueError: If model_name is not found in MODEL_CONFIGS
        """
        import shutil
        
        # Validate model name
        if model_name not in MODEL_CONFIGS:
            raise ValueError(f"Unknown model: {model_name}. Available models: {list(MODEL_CONFIGS.keys())}")
        
        # Get the HuggingFace model ID from config
        model_id = MODEL_CONFIGS[model_name]["id"]
        
        # Estimate required space based on model type
        # FLUX models: ~24GB
        if "flux" in model_id.lower():
            required_gb = 24.0
        # SDXL models: ~12GB
        elif any(kw in model_id.lower() for kw in ["xl", "sdxl", "pony", "stable-diffusion-3"]):
            required_gb = 12.0
        # SD 1.5 models: ~5GB
        else:
            required_gb = 5.0
        
        # Add 2GB buffer for safety
        required_with_buffer_gb = required_gb + 2.0
        
        # Get HuggingFace cache directory
        cache_dir = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        
        # Check available disk space
        try:
            disk_usage = shutil.disk_usage(cache_dir)
            available_gb = disk_usage.free / (1024 ** 3)  # Convert bytes to GB
            
            logger.debug(f"Disk space check for {model_name}: Required={required_with_buffer_gb:.1f}GB, Available={available_gb:.1f}GB")
            
            # Raise error if insufficient space
            if available_gb < required_with_buffer_gb:
                logger.error(f"Insufficient disk space for {model_name}: need {required_with_buffer_gb:.1f}GB, only {available_gb:.1f}GB available")
                raise DiskSpaceError(required_with_buffer_gb, available_gb)
            
            logger.info(f"Disk space check passed for {model_name}: {available_gb:.1f}GB available")
            
        except OSError as e:
            logger.error(f"Failed to check disk space: {e}")
            # Don't block download if we can't check disk space
            logger.warning("Proceeding with download despite disk space check failure")
    
    async def download_model_with_progress(
        self,
        model_name: str,
        progress_callback: Optional[Callable[[dict], Awaitable[None]]] = None
    ) -> bool:
        """
        Download a model from HuggingFace Hub with progress tracking.
        Prevents concurrent downloads of the same model using locks.
        
        Args:
            model_name: Key from MODEL_CONFIGS (e.g., "anime_kawai", "animagine_xl_4")
            progress_callback: Async function to call with progress updates
        
        Returns:
            True if download successful
        
        Raises:
            ModelDownloadError: If download fails
            AuthenticationError: If gated model requires token
            DiskSpaceError: If insufficient disk space
            ValueError: If model_name is not found in MODEL_CONFIGS
        """
        # Validate model name
        if model_name not in MODEL_CONFIGS:
            raise ValueError(f"Unknown model: {model_name}. Available models: {list(MODEL_CONFIGS.keys())}")
        
        # Get or create a lock for this model
        if model_name not in self._download_locks:
            self._download_locks[model_name] = asyncio.Lock()
        
        lock = self._download_locks[model_name]
        
        # Check if download is already in progress
        if lock.locked():
            logger.info(f"Download for {model_name} already in progress, waiting for completion...")
            if progress_callback:
                await progress_callback({
                    'type': 'download_waiting',
                    'model_name': model_name,
                    'message': f'Another download of {model_name} is in progress, waiting...'
                })
            
            # Wait for the existing download to complete
            async with lock:
                # Check the download state after acquiring lock
                if self._download_states.get(model_name) == 'completed':
                    logger.info(f"Model {model_name} download completed by another request")
                    if progress_callback:
                        await progress_callback({
                            'type': 'download_complete',
                            'model_name': model_name,
                            'message': f'Model {model_name} is now available'
                        })
                    return True
                elif self._download_states.get(model_name) == 'failed':
                    logger.warning(f"Previous download of {model_name} failed, retrying...")
                    # Fall through to retry the download
                else:
                    # State is unclear, proceed with download
                    pass
        
        # Acquire lock for this download
        async with lock:
            # Mark download as in progress
            self._download_states[model_name] = 'downloading'
            
            model_id = MODEL_CONFIGS[model_name]["id"]
            logger.info(f"Starting download for model: {model_id}")
            
            # Check disk space before download
            try:
                self._check_disk_space(model_name)
            except DiskSpaceError:
                # Mark as failed and re-raise
                self._download_states[model_name] = 'failed'
                raise
            
            # Check for HF_TOKEN environment variable for gated models
            hf_token = os.getenv("HF_TOKEN")
            
            # Track download progress
            progress_state = {
                'total_files': 0,
                'completed_files': 0,
                'total_bytes': 0,
                'downloaded_bytes': 0,
                'start_time': time.time(),
                'last_update_time': 0
            }
            
            # Progress tracking class for tqdm integration
            class ProgressTracker:
                def __init__(self, callback, state, model_name):
                    self.callback = callback
                    self.state = state
                    self.model_name = model_name
                    self.current_file = ""
                
                def __call__(self, block_num=0, block_size=1, total_size=0):
                    """Called by download progress hooks"""
                    if total_size > 0:
                        downloaded = block_num * block_size
                        self.state['downloaded_bytes'] = downloaded
                        self.state['total_bytes'] = total_size
                        
                        # Throttle updates to once per second
                        current_time = time.time()
                        if current_time - self.state['last_update_time'] < 1.0:
                            return
                        
                        self.state['last_update_time'] = current_time
                        
                        # Calculate progress metrics
                        elapsed = current_time - self.state['start_time']
                        progress_percent = (downloaded / total_size * 100) if total_size > 0 else 0
                        speed_mbps = (downloaded / (1024**2)) / elapsed if elapsed > 0 else 0
                        
                        # Calculate ETA
                        eta_seconds = None
                        if speed_mbps > 0:
                            remaining_mb = (total_size - downloaded) / (1024**2)
                            eta_seconds = int(remaining_mb / speed_mbps)
                        
                        # Send progress update via callback
                        if self.callback:
                            progress_data = {
                                'type': 'download_progress',
                                'model_name': self.model_name,
                                'progress_percent': round(progress_percent, 1),
                                'current_file': self.current_file or "Downloading...",
                                'downloaded_mb': round(downloaded / (1024**2), 1),
                                'total_mb': round(total_size / (1024**2), 1),
                                'speed_mbps': round(speed_mbps, 1),
                                'eta_seconds': eta_seconds
                            }
                            # Create task to send progress without blocking
                            asyncio.create_task(self.callback(progress_data))
            
            # Create progress tracker instance
            progress_tracker = ProgressTracker(progress_callback, progress_state, model_name)
            
            try:
                # Download model files using snapshot_download
                logger.info(f"Downloading model {model_id} from HuggingFace Hub...")
                
                # Check if model has a subfolder (e.g., Z-Anime uses diffusers/ subfolder)
                model_config = MODEL_CONFIGS[model_name]
                subfolder = model_config.get("subfolder", None)
                
                # For models with subfolders, only download that specific folder
                download_kwargs = {
                    "repo_id": model_id,
                    "token": hf_token,
                    "resume_download": True,
                    "local_files_only": False,
                    "cache_dir": Config.HF_HOME,  # Use local models folder
                }
                
                # If subfolder is specified, only download that folder
                if subfolder:
                    logger.info(f"Downloading only {subfolder}/ folder to save space...")
                    download_kwargs["allow_patterns"] = [f"{subfolder}/*"]
                
                # Use snapshot_download with resume support (run in thread to avoid blocking)
                cache_dir = await asyncio.to_thread(
                    snapshot_download,
                    **download_kwargs
                )
                
                # Mark download as completed
                self._download_states[model_name] = 'completed'
                
                logger.success(f"Model {model_name} downloaded successfully to {cache_dir}")
                
                # Send final progress update
                if progress_callback:
                    await progress_callback({
                        'type': 'download_progress',
                        'model_name': model_name,
                        'progress_percent': 100.0,
                        'current_file': 'Complete',
                        'downloaded_mb': progress_state.get('total_bytes', 0) / (1024**2),
                        'total_mb': progress_state.get('total_bytes', 0) / (1024**2),
                        'speed_mbps': 0.0,
                        'eta_seconds': 0
                    })
                
                return True
                
            except Exception as e:
                # Mark download as failed
                self._download_states[model_name] = 'failed'
                
                error_msg = str(e)
                logger.error(f"Failed to download model {model_name}: {error_msg}")
                
                # Check for authentication errors
                if "401" in error_msg or "authentication" in error_msg.lower() or "gated" in error_msg.lower():
                    logger.error(f"Model {model_name} requires HuggingFace authentication")
                    raise AuthenticationError(model_name)
                
                # Raise generic download error
                raise ModelDownloadError(model_name, error_msg)
    
    def get_available_devices(self):
        """Get list of available devices including NVIDIA, AMD, Intel, and Apple"""
        devices = [{"id": "cpu", "name": "CPU", "available": True, "type": "cpu"}]
        
        # NVIDIA CUDA or AMD ROCm (both use cuda backend)
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            
            # Detect if it's AMD (ROCm presents as CUDA)
            is_amd = "AMD" in gpu_name.upper() or "RADEON" in gpu_name.upper()
            
            devices.append({
                "id": "cuda",
                "name": f"{gpu_name} ({vram:.1f}GB)",
                "available": True,
                "type": "amd" if is_amd else "nvidia"
            })
        
        # Apple Silicon (MPS)
        if torch.backends.mps.is_available():
            devices.append({
                "id": "mps",
                "name": "Apple Silicon (Metal)",
                "available": True,
                "type": "apple"
            })
        
        # Intel Arc (XPU) - requires intel-extension-for-pytorch
        try:
            if hasattr(torch, 'xpu') and torch.xpu.is_available():
                xpu_name = "Intel Arc GPU"
                try:
                    xpu_name = torch.xpu.get_device_name(0)
                except:
                    pass
                devices.append({
                    "id": "xpu",
                    "name": xpu_name,
                    "available": True,
                    "type": "intel"
                })
        except Exception:
            pass
        
        return devices
    
    async def load_model(self, model_name: str = "anime_kawai", progress_callback: Optional[Callable[[dict], Awaitable[None]]] = None):
        """Load a specific model, downloading if necessary"""
        # Normalize model name (handle old format with underscores vs new format with hyphens)
        normalized_model_name = model_name
        if model_name not in MODEL_CONFIGS:
            # Try to find a matching model by replacing underscores with hyphens
            potential_match = model_name.replace('_', '-')
            if potential_match in MODEL_CONFIGS:
                logger.info(f"Model key normalized: {model_name} -> {potential_match}")
                normalized_model_name = potential_match
            else:
                # Try the reverse: replace hyphens with underscores in the middle part
                # e.g., "tensorart_stable-diffusion-3.5-medium-turbo" could be "tensorart_stable_diffusion_3_5_medium_turbo"
                # We need to be smarter about this
                for config_key in MODEL_CONFIGS.keys():
                    # Compare by normalizing both to lowercase and removing all separators
                    if config_key.replace('_', '').replace('-', '').lower() == model_name.replace('_', '').replace('-', '').lower():
                        logger.info(f"Model key normalized: {model_name} -> {config_key}")
                        normalized_model_name = config_key
                        break
        
        if normalized_model_name not in MODEL_CONFIGS:
            available_models = ', '.join(MODEL_CONFIGS.keys())
            raise ValueError(f"Unknown model: {model_name}. Available models: {available_models}")
        
        # Use normalized_model_name for everything from here on
        model_name = normalized_model_name
        model_id = MODEL_CONFIGS[model_name]["id"]
        logger.info(f"Loading model: {model_id}")
        
        # CRITICAL: Clear VRAM before loading new model
        if self.pipe is not None:
            logger.info("🧹 Clearing VRAM before loading new model...")
            # Move pipeline to CPU to free VRAM
            try:
                self.pipe = self.pipe.to("cpu")
            except:
                pass
            # Delete pipeline
            del self.pipe
            self.pipe = None
            # Also clear img2img pipeline if exists
            if self.img2img_pipe is not None:
                try:
                    self.img2img_pipe = self.img2img_pipe.to("cpu")
                except:
                    pass
                del self.img2img_pipe
                self.img2img_pipe = None
            # Force garbage collection
            gc.collect()
            # Clear DirectML/CUDA cache
            try:
                if hasattr(torch, 'cuda') and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.info("✅ CUDA cache cleared")
            except:
                pass
            try:
                if hasattr(torch, 'dml') and hasattr(torch.dml, 'empty_cache'):
                    torch.dml.empty_cache()
                    logger.info("✅ DirectML cache cleared")
            except:
                pass
            logger.info("✅ VRAM cleared successfully")
        
        # Check if model is downloaded
        if not self.is_model_downloaded(model_name):
            logger.info(f"Model {model_name} not found locally, downloading...")
            
            # Send initial download notification
            if progress_callback:
                await progress_callback({
                    'type': 'download_start',
                    'model_name': model_name,
                    'message': f'Downloading {model_name} from HuggingFace Hub...'
                })
            
            # Download with progress tracking
            try:
                await self.download_model_with_progress(model_name, progress_callback)
            except Exception as e:
                # Send download error notification
                if progress_callback:
                    await progress_callback({
                        'type': 'download_error',
                        'model_name': model_name,
                        'error': str(e)
                    })
                raise
            
            # Send completion notification
            if progress_callback:
                await progress_callback({
                    'type': 'download_complete',
                    'model_name': model_name,
                    'message': f'Download complete, loading model...'
                })
        
        try:
            # Check if this is a FLUX model (requires different pipeline)
            is_flux = "flux" in model_name.lower() or "FLUX" in model_id
            
            # Check if this is a SD 3.x model (requires StableDiffusion3Pipeline)
            is_sd3 = "stable-diffusion-3" in model_id.lower() or "stable_diffusion_3" in model_name.lower()
            
            # Check if this is Z-Anime (uses SD 3.x architecture with custom transformer)
            is_z_anime = "z-anime" in model_id.lower() or "z_anime" in model_name.lower()
            
            # Check if model is already downloaded
            model_already_downloaded = self.is_model_downloaded(model_name)
            
            if is_flux:
                # FLUX models use FluxPipeline
                from diffusers import FluxPipeline
                
                logger.info("Loading FLUX model with FluxPipeline...")
                logger.warning("⚠️ FLUX is a very large model (~24GB). Loading with aggressive memory optimizations...")
                
                # If model is downloaded in direct structure, use the local path
                if model_already_downloaded:
                    model_cache_path = self.get_model_cache_path(model_id)
                    
                    # Log relative path for cross-platform compatibility
                    try:
                        from pathlib import Path
                        from src.core.config import Config
                        rel_path = Path(model_cache_path).relative_to(Config.BASE_DIR)
                        logger.info(f"Loading FLUX from local path: {rel_path}")
                    except (ValueError, ImportError):
                        logger.info(f"Loading FLUX from local path: {model_cache_path}")
                    
                    self.pipe = FluxPipeline.from_pretrained(
                        str(model_cache_path),  # Use local path instead of model_id
                        torch_dtype=self.dtype,
                        local_files_only=True,
                        # CRITICAL: Memory optimizations for 16GB VRAM
                        low_cpu_mem_usage=True,  # Reduce CPU memory during loading
                        variant="fp16",  # Use FP16 variant if available
                    )
                else:
                    # Download from HuggingFace Hub
                    logger.info(f"Downloading FLUX from HuggingFace Hub: {model_id}")
                    self.pipe = FluxPipeline.from_pretrained(
                        model_id,
                        torch_dtype=self.dtype,
                        local_files_only=False,
                        # CRITICAL: Memory optimizations for 16GB VRAM
                        low_cpu_mem_usage=True,  # Reduce CPU memory during loading
                        variant="fp16",  # Use FP16 variant if available
                    )
                
                # Enable aggressive memory optimizations BEFORE moving to device
                logger.info("🔧 Enabling VAE slicing for FLUX...")
                self.pipe.enable_vae_slicing()
                
                logger.info("🔧 Enabling VAE tiling for FLUX...")
                self.pipe.enable_vae_tiling()
                
                # Enable model CPU offload to reduce VRAM usage
                logger.info("🔧 Enabling model CPU offload for FLUX (reduces VRAM to ~10GB)...")
                self.pipe.enable_model_cpu_offload()
                
                # DO NOT call .to(device) when using CPU offload - it handles device placement automatically
                logger.info("✅ FLUX loaded with memory optimizations (VAE slicing/tiling + CPU offload)")
                
                # Apply DirectML-specific optimizations
                device_str = str(self.device)
                if "privateuseone" in device_str or "dml" in device_str.lower():
                    self._apply_directml_optimizations(self.pipe)
                # Apply optimizations based on GPU vendor
                elif self.device == "cuda":
                    gpu_name = torch.cuda.get_device_name(0)
                    is_amd = self._detect_amd_gpu(gpu_name)
                    
                    if is_amd:
                        self._apply_rocm_optimizations(self.pipe)
                    else:
                        self._apply_cuda_optimizations(self.pipe)
                
                # FLUX doesn't have img2img pipeline yet
                self.img2img_pipe = None
                logger.info("Note: FLUX models don't support img2img yet")
                
            elif is_sd3 or is_z_anime:
                # SD 3.x models and Z-Anime - try different pipelines based on diffusers version
                try:
                    from diffusers import StableDiffusion3Pipeline
                    has_sd3_pipeline = True
                except ImportError:
                    has_sd3_pipeline = False
                    logger.warning("StableDiffusion3Pipeline not available in this diffusers version, using StableDiffusionPipeline")
                
                model_type = "Z-Anime" if is_z_anime else "SD 3.x"
                
                # Check if this is Z-Anime (needs special loading)
                is_zanime = "z-anime" in model_id.lower() or "z_anime" in model_name.lower()
                
                # For Z-Anime, we need to load from the diffusers/ subfolder directly
                if is_zanime:
                    from pathlib import Path
                    cache_dir = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
                    safe_model_id = model_id.replace("/", "--")
                    
                    # Try both possible cache locations
                    possible_paths = [
                        Path(cache_dir) / f"models--{safe_model_id}",
                        Path(cache_dir) / "hub" / f"models--{safe_model_id}",
                    ]
                    
                    model_cache_path = None
                    for path in possible_paths:
                        if path.exists():
                            model_cache_path = path
                            # Log relative path for cross-platform compatibility
                            try:
                                from src.core.config import Config
                                rel_path = path.relative_to(Config.BASE_DIR)
                                logger.info(f"Found model cache at: {rel_path}")
                            except (ValueError, ImportError):
                                logger.info(f"Found model cache at: {model_cache_path}")
                            break
                    
                    if not model_cache_path:
                        # Model not downloaded yet, use standard loading
                        load_kwargs = {
                            "torch_dtype": self.dtype,
                            "local_files_only": False,
                        }
                        model_id_to_load = model_id
                    else:
                        # Find the snapshot directory
                        snapshots_dir = model_cache_path / "snapshots"
                        if snapshots_dir.exists():
                            snapshots = sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                            if snapshots:
                                model_path = snapshots[0] / "diffusers"
                                if model_path.exists():
                                    # Log relative path for cross-platform compatibility
                                    try:
                                        from src.core.config import Config
                                        rel_path = model_path.relative_to(Config.BASE_DIR)
                                        logger.info(f"Loading Z-Anime from local path: {rel_path}")
                                    except (ValueError, ImportError):
                                        logger.info(f"Loading Z-Anime from local path: {model_path}")
                                    
                                    load_kwargs = {
                                        "torch_dtype": self.dtype,
                                        "local_files_only": True,
                                    }
                                    model_id_to_load = str(model_path)
                                else:
                                    load_kwargs = {"torch_dtype": self.dtype, "local_files_only": False}
                                    model_id_to_load = model_id
                            else:
                                load_kwargs = {"torch_dtype": self.dtype, "local_files_only": False}
                                model_id_to_load = model_id
                        else:
                            load_kwargs = {"torch_dtype": self.dtype, "local_files_only": False}
                            model_id_to_load = model_id
                else:
                    # Standard loading for SD 3.x models
                    load_kwargs = {
                        "torch_dtype": self.dtype,
                        "local_files_only": False,
                    }
                    # Only add variant if model supports it (not all SD 3.x models have fp16 variant)
                    # SD 3.5 Turbo uses standard weights without variant
                    model_id_to_load = model_id
                
                # Try with low_cpu_mem_usage first, fallback if it fails
                try:
                    # For Z-Anime, load with optional components
                    if is_zanime:
                        self.pipe = StableDiffusion3Pipeline.from_pretrained(
                            model_id_to_load,
                            low_cpu_mem_usage=True,
                            text_encoder_2=None,
                            text_encoder_3=None,
                            tokenizer_2=None,
                            tokenizer_3=None,
                            **load_kwargs
                        )
                    else:
                        self.pipe = StableDiffusion3Pipeline.from_pretrained(
                            model_id_to_load,
                            low_cpu_mem_usage=True,
                            **load_kwargs
                        )
                    logger.info("✅ Loaded with low_cpu_mem_usage=True")
                except (ValueError, RuntimeError) as e:
                    if "expected shape" in str(e) or "mismatched" in str(e).lower():
                        logger.warning("⚠️ Size mismatch detected, retrying with low_cpu_mem_usage=False and ignore_mismatched_sizes=True...")
                        if is_zanime:
                            self.pipe = StableDiffusion3Pipeline.from_pretrained(
                                model_id_to_load,
                                text_encoder_2=None,
                                text_encoder_3=None,
                                tokenizer_2=None,
                                tokenizer_3=None,
                                low_cpu_mem_usage=False,
                                ignore_mismatched_sizes=True,
                                **load_kwargs
                            )
                        else:
                            self.pipe = StableDiffusion3Pipeline.from_pretrained(
                                model_id_to_load,
                                low_cpu_mem_usage=False,
                                ignore_mismatched_sizes=True,
                                **load_kwargs
                            )
                        logger.info("✅ Loaded with ignore_mismatched_sizes=True")
                    else:
                        raise
                
                # Enable model CPU offload to reduce VRAM usage and RAM spikes
                logger.info("🔧 Enabling model CPU offload (keeps RAM low, uses VRAM efficiently)...")
                self.pipe.enable_model_cpu_offload()
                
                # Enable VAE optimizations
                logger.info("🔧 Enabling VAE slicing and tiling...")
                self.pipe.enable_vae_slicing()
                self.pipe.enable_vae_tiling()
                
                # DO NOT call .to(device) when using CPU offload - it handles device placement automatically
                logger.info("✅ Model loaded with CPU offload (RAM-friendly, VRAM-optimized)")
                
                # Apply DirectML-specific optimizations (only if not using CPU offload)
                # CPU offload handles device placement, so we skip manual optimizations
                
                # SD 3.x and Z-Anime don't have img2img pipeline yet
                self.img2img_pipe = None
                logger.info(f"Note: {model_type} models don't support img2img yet")
                
            else:
                # Check if this is an SDXL model
                model_config = MODEL_CONFIGS.get(model_name, {})
                model_type = model_config.get("model_type", "sd15")
                
                # Check if model has a subfolder
                subfolder = model_config.get("subfolder", None)
                
                # Determine if we should load from local path or HuggingFace Hub
                if model_already_downloaded:
                    model_cache_path = self.get_model_cache_path(model_id)
                    model_path_to_load = str(model_cache_path)
                    
                    # Log relative path for cross-platform compatibility
                    try:
                        from pathlib import Path
                        from src.core.config import Config
                        rel_path = Path(model_cache_path).relative_to(Config.BASE_DIR)
                        logger.info(f"Loading model from local path: {rel_path}")
                    except (ValueError, ImportError):
                        logger.info(f"Loading model from local path: {model_path_to_load}")
                    
                    load_kwargs = {
                        "torch_dtype": self.dtype,
                        "safety_checker": None,
                        "requires_safety_checker": False,
                        "local_files_only": True,
                    }
                else:
                    model_path_to_load = model_id
                    logger.info(f"Loading model from HuggingFace Hub: {model_path_to_load}")
                    
                    load_kwargs = {
                        "torch_dtype": self.dtype,
                        "safety_checker": None,
                        "requires_safety_checker": False,
                        "local_files_only": False,
                    }
                
                # Add subfolder if specified
                if subfolder:
                    load_kwargs["subfolder"] = subfolder
                    logger.info(f"Loading model from subfolder: {subfolder}")
                
                # Use the correct pipeline based on model type
                if model_type == "sdxl":
                    # SDXL models require StableDiffusionXLPipeline
                    from diffusers import StableDiffusionXLPipeline
                    
                    logger.info(f"Loading SDXL model with StableDiffusionXLPipeline...")
                    
                    self.pipe = StableDiffusionXLPipeline.from_pretrained(
                        model_path_to_load,
                        **load_kwargs
                    )
                    
                    self.pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
                        self.pipe.scheduler.config
                    )
                else:
                    # Standard SD 1.5 models
                    self.pipe = StableDiffusionPipeline.from_pretrained(
                        model_path_to_load,
                        **load_kwargs
                    )
                    
                    self.pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
                        self.pipe.scheduler.config
                    )
                
                self.pipe = self.pipe.to(self.device)
                
                # Apply DirectML-specific optimizations
                device_str = str(self.device)
                if "privateuseone" in device_str or "dml" in device_str.lower():
                    self._apply_directml_optimizations(self.pipe)
                # Apply optimizations based on GPU vendor
                elif self.device == "cuda":
                    gpu_name = torch.cuda.get_device_name(0)
                    is_amd = self._detect_amd_gpu(gpu_name)
                    
                    if is_amd:
                        self._apply_rocm_optimizations(self.pipe)
                    else:
                        self._apply_cuda_optimizations(self.pipe)
                
                # Create img2img pipeline
                self.img2img_pipe = StableDiffusionImg2ImgPipeline(
                    vae=self.pipe.vae,
                    text_encoder=self.pipe.text_encoder,
                    tokenizer=self.pipe.tokenizer,
                    unet=self.pipe.unet,
                    scheduler=self.pipe.scheduler,
                    safety_checker=None,
                    feature_extractor=None,
                    requires_safety_checker=False
                )
                
                if not self.dram_config["enabled"]:
                    self.img2img_pipe = self.img2img_pipe.to(self.device)
                
                # Apply DirectML-specific optimizations
                device_str = str(self.device)
                if "privateuseone" in device_str or "dml" in device_str.lower():
                    self._apply_directml_optimizations(self.img2img_pipe)
                # Apply optimizations based on GPU vendor
                elif self.device == "cuda":
                    gpu_name = torch.cuda.get_device_name(0)
                    is_amd = self._detect_amd_gpu(gpu_name)
                    
                    if is_amd:
                        self._apply_rocm_optimizations(self.img2img_pipe)
                    else:
                        self._apply_cuda_optimizations(self.img2img_pipe)
            
            self.current_model = model_name
            logger.success(f"Model loaded: {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def _apply_cuda_optimizations(self, pipeline):
        """Apply CUDA-specific optimizations"""
        pipeline.enable_attention_slicing(slice_size=1)
        
        # Use new VAE methods to avoid deprecation warnings
        if hasattr(pipeline, 'vae') and pipeline.vae is not None:
            if hasattr(pipeline.vae, 'enable_slicing'):
                pipeline.vae.enable_slicing()
            if hasattr(pipeline.vae, 'enable_tiling'):
                pipeline.vae.enable_tiling()
        
        if self.dram_config["enabled"]:
            self._apply_dram_extension(pipeline)
        
        if self.dtype == torch.float16 and hasattr(pipeline, 'vae'):
            pipeline.vae.to(torch.float32)
        
        # Use centralized cache clearing
        clear_cache("cuda", synchronize=False)
    
    def _apply_directml_optimizations(self, pipeline):
        """
        Apply DirectML-specific optimizations for AMD/Intel GPUs on Windows.
        
        DirectML doesn't support scaled_dot_product_attention, so we need to
        use a compatible attention processor.
        """
        logger.info("Applying DirectML optimizations...")
        
        try:
            # Import attention processors
            from diffusers.models.attention_processor import AttnProcessor
            
            # Set compatible attention processor for DirectML
            # DirectML doesn't support scaled_dot_product_attention
            if hasattr(pipeline, 'unet'):
                pipeline.unet.set_attn_processor(AttnProcessor())
                logger.info("✓ DirectML-compatible attention processor set")
            
            # Enable attention slicing for memory efficiency
            pipeline.enable_attention_slicing(slice_size=1)
            logger.info("✓ Attention slicing enabled")
            
            # Enable VAE optimizations
            if hasattr(pipeline, 'vae') and pipeline.vae is not None:
                if hasattr(pipeline.vae, 'enable_slicing'):
                    pipeline.vae.enable_slicing()
                    logger.info("✓ VAE slicing enabled")
                if hasattr(pipeline.vae, 'enable_tiling'):
                    pipeline.vae.enable_tiling()
                    logger.info("✓ VAE tiling enabled")
            
            logger.success("DirectML optimizations applied successfully")
            
        except Exception as e:
            logger.error(f"Failed to apply DirectML optimizations: {e}")
            # Continue anyway - the model might still work
    
    def _apply_rocm_optimizations(self, pipeline):
        """
        Apply ROCm-specific optimizations for AMD GPUs.
        
        Enables:
        - Attention slicing for memory efficiency
        - VAE slicing to reduce VRAM usage
        - VAE tiling for large image generation
        - DRAM Extension if VRAM < threshold
        """
        from src.core.config import Config
        
        # Check optimization level
        optimization_level = getattr(Config, 'ROCM_OPTIMIZATION_LEVEL', 1)
        
        if optimization_level == 0:
            logger.info("ROCm optimizations disabled (ROCM_OPTIMIZATION_LEVEL=0)")
            return
        
        logger.info(f"Applying ROCm optimizations (level {optimization_level})...")
        
        # Standard optimizations (level 1+)
        pipeline.enable_attention_slicing(slice_size=1)
        logger.info("✓ Attention slicing enabled")
        
        # Use new VAE methods to avoid deprecation warnings
        if hasattr(pipeline, 'vae') and pipeline.vae is not None:
            if hasattr(pipeline.vae, 'enable_slicing'):
                pipeline.vae.enable_slicing()
                logger.info("✓ VAE slicing enabled")
            if hasattr(pipeline.vae, 'enable_tiling'):
                pipeline.vae.enable_tiling()
                logger.info("✓ VAE tiling enabled")
        
        # Check VRAM for DRAM Extension
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        
        # Aggressive mode (level 2): Force DRAM extension
        if optimization_level == 2:
            logger.info("Aggressive optimization mode: Forcing DRAM Extension")
            self._apply_dram_extension(pipeline)
        # Standard mode (level 1): Enable DRAM extension if VRAM < threshold
        elif self.dram_config["enabled"] or vram_gb < self.dram_config["vram_threshold_gb"]:
            self._apply_dram_extension(pipeline)
        
        # Keep VAE in float32 for stability when using float16
        if self.dtype == torch.float16 and hasattr(pipeline, 'vae'):
            pipeline.vae.to(torch.float32)
            logger.info("✓ VAE kept in float32 for stability")
        
        # Use centralized cache clearing
        clear_cache("cuda", synchronize=False)
        logger.success("ROCm optimizations applied successfully")
    
    def _apply_dram_extension(self, pipeline):
        """Enable DRAM as VRAM extension"""
        if self.device != "cuda":
            return
        
        try:
            if hasattr(pipeline, 'enable_sequential_cpu_offload'):
                pipeline.enable_sequential_cpu_offload()
                logger.success("Sequential CPU offload enabled")
            elif hasattr(pipeline, 'enable_model_cpu_offload'):
                pipeline.enable_model_cpu_offload()
                logger.success("Model CPU offload enabled")
            
            torch.cuda.set_per_process_memory_fraction(0.95)
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True
            
        except Exception as e:
            logger.error(f"Failed to enable DRAM extension: {e}")
    
    def get_safe_params(self, width: int, height: int, steps: int) -> tuple:
        """Auto-adjust parameters based on VRAM"""
        if self.dram_config["enabled"]:
            return width, height, steps
        
        if self.device != "cuda":
            return width, height, steps
        
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        total_pixels = width * height
        
        if vram_gb <= 4:
            if total_pixels > 512 * 512:
                width, height = 512, 512
                logger.warning(f"Auto-adjusted to {width}x{height} for 4GB VRAM")
            if steps > 25:
                steps = 25
                
        elif vram_gb <= 6:
            if total_pixels > 720 * 1280:
                width, height = 720, 1280
                logger.warning(f"Auto-adjusted to {width}x{height} for 6GB VRAM")
            if steps > 35:
                steps = 35
        
        return width, height, steps
    
    def check_vram_availability(self, width: int, height: int, steps: int) -> dict:
        """
        Check if there's enough VRAM for the requested generation.
        Returns dict with can_generate, estimated_vram_gb, available_vram_gb, and adjusted_params if needed.
        """
        result = {
            "can_generate": True,
            "estimated_vram_gb": 0,
            "available_vram_gb": 0,
            "adjusted_params": None,
            "dram_enabled": self.dram_config["enabled"]
        }
        
        if self.device != "cuda":
            return result
        
        try:
            # Get current VRAM status
            total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            allocated_vram = torch.cuda.memory_allocated(0) / (1024**3)
            cached_vram = torch.cuda.memory_reserved(0) / (1024**3)
            available_vram = total_vram - allocated_vram
            
            result["total_vram_gb"] = round(total_vram, 2)
            result["available_vram_gb"] = round(available_vram, 2)
            result["allocated_vram_gb"] = round(allocated_vram, 2)
            
            # Estimate VRAM needed for generation
            # Base model: ~2-4GB, per megapixel: ~0.5-1GB, per 10 steps: ~0.1GB
            total_pixels = width * height
            megapixels = total_pixels / 1_000_000
            
            # Estimation formula (empirical)
            base_vram = 2.5  # Base model loaded
            pixel_vram = megapixels * 0.8  # Per megapixel
            step_vram = (steps / 50) * 0.3  # Steps overhead
            
            estimated_vram = base_vram + pixel_vram + step_vram
            result["estimated_vram_gb"] = round(estimated_vram, 2)
            
            # If DRAM extension is enabled, we can use more
            if self.dram_config["enabled"]:
                max_dram = self.dram_config["max_dram_gb"]
                effective_memory = total_vram + max_dram * 0.3  # DRAM is slower, count 30%
                result["effective_memory_gb"] = round(effective_memory, 2)
                
                if estimated_vram <= effective_memory:
                    result["can_generate"] = True
                    result["using_dram"] = estimated_vram > total_vram
                    return result
            
            # Check if we can generate
            safety_margin = 0.5  # Keep 0.5GB free
            if estimated_vram > (available_vram - safety_margin):
                result["can_generate"] = False
                
                # Try to find adjusted parameters that would work
                adjusted = self._find_safe_params(available_vram - safety_margin, width, height, steps)
                if adjusted:
                    result["adjusted_params"] = adjusted
                    result["can_generate"] = True
                    logger.info(f"VRAM check: adjusted params to {adjusted}")
            
            return result
            
        except Exception as e:
            logger.error(f"VRAM check failed: {e}")
            return result
    
    def _find_safe_params(self, available_vram: float, width: int, height: int, steps: int) -> dict:
        """Find parameters that fit in available VRAM"""
        base_vram = 2.5
        
        # Try reducing resolution first
        resolutions = [
            (width, height),
            (int(width * 0.75), int(height * 0.75)),
            (512, 768),
            (512, 512),
            (384, 512),
        ]
        
        step_options = [steps, min(steps, 35), min(steps, 25), min(steps, 15)]
        
        for w, h in resolutions:
            for s in step_options:
                megapixels = (w * h) / 1_000_000
                estimated = base_vram + megapixels * 0.8 + (s / 50) * 0.3
                
                if estimated <= available_vram:
                    # Round to multiples of 64 for optimal performance
                    w = (w // 64) * 64
                    h = (h // 64) * 64
                    return {"width": max(256, w), "height": max(256, h), "steps": s}
        
        return None
    
    def get_vram_status(self) -> dict:
        """Get current VRAM status for monitoring"""
        if self.device != "cuda":
            return {"device": self.device, "vram_available": False}
        
        try:
            total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            cached = torch.cuda.memory_reserved(0) / (1024**3)
            free = total - allocated
            
            return {
                "device": "cuda",
                "gpu_name": torch.cuda.get_device_name(0),
                "total_vram_gb": round(total, 2),
                "allocated_vram_gb": round(allocated, 2),
                "cached_vram_gb": round(cached, 2),
                "free_vram_gb": round(free, 2),
                "utilization_percent": round((allocated / total) * 100, 1),
                "dram_extension": self.dram_config
            }
        except Exception as e:
            return {"device": "cuda", "error": str(e)}
    
    def cleanup(self):
        """Clean up resources"""
        # Clear VAE cache
        self._vae_cache = None
        self._vae_cache_dtype = None
        
        # Use centralized cleanup
        memory_manager.free_memory_aggressive("cuda")
    
    def cache_vae(self):
        """Cache VAE for faster subsequent generations"""
        if self.pipe is None or self.pipe.vae is None:
            return
        
        try:
            # Keep VAE in float32 for stability
            if self.pipe.vae.dtype != torch.float32:
                self.pipe.vae.to(torch.float32)
                logger.debug("VAE converted to float32 for caching")
            
            # Move to CPU to save VRAM, but keep reference
            if not self.dram_config["enabled"]:
                self._vae_cache = self.pipe.vae
                self._vae_cache_dtype = torch.float32
                logger.debug("VAE cached in memory")
        except Exception as e:
            logger.warning(f"Failed to cache VAE: {e}")
    
    def use_cached_vae(self) -> bool:
        """Use cached VAE if available"""
        if self._vae_cache is not None and self.pipe is not None:
            try:
                self.pipe.vae = self._vae_cache
                if self.device == "cuda":
                    self.pipe.vae.to(self.device)
                logger.debug("Using cached VAE")
                return True
            except Exception as e:
                logger.warning(f"Failed to use cached VAE: {e}")
        return False


# Global instance
pipeline_service = PipelineService()
