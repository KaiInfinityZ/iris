"""
Unified device detection and hardware capability management for I.R.I.S.
Ported from jufi.ai V0 with enhancements for Iris.
"""
import torch
import os
import gc
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from ..utils.logger import create_logger

logger = create_logger("DeviceManager")

@dataclass
class DeviceInfo:
    """Hardware device information"""
    device_type: str        # 'cuda', 'directml', 'mps', 'xpu', 'cpu'
    torch_device: Any       # torch.device or directml device
    vendor: str             # 'nvidia', 'amd', 'intel', 'apple', 'cpu'
    name: str               # Full GPU name
    vram_total_gb: float    # Total VRAM in GB
    dtype: torch.dtype      # Default recommended dtype
    supports_fp16: bool     # Hardware supports float16
    supports_bf16: bool     # Hardware supports bfloat16
    supports_compile: bool  # Hardware supports torch.compile

class DeviceManager:
    """Singleton manager for hardware resources"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DeviceManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.info: Optional[DeviceInfo] = None
        self._forced_device: Optional[str] = None  # User-forced device
        self._detect()
        self._initialized = True

    def _detect(self, force_device: Optional[str] = None):
        """Perform hardware detection with optional forced device"""
        
        # Handle forced device first
        if force_device:
            self._forced_device = force_device
            if force_device == "cpu":
                self._init_cpu()
                logger.info("Device forced to CPU")
                return
            elif force_device == "mps" and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                self._init_mps()
                logger.info("Device forced to MPS (Apple Silicon)")
                return
            elif force_device == "xpu" and hasattr(torch, 'xpu') and torch.xpu.is_available():
                self._init_xpu()
                logger.info("Device forced to Intel XPU")
                return
            elif force_device == "directml":
                try:
                    import torch_directml
                    if torch_directml.is_available():
                        self._init_directml(torch_directml)
                        logger.info("Device forced to DirectML")
                        return
                except ImportError:
                    logger.warning("DirectML not available, falling back to auto-detection")
            
            # If forced device not available, fall through to auto-detection
            # but remember the user's preference
            self._forced_device = force_device
        """Perform hardware detection"""
        
        # Priority 1: CUDA (NVIDIA/ROCm)
        if torch.cuda.is_available() and force_device not in ("cpu", "directml"):
            self._init_cuda()
            return

        # Priority 2: DirectML
        try:
            import torch_directml
            if torch_directml.is_available() and force_device != "cpu":
                self._init_directml(torch_directml)
                return
        except ImportError:
            pass

        # Priority 3: Apple Silicon (MPS)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available() and force_device != "cpu":
            self._init_mps()
            return

        # Priority 4: Intel XPU
        try:
            if hasattr(torch, 'xpu') and torch.xpu.is_available():
                self._init_xpu()
                return
        except Exception:
            pass

        # Fallback: CPU
        self._init_cpu()

    def _init_cuda(self):
        """Initialize CUDA device (NVIDIA or AMD ROCm)"""
        gpu_name = torch.cuda.get_device_name(0)
        is_amd = "AMD" in gpu_name.upper() or "RADEON" in gpu_name.upper()
        vendor = "amd" if is_amd else "nvidia"
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        
        # Default dtype logic
        dtype = torch.float16
        if is_amd:
            # RDNA Detection and ROCm optimization
            if any(x in gpu_name.upper() for x in ["RX 9", "RX 90", "RX 9000"]):
                os.environ['HSA_OVERRIDE_GFX_VERSION'] = '12.0.0'
                logger.info("RDNA4 detected - Matrix Core optimizations enabled")
            elif any(x in gpu_name.upper() for x in ["RX 7", "RX 70", "RX 7000"]):
                os.environ['HSA_OVERRIDE_GFX_VERSION'] = '11.0.0'
                logger.info("RDNA3 detected - Matrix Core optimizations enabled")
            elif any(x in gpu_name.upper() for x in ["RX 6", "RX 60", "RX 6000"]):
                os.environ['HSA_OVERRIDE_GFX_VERSION'] = '10.3.0'
                logger.info("RDNA2 detected")
            else:
                dtype = torch.float32  # Older AMD GPUs
                logger.info("Older AMD GPU detected - using FP32")
        
        # Check for torch.compile() support
        supports_compile = any(x in gpu_name.upper() for x in [
            "RTX 30", "RTX 40", "RTX 50", "A100", "H100",  # NVIDIA
            "RX 6", "RX 7", "RX 9"  # AMD RDNA2+
        ])

        self.info = DeviceInfo(
            device_type="cuda",
            torch_device=torch.device("cuda"),
            vendor=vendor,
            name=gpu_name,
            vram_total_gb=vram,
            dtype=dtype,
            supports_fp16=True,
            supports_bf16=not is_amd,  # NVIDIA usually supports bf16, ROCm varies
            supports_compile=supports_compile
        )
        
        # Enable expandable segments for better memory management
        os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
        logger.success(f"✓ CUDA Device Initialized: {gpu_name} ({vram:.1f}GB VRAM)")
        if supports_compile:
            logger.info("  torch.compile() support: ENABLED")

    def _init_directml(self, torch_directml):
        """Initialize DirectML device (Windows AMD/Intel fallback)"""
        device = torch_directml.device()
        try:
            name = torch_directml.device_name(0)
        except:
            name = "DirectML GPU"
            
        # Advanced VRAM & Architecture detection
        vram = 8.0  # Default estimate
        dtype = torch.float32
        supports_fp16 = False
        
        upper_name = name.upper()
        if "RX 9" in upper_name or "9070" in upper_name:
            vram = 16.0
            dtype = torch.float16
            supports_fp16 = True
            logger.info("RDNA4 detected on DirectML")
        elif "RX 7" in upper_name or "7900" in upper_name:
            vram = 20.0
            dtype = torch.float16
            supports_fp16 = True
            logger.info("RDNA3 detected on DirectML")
        elif "RX 6" in upper_name or "6800" in upper_name:
            vram = 16.0
            # RX 6000 can use FP16 but some DirectML kernels are buggy
            dtype = torch.float32
            logger.info("RDNA2 detected on DirectML - using FP32 for stability")
            
        self.info = DeviceInfo(
            device_type="directml",
            torch_device=device,
            vendor="amd" if "RADEON" in upper_name else "intel/nvidia",
            name=name,
            vram_total_gb=vram,
            dtype=dtype,
            supports_fp16=supports_fp16,
            supports_bf16=False,
            supports_compile=False
        )
        logger.success(f"✓ DirectML Device Initialized: {name} (FP16: {supports_fp16})")

    def _init_mps(self):
        """Initialize Apple Silicon (MPS) device"""
        self.info = DeviceInfo(
            device_type="mps",
            torch_device=torch.device("mps"),
            vendor="apple",
            name="Apple Silicon GPU",
            vram_total_gb=16.0,  # Shared memory
            dtype=torch.float32,
            supports_fp16=True,
            supports_bf16=False,
            supports_compile=False
        )
        logger.success("✓ Apple Silicon (MPS) Initialized")

    def _init_xpu(self):
        """Initialize Intel XPU device"""
        name = torch.xpu.get_device_name(0)
        self.info = DeviceInfo(
            device_type="xpu",
            torch_device=torch.device("xpu"),
            vendor="intel",
            name=name,
            vram_total_gb=16.0,
            dtype=torch.float16,
            supports_fp16=True,
            supports_bf16=True,
            supports_compile=False
        )
        logger.success(f"✓ Intel XPU Initialized: {name}")

    def _init_cpu(self):
        """Initialize CPU fallback"""
        self.info = DeviceInfo(
            device_type="cpu",
            torch_device=torch.device("cpu"),
            vendor="cpu",
            name="CPU",
            vram_total_gb=0,
            dtype=torch.float32,
            supports_fp16=False,
            supports_bf16=True,
            supports_compile=False
        )
        logger.info("⚠ Fallback to CPU mode")

    def get_available_vram_gb(self) -> float:
        """Estimate currently available VRAM"""
        if self.info.device_type == "cuda":
            try:
                total = torch.cuda.get_device_properties(0).total_memory
                allocated = torch.cuda.memory_allocated(0)
                return (total - allocated) / 1024**3
            except:
                return self.info.vram_total_gb
        return self.info.vram_total_gb  # Fallback for DirectML/MPS

    def get_vram_stats(self) -> Dict[str, float]:
        """Get detailed VRAM statistics"""
        if self.info.device_type == "cuda":
            try:
                total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                reserved = torch.cuda.memory_reserved(0) / 1024**3
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                free = total - allocated
                
                return {
                    "total_gb": round(total, 2),
                    "reserved_gb": round(reserved, 2),
                    "allocated_gb": round(allocated, 2),
                    "free_gb": round(free, 2),
                    "utilization_percent": round((allocated / total) * 100, 1)
                }
            except:
                pass
        
        return {
            "total_gb": round(self.info.vram_total_gb, 2),
            "reserved_gb": 0,
            "allocated_gb": 0,
            "free_gb": round(self.info.vram_total_gb, 2),
            "utilization_percent": 0
        }

    def empty_cache(self):
        """Clear device cache"""
        gc.collect()
        if self.info.device_type == "cuda":
            try:
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.debug("CUDA cache cleared")
            except:
                pass

    def get_device_info_dict(self) -> Dict[str, Any]:
        """Get device information as dictionary"""
        return {
            "device_type": self.info.device_type,
            "vendor": self.info.vendor,
            "name": self.info.name,
            "vram_total_gb": round(self.info.vram_total_gb, 2),
            "dtype": str(self.info.dtype),
            "supports_fp16": self.info.supports_fp16,
            "supports_bf16": self.info.supports_bf16,
            "supports_compile": self.info.supports_compile,
            **self.get_vram_stats()
        }

    def switch_device(self, target: str) -> Dict[str, Any]:
        """
        Switch to a different device.
        
        Args:
            target: Target device - "cuda", "cpu", "mps", "xpu", "directml", "auto"
        
        Returns:
            Dict with old_device, new_device, and success status
        """
        old_device = self.info.device_type if self.info else "unknown"
        
        if target == "auto":
            self._forced_device = None
            self._detect()
            self._initialized = True
            return {
                "success": True,
                "old_device": old_device,
                "new_device": self.info.device_type
            }
        
        # Validate target device is available
        if target == "cuda" and not torch.cuda.is_available():
            return {"success": False, "error": "CUDA not available"}
        if target == "mps" and not (hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()):
            return {"success": False, "error": "MPS not available"}
        if target == "xpu" and not (hasattr(torch, 'xpu') and torch.xpu.is_available()):
            return {"success": False, "error": "XPU not available"}
        if target == "directml":
            try:
                import torch_directml
                if not torch_directml.is_available():
                    return {"success": False, "error": "DirectML not available"}
            except ImportError:
                return {"success": False, "error": "DirectML not installed"}
        
        # Detect new device
        self._detect(force_device=target)
        self._initialized = True
        
        return {
            "success": True,
            "old_device": old_device,
            "new_device": self.info.device_type
        }

# Global singleton instance
device_manager = DeviceManager()

# Convenience functions
def get_device() -> torch.device:
    """Get the current torch device"""
    return device_manager.info.torch_device

def get_dtype() -> torch.dtype:
    """Get the recommended dtype for the current device"""
    return device_manager.info.dtype

def get_vram_gb() -> float:
    """Get total VRAM in GB"""
    return device_manager.info.vram_total_gb

def get_available_vram_gb() -> float:
    """Get available VRAM in GB"""
    return device_manager.get_available_vram_gb()
