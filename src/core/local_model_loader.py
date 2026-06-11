"""Local model loading and management for I.R.I.S."""
import torch
from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline
from pathlib import Path
import os
import json
from typing import Dict, List, Optional

from ..utils.logger import create_logger
from .config import Config

logger = create_logger("LocalModelLoader")


class LocalModelLoader:
    """Handles loading and managing AI models from local directories"""
    
    def __init__(self):
        self.pipe = None
        self.img2img_pipe = None
        self.upscaler_models = {}  # Dictionary to store multiple upscaler models
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.huggingface_path = Path(Config.HUGGINGFACE_MODELS_PATH)
        self.realesrgan_path = Path(Config.REALESRGAN_MODELS_PATH)
        self.swinir_path = Path(Config.SWINIR_MODELS_PATH)
        self.hf_home = Path(Config.HF_HOME)
        
        # Ensure model directories exist
        self._ensure_model_directories()
        
    def _ensure_model_directories(self):
        """Create model directories if they don't exist"""
        try:
            self.huggingface_path.mkdir(parents=True, exist_ok=True)
            self.realesrgan_path.mkdir(parents=True, exist_ok=True)
            self.swinir_path.mkdir(parents=True, exist_ok=True)
            self.hf_home.mkdir(parents=True, exist_ok=True)
            
            # Log relative paths for cross-platform compatibility
            try:
                from pathlib import Path
                base_dir = Path(__file__).resolve().parents[2]  # Project root
                hf_rel = self.huggingface_path.relative_to(base_dir)
                re_rel = self.realesrgan_path.relative_to(base_dir)
                sw_rel = self.swinir_path.relative_to(base_dir)
                cache_rel = self.hf_home.relative_to(base_dir) if self.hf_home.is_relative_to(base_dir) else self.hf_home
                logger.info(f"Model directories ensured: {hf_rel}, {re_rel}, {sw_rel}, {cache_rel}")
            except (ValueError, AttributeError):
                # Fallback if relative path fails
                logger.info(f"Model directories ensured: {self.huggingface_path}, {self.realesrgan_path}, {self.swinir_path}, {self.hf_home}")
        except Exception as e:
            logger.warning(f"Could not create model directories: {e}")
    
    def scan_local_models(self) -> Dict[str, List[str]]:
        """Scan local directories for available models"""
        models = {
            "diffusion": [],
            "upscaler": []
        }
        
        # Scan HuggingFace models
        if self.huggingface_path.exists():
            # Check both direct path and hub subdirectory
            search_paths = [self.huggingface_path]
            hub_path = self.huggingface_path / "hub"
            if hub_path.exists():
                search_paths.append(hub_path)
            
            for search_path in search_paths:
                for model_dir in search_path.iterdir():
                    if model_dir.is_dir() and model_dir.name not in ["hub", "accelerate", "xet", ".locks"]:
                        # Check if it's a valid diffusion model (direct structure)
                        if self._is_valid_diffusion_model(model_dir):
                            models["diffusion"].append(str(model_dir))
                        # Check if it has snapshots subdirectory (HF cache structure)
                        elif (model_dir / "snapshots").exists():
                            snapshots_dir = model_dir / "snapshots"
                            # Get the latest snapshot (usually there's only one)
                            snapshot_dirs = [d for d in snapshots_dir.iterdir() if d.is_dir()]
                            if snapshot_dirs:
                                # Use the most recently modified snapshot
                                latest_snapshot = max(snapshot_dirs, key=lambda p: p.stat().st_mtime)
                                if self._is_valid_diffusion_model(latest_snapshot):
                                    models["diffusion"].append(str(latest_snapshot))
                        
        # Scan RealESRGAN models
        if self.realesrgan_path.exists():
            for model_file in self.realesrgan_path.glob("*.pth"):
                models["upscaler"].append(str(model_file))
                
        logger.info(f"Found {len(models['diffusion'])} diffusion models and {len(models['upscaler'])} upscaler models")
        return models
    
    def _is_valid_diffusion_model(self, model_path: Path) -> bool:
        """Check if a directory contains a valid diffusion model"""
        # Check for model_index.json first
        if not (model_path / "model_index.json").exists():
            return False
        
        # Check for required components (unet OR transformer for FLUX/SD3)
        has_unet = (model_path / "unet").exists()
        has_transformer = (model_path / "transformer").exists()
        
        if not (has_unet or has_transformer):
            return False
        
        # Check for other required files
        required_files = ["vae", "text_encoder", "tokenizer"]
        for required in required_files:
            if not (model_path / required).exists():
                return False
        
        return True
    
    async def load_text2img_pipeline(self, model_path: str = None):
        """Load the text-to-image pipeline from local path"""
        if model_path is None:
            # Use first available local model
            models = self.scan_local_models()
            if not models["diffusion"]:
                logger.error("No local diffusion models found")
                return False
            model_path = models["diffusion"][0]
            
        logger.info(f"Loading text-to-image model from: {model_path}")
        
        try:
            self.pipe = StableDiffusionPipeline.from_pretrained(
                model_path,
                torch_dtype=self.dtype,
                safety_checker=None,
                local_files_only=True  # Force local loading
            )
            self.pipe = self.pipe.to(self.device)
            
            # Enable memory optimizations
            if torch.cuda.is_available():
                self.pipe.enable_attention_slicing()
                self.pipe.enable_vae_slicing()
                self.pipe.enable_vae_tiling()
                
                # DRAM extension for low VRAM GPUs
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if vram_gb < Config.VRAM_THRESHOLD_GB:
                    self.pipe.enable_model_cpu_offload()
                    logger.info(f"DRAM Extension enabled for {vram_gb:.1f}GB VRAM GPU")
                    
            logger.info("Text-to-image pipeline loaded successfully from local path")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load text-to-image pipeline: {e}")
            return False
            
    async def load_img2img_pipeline(self):
        """Load the image-to-image pipeline"""
        if not self.pipe:
            logger.error("Text-to-image pipeline must be loaded first")
            return False
            
        try:
            logger.info("Loading image-to-image pipeline...")
            self.img2img_pipe = StableDiffusionImg2ImgPipeline(
                vae=self.pipe.vae,
                text_encoder=self.pipe.text_encoder,
                tokenizer=self.pipe.tokenizer,
                unet=self.pipe.unet,
                scheduler=self.pipe.scheduler,
                safety_checker=None,
                feature_extractor=self.pipe.feature_extractor
            )
            self.img2img_pipe = self.img2img_pipe.to(self.device)
            
            logger.info("Image-to-image pipeline loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load image-to-image pipeline: {e}")
            return False
    
    async def load_realesrgan_models(self):
        """Load all available RealESRGAN models from local directory or download defaults"""
        try:
            # Apply torchvision compatibility fix
            self._patch_torchvision_compat()
            
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan import RealESRGANer
            
            # Detect device and architecture
            device_type, architecture = self._detect_device_and_architecture()
            
            # Select precision based on device
            dtype = self._select_precision(device_type, architecture)
            use_half = (dtype == torch.float16)
            
            # Configure device string for RealESRGANer
            if device_type == "directml":
                try:
                    import torch_directml
                    device = torch_directml.device()
                except ImportError:
                    device = "cpu"
                    logger.warning("DirectML not available, falling back to CPU")
            elif device_type in ["cuda", "mps", "xpu"]:
                device = device_type
            else:
                device = "cpu"
            
            # Get VRAM for tile size configuration
            vram_gb = 8.0  # Default assumption
            if device_type == "cuda" and torch.cuda.is_available():
                try:
                    vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                except:
                    pass
            
            # DirectML doesn't report VRAM correctly - disable tiling to prevent black artifacts
            # Black artifacts from tiling are worse than OOM, so we use 0 (no tiling)
            if device_type == "directml":
                # Use larger tile (0 = no tiling) to avoid black block artifacts
                # RealESRGAN with DirectML has issues with tile overlap blending
                vram_gb = 16.0  # Force high VRAM config to disable tiling
                logger.info("DirectML detected: disabling tile-based processing to prevent black artifacts")
            
            # Configure tile size based on VRAM
            tile_size = self._configure_tile_size(vram_gb)
            
            # For DirectML: use much larger tile to prevent black artifacts
            # The issue is tile overlap blending doesn't work well with DirectML
            if device_type == "directml":
                tile_size = 0  # Disable tiling entirely for DirectML
            
            # Get optimization level from config
            optimization_level = Config.DIRECTML_OPTIMIZATION_LEVEL
            
            models = self.scan_local_models()
            
            # If no local models found, set up default downloadable models
            if not models["upscaler"]:
                logger.info("No local RealESRGAN models found, setting up default models for download")
                
                # Default RealESRGAN models that will be downloaded automatically
                default_models = {
                    "x4plus": {
                        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
                        "arch": "standard"  # 23 blocks
                    },
                    "x4plus_anime": {
                        "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth", 
                        "arch": "anime"  # 6 blocks
                    }
                }
                
                for model_name, model_info in default_models.items():
                    try:
                        # Determine model architecture
                        if model_info["arch"] == "anime":
                            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
                        else:
                            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
                        
                        upscaler = RealESRGANer(
                            scale=4,
                            model_path=model_info["url"],  # RealESRGANer will download automatically
                            model=model,
                            tile=tile_size,
                            tile_pad=20,  # Increased to prevent black artifacts at tile edges
                            pre_pad=0,
                            half=use_half,
                            device=device
                        )
                        
                        # Apply DirectML optimizations if on DirectML device
                        if device_type == "directml" and optimization_level > 0:
                            self._apply_directml_optimizations(upscaler, optimization_level)
                        
                        self.upscaler_models[model_name] = upscaler
                        
                        # Log optimization status
                        opt_status = f"DirectML optimized (level={optimization_level})" if device_type == "directml" and optimization_level > 0 else "standard"
                        matrix_core_status = " with Matrix Cores" if architecture in ["RDNA3", "RDNA4"] else ""
                        logger.info(f"Loaded RealESRGAN model: {model_name} ({opt_status}{matrix_core_status}, will download on first use)")
                        
                    except Exception as e:
                        logger.warning(f"Failed to setup model {model_name}: {e}")
            else:
                # Load local models
                for model_path in models["upscaler"]:
                    model_name = Path(model_path).stem
                    
                    try:
                        # Determine model architecture based on filename
                        if "anime" in model_name.lower():
                            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
                        else:
                            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
                        
                        upscaler = RealESRGANer(
                            scale=4,
                            model_path=model_path,
                            model=model,
                            tile=tile_size,
                            tile_pad=20,  # Increased to prevent black artifacts at tile edges
                            pre_pad=0,
                            half=use_half,
                            device=device
                        )
                        
                        # Apply DirectML optimizations if on DirectML device
                        if device_type == "directml" and optimization_level > 0:
                            self._apply_directml_optimizations(upscaler, optimization_level)
                        
                        self.upscaler_models[model_name] = upscaler
                        
                        # Log optimization status
                        opt_status = f"DirectML optimized (level={optimization_level})" if device_type == "directml" and optimization_level > 0 else "standard"
                        matrix_core_status = " with Matrix Cores" if architecture in ["RDNA3", "RDNA4"] else ""
                        logger.info(f"Loaded local RealESRGAN model: {model_name} ({opt_status}{matrix_core_status})")
                        
                    except Exception as e:
                        logger.warning(f"Failed to load model {model_name}: {e}")
                        
            if self.upscaler_models:
                logger.info(f"Successfully loaded {len(self.upscaler_models)} RealESRGAN models")
                return True
            else:
                logger.warning("No RealESRGAN models could be loaded")
                return False
                
        except ImportError as e:
            logger.warning(f"RealESRGAN dependencies not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load RealESRGAN models: {e}")
            return False
    
    def _patch_torchvision_compat(self):
        """Fix torchvision >= 0.18 compatibility with basicsr/realesrgan"""
        try:
            import torchvision.transforms.functional_tensor
        except ImportError:
            import sys
            import types
            import torchvision.transforms.functional as F
            
            # Create dummy module with required functions
            functional_tensor = types.ModuleType('torchvision.transforms.functional_tensor')
            functional_tensor.rgb_to_grayscale = F.rgb_to_grayscale
            sys.modules['torchvision.transforms.functional_tensor'] = functional_tensor
    
    def _detect_device_and_architecture(self):
        """
        Detect device and AMD GPU architecture.
        
        Returns:
            Tuple of (device_type: str, architecture: str)
            device_type: "directml", "cuda", "mps", "xpu", "cpu"
            architecture: "RDNA1", "RDNA2", "RDNA3", "RDNA4", "RDNA_PRO", "Unknown", or None
        """
        architecture = None
        
        # Check for DirectML (AMD/Intel GPUs on Windows)
        try:
            import torch_directml
            if torch_directml.is_available():
                device_type = "directml"
                
                # Try to get GPU name from Windows
                try:
                    import subprocess
                    result = subprocess.run(
                        ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    gpu_lines = [line.strip() for line in result.stdout.split('\n') 
                                if line.strip() and line.strip() != 'Name']
                    if gpu_lines:
                        gpu_name = gpu_lines[0]
                        if self._is_amd_gpu(gpu_name):
                            architecture = self._detect_rdna_architecture(gpu_name)
                            logger.info(f"[SUCCESS] AMD GPU detected via DirectML: {gpu_name}")
                        else:
                            logger.info(f"DirectML GPU detected: {gpu_name}")
                except Exception as e:
                    logger.debug(f"Could not get GPU name: {e}")
                
                return (device_type, architecture)
        except ImportError:
            pass  # DirectML not installed
        
        # CUDA covers both NVIDIA and AMD ROCm
        if torch.cuda.is_available():
            device_type = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            
            # Detect if AMD GPU
            if self._is_amd_gpu(gpu_name):
                architecture = self._detect_rdna_architecture(gpu_name)
                logger.info(f"AMD GPU detected: {gpu_name}")
            else:
                logger.info(f"NVIDIA GPU detected: {gpu_name}")
            
            return (device_type, architecture)
        
        # Apple Silicon
        if torch.backends.mps.is_available():
            return ("mps", None)
        
        # Intel Arc
        if hasattr(torch, 'xpu') and torch.xpu.is_available():
            return ("xpu", None)
        
        # CPU fallback
        return ("cpu", None)
    
    def _is_amd_gpu(self, gpu_name: str) -> bool:
        """
        Detect if GPU is AMD Radeon.
        
        Args:
            gpu_name: GPU name from torch.cuda.get_device_name() or wmic
        
        Returns:
            True if AMD GPU, False otherwise
        """
        gpu_name_upper = gpu_name.upper()
        return "AMD" in gpu_name_upper or "RADEON" in gpu_name_upper
    
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
    
    def _select_precision(self, device_type: str, architecture: str = None) -> torch.dtype:
        """
        Select appropriate precision for device and architecture.
        
        Args:
            device_type: Device type ("directml", "cuda", "mps", "xpu", "cpu")
            architecture: AMD architecture string (optional)
        
        Returns:
            torch.float16 for DirectML and RDNA1+ devices, torch.float32 otherwise
        """
        # Check for ROCM_FORCE_FLOAT32 configuration override
        if hasattr(Config, 'ROCM_FORCE_FLOAT32') and Config.ROCM_FORCE_FLOAT32:
            logger.info("ROCM_FORCE_FLOAT32 enabled, using float32")
            return torch.float32
        
        # DirectML works best with float16
        if device_type == "directml":
            if architecture in ["RDNA3", "RDNA4"]:
                logger.success(f"AMD {architecture} detected with Matrix Cores! Using float16")
            elif architecture:
                logger.success(f"AMD {architecture} detected! Using float16")
            else:
                logger.info("DirectML device detected, using float16")
            return torch.float16
        
        # CUDA with AMD GPU: RDNA1+ supports float16
        if device_type == "cuda" and architecture:
            if architecture in ["RDNA1", "RDNA2", "RDNA3", "RDNA4", "RDNA_PRO"]:
                if architecture in ["RDNA3", "RDNA4"]:
                    logger.success(f"AMD {architecture} detected with Matrix Cores! Using float16")
                else:
                    logger.success(f"AMD {architecture} detected! Using float16")
                return torch.float16
            else:
                logger.info(f"AMD GPU architecture {architecture}: Using float32 for compatibility")
                return torch.float32
        
        # CUDA with NVIDIA GPU: Check for tensor cores
        if device_type == "cuda":
            gpu_name = torch.cuda.get_device_name(0)
            has_tensor_cores = any(arch in gpu_name.upper() 
                                  for arch in ["RTX", "A100", "V100", "T4", "A10", "A40"])
            if has_tensor_cores:
                logger.success("NVIDIA Tensor Cores detected! Using float16")
                return torch.float16
            else:
                logger.info("No Tensor Cores detected, using float32")
                return torch.float32
        
        # CPU, MPS, XPU: Use float32
        return torch.float32
    
    def _apply_directml_optimizations(self, model, optimization_level: int = 1):
        """
        Apply DirectML optimizations to upscaler model.
        
        Args:
            model: The upscaler model to optimize
            optimization_level: 0=disabled, 1=standard, 2=aggressive
        
        Returns:
            True if optimizations applied successfully, False otherwise
        """
        if optimization_level == 0:
            logger.info("DirectML optimizations disabled (level=0)")
            return False
        
        try:
            # Import attention processor
            try:
                from diffusers.models.attention_processor import AttnProcessor
            except ImportError:
                logger.warning("diffusers not available, skipping attention processor optimization")
                AttnProcessor = None
            
            logger.info("Applying DirectML optimizations...")
            
            # Apply attention processor if model has unet
            if AttnProcessor and hasattr(model, 'unet'):
                try:
                    model.unet.set_attn_processor(AttnProcessor())
                    logger.info("✓ DirectML-compatible attention processor set")
                except Exception as e:
                    logger.debug(f"Could not set attention processor: {e}")
            
            # Enable attention slicing if available
            if hasattr(model, 'enable_attention_slicing'):
                try:
                    model.enable_attention_slicing(slice_size=1)
                    logger.info("✓ Attention slicing enabled")
                except Exception as e:
                    logger.debug(f"Could not enable attention slicing: {e}")
            
            # Enable VAE optimizations if model has VAE
            if hasattr(model, 'vae'):
                try:
                    if hasattr(model, 'enable_vae_slicing'):
                        model.enable_vae_slicing()
                        logger.info("✓ VAE slicing enabled")
                except Exception as e:
                    logger.debug(f"Could not enable VAE slicing: {e}")
                
                try:
                    if hasattr(model, 'enable_vae_tiling'):
                        model.enable_vae_tiling()
                        logger.info("✓ VAE tiling enabled")
                except Exception as e:
                    logger.debug(f"Could not enable VAE tiling: {e}")
            
            logger.success("[SUCCESS] DirectML optimizations applied successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to apply DirectML optimizations: {e}")
            return False
    
    def _configure_tile_size(self, vram_gb: float) -> int:
        """
        Configure tile size based on available VRAM.
        
        Args:
            vram_gb: Available VRAM in GB
        
        Returns:
            Tile size (0 = no tiling, >0 = tile size in pixels)
        """
        threshold = Config.UPSCALER_VRAM_THRESHOLD_GB
        
        if vram_gb < threshold:
            tile_size = Config.UPSCALER_TILE_SIZE_LOW_VRAM
            logger.info(f"Low VRAM ({vram_gb:.1f}GB < {threshold}GB): Using tile size {tile_size}px")
        else:
            tile_size = Config.UPSCALER_TILE_SIZE_HIGH_VRAM
            if tile_size == 0:
                logger.info(f"High VRAM ({vram_gb:.1f}GB >= {threshold}GB): No tiling (best quality)")
            else:
                logger.info(f"High VRAM ({vram_gb:.1f}GB >= {threshold}GB): Using tile size {tile_size}px")
        
        return tile_size
    
    def get_available_upscaler_models(self) -> List[str]:
        """Get list of available upscaler model names"""
        model_names = list(self.upscaler_models.keys())
        
        # If no models loaded, return default model names that will be available
        if not model_names:
            return ["x4plus", "x4plus_anime"]
            
        return model_names
    
    def get_upscaler_model(self, model_name: str = None):
        """Get specific upscaler model or default"""
        if model_name and model_name in self.upscaler_models:
            return self.upscaler_models[model_name]
        elif self.upscaler_models:
            # Return first available model
            return next(iter(self.upscaler_models.values()))
        return None
    
    def get_pipelines(self):
        """Get loaded pipelines"""
        return {
            "text2img": self.pipe,
            "img2img": self.img2img_pipe,
            "upscaler_models": self.upscaler_models
        }