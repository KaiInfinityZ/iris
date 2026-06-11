"""
Memory Management utilities for I.R.I.S.
Centralized VRAM and RAM management to avoid code duplication.
"""
import torch
import gc
from typing import Optional, Dict, Any
from ..utils.logger import create_logger

logger = create_logger("MemoryManager")


class MemoryManager:
    """Singleton for centralized memory management"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MemoryManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
    
    def clear_cache(self, device_type: str = "cuda", synchronize: bool = True):
        """
        Clear memory cache for the specified device.
        
        Args:
            device_type: Device type ('cuda', 'cpu', 'all')
            synchronize: Whether to synchronize CUDA before clearing (slower but more thorough)
        """
        # Always clear Python garbage
        gc.collect()
        
        if device_type in ("cuda", "all"):
            if torch.cuda.is_available():
                try:
                    if synchronize:
                        torch.cuda.synchronize()
                    torch.cuda.empty_cache()
                    logger.debug("CUDA cache cleared")
                except Exception as e:
                    logger.warning(f"Failed to clear CUDA cache: {e}")
        
        if device_type == "all":
            # Clear any other device caches if available
            try:
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    # MPS doesn't have empty_cache, just gc
                    pass
            except:
                pass
    
    def get_memory_stats(self, device_type: str = "cuda") -> Dict[str, Any]:
        """
        Get memory statistics for the specified device.
        
        Args:
            device_type: Device type ('cuda', 'cpu', 'mps')
        
        Returns:
            Dict with memory statistics
        """
        if device_type == "cuda" and torch.cuda.is_available():
            try:
                props = torch.cuda.get_device_properties(0)
                total_gb = props.total_memory / (1024**3)
                allocated_gb = torch.cuda.memory_allocated(0) / (1024**3)
                reserved_gb = torch.cuda.memory_reserved(0) / (1024**3)
                free_gb = total_gb - allocated_gb
                
                return {
                    "device": "cuda",
                    "total_gb": round(total_gb, 2),
                    "allocated_gb": round(allocated_gb, 2),
                    "reserved_gb": round(reserved_gb, 2),
                    "free_gb": round(free_gb, 2),
                    "utilization_percent": round((allocated_gb / total_gb) * 100, 1) if total_gb > 0 else 0
                }
            except Exception as e:
                logger.warning(f"Failed to get CUDA memory stats: {e}")
        
        elif device_type == "cpu":
            try:
                import psutil
                ram = psutil.virtual_memory()
                return {
                    "device": "cpu",
                    "total_gb": round(ram.total / (1024**3), 2),
                    "allocated_gb": round((ram.total - ram.available) / (1024**3), 2),
                    "free_gb": round(ram.available / (1024**3), 2),
                    "utilization_percent": round(ram.percent, 1)
                }
            except ImportError:
                logger.warning("psutil not available for RAM stats")
        
        return {"device": device_type, "error": "Stats not available"}
    
    def estimate_vram_usage(
        self, 
        width: int, 
        height: int, 
        steps: int,
        model_type: str = "sd1.5",
        dtype: torch.dtype = torch.float16
    ) -> float:
        """
        Estimate VRAM usage for image generation.
        
        Args:
            width: Image width
            height: Image height
            steps: Number of inference steps
            model_type: Model type ('sd1.5', 'sdxl', 'flux')
            dtype: Data type (float16 or float32)
        
        Returns:
            Estimated VRAM usage in GB
        """
        # Base model sizes (approximate)
        base_sizes = {
            "sd1.5": 2.0,  # ~2GB for SD 1.5
            "sdxl": 6.0,   # ~6GB for SDXL
            "flux": 12.0,  # ~12GB for FLUX
            "sd3": 8.0     # ~8GB for SD3
        }
        
        base_vram = base_sizes.get(model_type, 2.0)
        
        # Adjust for dtype
        if dtype == torch.float32:
            base_vram *= 1.5
        
        # Calculate latent size (latents are 1/8 the image size in diffusion models)
        latent_width = width // 8
        latent_height = height // 8
        
        # Approximate VRAM for latents (in GB)
        # Formula: channels (4) * width * height * steps * bytes_per_value / 1GB
        bytes_per_value = 2 if dtype == torch.float16 else 4
        latent_vram = (4 * latent_width * latent_height * steps * bytes_per_value) / (1024**3)
        
        # Add some overhead for attention mechanism and misc buffers
        overhead = 0.5
        
        total_vram = base_vram + latent_vram + overhead
        return round(total_vram, 2)
    
    def optimize_params_for_vram(
        self,
        width: int,
        height: int,
        steps: int,
        available_vram_gb: float,
        model_type: str = "sd1.5",
        dtype: torch.dtype = torch.float16
    ) -> Dict[str, int]:
        """
        Optimize parameters to fit within available VRAM.
        
        Args:
            width: Requested width
            height: Requested height
            steps: Requested steps
            available_vram_gb: Available VRAM in GB
            model_type: Model type
            dtype: Data type
        
        Returns:
            Dict with optimized width, height, steps
        """
        # Check if current params fit
        estimated_vram = self.estimate_vram_usage(width, height, steps, model_type, dtype)
        
        if estimated_vram <= available_vram_gb:
            return {"width": width, "height": height, "steps": steps}
        
        # Need to reduce - priority: steps first, then resolution
        logger.warning(f"Estimated VRAM ({estimated_vram:.1f}GB) exceeds available ({available_vram_gb:.1f}GB)")
        
        adjusted_width = width
        adjusted_height = height
        adjusted_steps = steps
        
        # Reduce steps first (less impact on quality)
        while adjusted_steps > 15:
            adjusted_steps = max(15, adjusted_steps - 5)
            estimated_vram = self.estimate_vram_usage(
                adjusted_width, adjusted_height, adjusted_steps, model_type, dtype
            )
            if estimated_vram <= available_vram_gb:
                logger.info(f"Reduced steps to {adjusted_steps} to fit VRAM")
                return {
                    "width": adjusted_width,
                    "height": adjusted_height,
                    "steps": adjusted_steps
                }
        
        # If still too much, reduce resolution
        scale_factor = 0.9
        while estimated_vram > available_vram_gb and adjusted_width > 256:
            adjusted_width = int(adjusted_width * scale_factor) // 8 * 8  # Keep divisible by 8
            adjusted_height = int(adjusted_height * scale_factor) // 8 * 8
            
            estimated_vram = self.estimate_vram_usage(
                adjusted_width, adjusted_height, adjusted_steps, model_type, dtype
            )
        
        logger.info(f"Adjusted params: {adjusted_width}x{adjusted_height}, {adjusted_steps} steps")
        return {
            "width": max(256, adjusted_width),
            "height": max(256, adjusted_height),
            "steps": adjusted_steps
        }
    
    def free_memory_aggressive(self, device_type: str = "cuda"):
        """
        Aggressively free memory (slower but more thorough).
        Use before large operations like model loading.
        
        Args:
            device_type: Device to free memory on
        """
        logger.info("Performing aggressive memory cleanup...")
        
        # Multiple garbage collection passes
        for _ in range(3):
            gc.collect()
        
        if device_type == "cuda" and torch.cuda.is_available():
            try:
                # Synchronize first
                torch.cuda.synchronize()
                # Empty cache
                torch.cuda.empty_cache()
                # Reset peak memory stats
                torch.cuda.reset_peak_memory_stats()
                
                freed_mb = torch.cuda.memory_reserved(0) / (1024**2)
                logger.info(f"Freed ~{freed_mb:.0f}MB CUDA memory")
            except Exception as e:
                logger.warning(f"Aggressive CUDA cleanup failed: {e}")


# Global singleton
memory_manager = MemoryManager()


# Convenience functions
def clear_cache(device_type: str = "cuda", synchronize: bool = True):
    """Clear memory cache"""
    memory_manager.clear_cache(device_type, synchronize)


def get_memory_stats(device_type: str = "cuda") -> Dict[str, Any]:
    """Get memory statistics"""
    return memory_manager.get_memory_stats(device_type)


def estimate_vram_usage(
    width: int,
    height: int,
    steps: int,
    model_type: str = "sd1.5",
    dtype: torch.dtype = torch.float16
) -> float:
    """Estimate VRAM usage"""
    return memory_manager.estimate_vram_usage(width, height, steps, model_type, dtype)


def optimize_params_for_vram(
    width: int,
    height: int,
    steps: int,
    available_vram_gb: float,
    model_type: str = "sd1.5",
    dtype: torch.dtype = torch.float16
) -> Dict[str, int]:
    """Optimize parameters for available VRAM"""
    return memory_manager.optimize_params_for_vram(
        width, height, steps, available_vram_gb, model_type, dtype
    )
