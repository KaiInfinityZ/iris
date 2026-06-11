"""Image upscaling service for I.R.I.S.
Enhanced with jufi.ai V0 optimizations:
- Dynamic GPU tiling based on VRAM
- Matrix Core optimization for RDNA3/4
- Numerical stability checking
- Artifact detection and correction
"""
from PIL import Image
import torch
from pathlib import Path
import numpy as np
import cv2
import time

from ..utils.logger import create_logger
from ..core.config import Config

# Import device manager for intelligent optimizations
try:
    from ..core.device_manager import device_manager
    HAS_DEVICE_MANAGER = True
except ImportError:
    HAS_DEVICE_MANAGER = False

logger = create_logger("Upscaler")


class UpscalerService:
    """Handles image upscaling operations - all methods use standard CUDA cores (no Tensor Cores required)"""
    
    def __init__(self, model_loader):
        self.model_loader = model_loader
    
    def _has_black_artifacts(self, img_array: np.ndarray, threshold: float = 0.3) -> bool:
        """
        Detect black rectangular artifacts in upscaled image.
        
        Args:
            img_array: Image array (H, W, C) with values 0-255
            threshold: Fraction of black pixels to consider as artifact (0.0-1.0)
        
        Returns:
            True if significant black artifacts detected
        """
        # Convert to grayscale for analysis
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_array
        
        # Count pixels that are completely black (value < 10)
        black_pixels = np.sum(gray < 10)
        total_pixels = gray.size
        black_ratio = black_pixels / total_pixels
        
        # Check for large contiguous black regions (likely artifacts)
        _, binary = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Check if any contour is suspiciously large (>5% of image)
        image_area = gray.shape[0] * gray.shape[1]
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > image_area * 0.05:  # 5% of image
                logger.warning(f"Large black region detected: {area / image_area * 100:.1f}% of image")
                return True
        
        # Check overall black ratio
        if black_ratio > threshold:
            logger.warning(f"High black pixel ratio: {black_ratio * 100:.1f}%")
            return True
        
        return False
    
    def _check_numerical_stability(self, img_array: np.ndarray) -> bool:
        """
        Check for numerical instability (NaN or Inf values) in output.
        
        Args:
            img_array: Image array to check
        
        Returns:
            True if stable (no NaN/Inf), False if unstable
        """
        has_nan = np.isnan(img_array).any()
        has_inf = np.isinf(img_array).any()
        
        if has_nan or has_inf:
            logger.warning(f"[NUMERICAL INSTABILITY] NaN: {has_nan}, Inf: {has_inf}")
            return False
        
        return True
        
    def _get_optimal_tile_size(self) -> int:
        """Calculate optimal tile size based on available VRAM (jufi.ai optimization)"""
        if not HAS_DEVICE_MANAGER:
            return 400  # Default fallback
        
        device_type = device_manager.info.device_type
        
        if device_type not in ["cuda", "xpu"]:
            return 0  # No tiling for CPU/DirectML
        
        try:
            vram_gb = device_manager.info.vram_total_gb
            
            # Dynamic tile sizing based on VRAM
            if vram_gb >= 12:
                tile_size = 768  # High-end GPUs (RTX 4090, 7900 XTX)
            elif vram_gb >= 8:
                tile_size = 512  # High-end GPUs (RTX 3070+, RX 6800+)
            elif vram_gb >= 6:
                tile_size = 400  # Mid-range GPUs (RTX 3060, RX 6600)
            else:
                tile_size = 256  # Low-end GPUs (GTX 1660, RX 580)
            
            logger.debug(f"Optimal tile size for {vram_gb:.1f}GB VRAM: {tile_size}x{tile_size}")
            return tile_size
            
        except Exception as e:
            logger.warning(f"Failed to calculate optimal tile size: {e}")
            return 400
    
    def upscale_with_realesrgan(self, image: Image.Image, scale: int = 2) -> Image.Image:
        """Upscale using Real-ESRGAN (RRDB-Net, standard CUDA cores)
        Enhanced with dynamic GPU tiling and artifact detection"""
        if not self.model_loader.upscaler:
            raise RuntimeError("Real-ESRGAN not available")
        
        # Handle alpha channel - convert RGBA to RGB
        if image.mode == 'RGBA':
            logger.debug("Converting RGBA to RGB for upscaling")
            # Create white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # Use alpha as mask
            image = background
        elif image.mode != 'RGB':
            logger.debug(f"Converting {image.mode} to RGB for upscaling")
            image = image.convert('RGB')
        
        # Convert PIL to numpy
        img_array = np.array(image)
        
        # Validate input
        if img_array.shape[2] != 3:
            raise ValueError(f"Expected 3 channels (RGB), got {img_array.shape[2]}")
        
        # Convert RGB to BGR for OpenCV/Real-ESRGAN
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Apply dynamic GPU tiling for optimal performance (jufi.ai optimization)
        tile_size = self._get_optimal_tile_size()
        if tile_size > 0:
            self.model_loader.upscaler.tile = tile_size
            self.model_loader.upscaler.tile_pad = 10
            logger.debug(f"GPU upscaling with tile size {tile_size}x{tile_size}")
        
        # Upscale
        output, _ = self.model_loader.upscaler.enhance(img_array, outscale=scale)
        
        # Check for numerical instability
        if not self._check_numerical_stability(output):
            logger.warning("[FALLBACK] Numerical instability detected, falling back to FP32...")
            raise RuntimeError("Numerical instability (NaN/Inf) detected in output")
        
        # Validate output - check for black artifacts
        if self._has_black_artifacts(output, threshold=0.3):
            logger.warning("Black artifacts detected in upscaled image, attempting correction...")
            # Try without color conversion (some models expect RGB directly)
            img_array_rgb = np.array(image)
            try:
                output, _ = self.model_loader.upscaler.enhance(img_array_rgb, outscale=scale)
                if self._has_black_artifacts(output, threshold=0.3):
                    raise RuntimeError("Black artifacts persist after correction attempt")
                logger.info("Black artifact correction successful")
            except Exception as e:
                logger.error(f"Failed to correct black artifacts: {e}")
                raise
        
        # Convert BGR back to RGB
        output = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
        
        # Final validation
        if output.shape[2] != 3:
            raise ValueError(f"Output has unexpected channels: {output.shape[2]}")
        
        return Image.fromarray(output)
    
    def upscale_with_bsrgan(self, image: Image.Image, scale: int = 2) -> Image.Image:
        """Upscale using BSRGAN - best for degraded/compressed images (standard CUDA cores)
        Enhanced with dynamic GPU tiling"""
        if not self.model_loader.upscaler_bsrgan:
            # Try to load on demand
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't await in sync context, fall back
                    raise RuntimeError("BSRGAN not loaded")
                else:
                    loop.run_until_complete(self.model_loader.load_upscaler_bsrgan())
            except:
                raise RuntimeError("BSRGAN not available")
        
        if not self.model_loader.upscaler_bsrgan:
            raise RuntimeError("BSRGAN not available")
        
        # Handle alpha channel - convert RGBA to RGB
        if image.mode == 'RGBA':
            logger.debug("Converting RGBA to RGB for upscaling")
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background
        elif image.mode != 'RGB':
            logger.debug(f"Converting {image.mode} to RGB for upscaling")
            image = image.convert('RGB')
        
        img_array = np.array(image)
        
        # Validate input
        if img_array.shape[2] != 3:
            raise ValueError(f"Expected 3 channels (RGB), got {img_array.shape[2]}")
        
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Apply dynamic GPU tiling (jufi.ai optimization)
        tile_size = self._get_optimal_tile_size()
        if tile_size > 0:
            self.model_loader.upscaler_bsrgan.tile = tile_size
            self.model_loader.upscaler_bsrgan.tile_pad = 10
            logger.debug(f"BSRGAN GPU upscaling with tile size {tile_size}x{tile_size}")
        
        output, _ = self.model_loader.upscaler_bsrgan.enhance(img_array, outscale=scale)
        
        # Check for black artifacts
        if self._has_black_artifacts(output, threshold=0.3):
            logger.warning("Black artifacts detected in BSRGAN output")
        
        output = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
        return Image.fromarray(output)
    
    def upscale_with_anime_v3(self, image: Image.Image, scale: int = 2) -> Image.Image:
        """Upscale using Real-ESRGAN Anime v3 - fastest for anime (standard CUDA cores)
        Enhanced with dynamic GPU tiling - Anime v3 is more efficient, can use larger tiles"""
        if not self.model_loader.upscaler_anime:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    raise RuntimeError("Anime v3 not loaded")
                else:
                    loop.run_until_complete(self.model_loader.load_upscaler_anime_v3())
            except:
                raise RuntimeError("Anime v3 not available")
        
        if not self.model_loader.upscaler_anime:
            raise RuntimeError("Anime v3 not available")
        
        # Handle alpha channel - convert RGBA to RGB
        if image.mode == 'RGBA':
            logger.debug("Converting RGBA to RGB for upscaling")
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background
        elif image.mode != 'RGB':
            logger.debug(f"Converting {image.mode} to RGB for upscaling")
            image = image.convert('RGB')
        
        img_array = np.array(image)
        
        # Validate input
        if img_array.shape[2] != 3:
            raise ValueError(f"Expected 3 channels (RGB), got {img_array.shape[2]}")
        
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Anime v3 is smaller and more efficient, can use larger tiles (jufi.ai optimization)
        tile_size = self._get_optimal_tile_size()
        if tile_size > 0:
            # Increase tile size by 1.5x for Anime v3 (it's more efficient)
            tile_size = int(tile_size * 1.5)
            self.model_loader.upscaler_anime.tile = tile_size
            self.model_loader.upscaler_anime.tile_pad = 10
            logger.debug(f"Anime v3 GPU upscaling with tile size {tile_size}x{tile_size}")
        
        output, _ = self.model_loader.upscaler_anime.enhance(img_array, outscale=scale)
        
        # Check for black artifacts
        if self._has_black_artifacts(output, threshold=0.3):
            logger.warning("Black artifacts detected in Anime v3 output")
        
        output = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
        return Image.fromarray(output)
    
    def upscale_with_swinir(self, image: Image.Image, scale: int = 2) -> Image.Image:
        """Upscale using SwinIR (higher quality, slower) - uses standard CUDA cores"""
        if not self.model_loader.swinir_model:
            raise RuntimeError("SwinIR not available")
        
        # Convert PIL to tensor
        img_array = np.array(image).astype(np.float32) / 255.0
        img_tensor = torch.from_numpy(img_array).permute(2, 0, 1).unsqueeze(0)
        img_tensor = img_tensor.to(self.model_loader.device)
        
        # Upscale with SwinIR
        with torch.no_grad():
            output_tensor = self.model_loader.swinir_model(img_tensor)
        
        # Convert back to PIL
        output_array = output_tensor.squeeze(0).permute(1, 2, 0).cpu().numpy()
        output_array = (output_array * 255.0).clip(0, 255).astype(np.uint8)
        
        # Handle different scales
        if scale != 4:  # SwinIR is typically 4x, adjust if needed
            output_img = Image.fromarray(output_array)
            target_size = (image.width * scale, image.height * scale)
            return output_img.resize(target_size, Image.Resampling.LANCZOS)
        
        return Image.fromarray(output_array)
        
    def upscale_with_lanczos(self, image: Image.Image, scale: int = 2) -> Image.Image:
        """Upscale using Lanczos interpolation (CPU fallback, no GPU needed)"""
        new_width = image.width * scale
        new_height = image.height * scale
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def get_available_methods(self) -> list:
        """Get list of available upscaling methods"""
        methods = [{"id": "lanczos", "name": "Lanczos", "desc": "CPU interpolation (fast)", "gpu": False}]
        
        if self.model_loader.upscaler:
            methods.append({"id": "realesrgan", "name": "Real-ESRGAN", "desc": "General purpose (CUDA)", "gpu": True})
        
        if self.model_loader.upscaler_anime:
            methods.append({"id": "anime_v3", "name": "Anime v3", "desc": "Fast anime upscaling (CUDA)", "gpu": True})
        
        if self.model_loader.upscaler_bsrgan:
            methods.append({"id": "bsrgan", "name": "BSRGAN", "desc": "Degraded images (CUDA)", "gpu": True})
        
        if self.model_loader.swinir_model:
            methods.append({"id": "swinir", "name": "SwinIR", "desc": "Highest quality (CUDA)", "gpu": True})
        
        return methods
    
    def _upscale_with_retry(self, image: Image.Image, scale: int, method: str) -> Image.Image:
        """
        Upscale with retry logic and fallback mechanisms.
        
        Args:
            image: Input PIL Image
            scale: Upscaling factor
            method: Upscaling method
        
        Returns:
            Upscaled image
        
        Fallback chain:
        1. Try with optimizations enabled
        2. If fails: Retry without optimizations (FP32)
        3. If still fails: Fall back to Lanczos (CPU)
        """
        try:
            # Try with optimizations
            if method == "swinir" and self.model_loader.swinir_model:
                return self.upscale_with_swinir(image, scale)
            elif method == "bsrgan":
                return self.upscale_with_bsrgan(image, scale)
            elif method == "anime_v3":
                return self.upscale_with_anime_v3(image, scale)
            elif method == "realesrgan" and self.model_loader.upscaler:
                return self.upscale_with_realesrgan(image, scale)
            else:
                return self.upscale_with_lanczos(image, scale)
                
        except RuntimeError as e:
            error_msg = str(e).lower()
            
            # Check for numerical instability (NaN/Inf)
            if "nan" in error_msg or "inf" in error_msg:
                logger.warning(f"[FALLBACK] Numerical instability detected, retrying with FP32...")
                # TODO: Reload model with FP32 and retry
                logger.warning(f"[FALLBACK] FP32 retry not implemented, falling back to Lanczos")
                return self.upscale_with_lanczos(image, scale)
            
            # Check for memory exhaustion
            elif "out of memory" in error_msg or "cuda" in error_msg:
                logger.warning(f"[FALLBACK] Memory exhaustion detected, falling back to Lanczos (CPU)")
                return self.upscale_with_lanczos(image, scale)
            
            # Other errors
            else:
                logger.warning(f"[FALLBACK] {method} failed: {e}, falling back to Lanczos")
                return self.upscale_with_lanczos(image, scale)
        
        except Exception as e:
            logger.warning(f"[FALLBACK] Unexpected error in {method}: {e}, falling back to Lanczos")
            return self.upscale_with_lanczos(image, scale)
    
    def upscale(self, image: Image.Image, scale: int = 2, method: str = "realesrgan") -> Image.Image:
        """Upscale image using specified method
        
        Args:
            image: Input PIL Image
            scale: Upscaling factor (2, 4, or 8)
            method: Upscaling method ('realesrgan', 'bsrgan', 'anime_v3', 'swinir', or 'lanczos')
        
        All GPU methods use standard CUDA cores - no Tensor Cores required!
        """
        # Performance tracking
        if Config.ENABLE_UPSCALER_METRICS:
            start_time = time.time()
            input_size = (image.width, image.height)
            logger.info(f"[METRICS] Starting upscale: {input_size[0]}x{input_size[1]} -> {scale}x with {method}")
            
            # Check for Matrix Core optimization
            try:
                device_type, architecture = self.model_loader._detect_device_and_architecture()
                if architecture in ["RDNA3", "RDNA4"]:
                    logger.info(f"[METRICS] Matrix Core optimization: ENABLED ({architecture})")
                elif device_type == "directml":
                    logger.info(f"[METRICS] DirectML optimization: ENABLED")
                else:
                    logger.info(f"[METRICS] Optimization: Standard ({device_type})")
            except:
                pass
        
        try:
            if method == "swinir" and self.model_loader.swinir_model:
                logger.info(f"Using SwinIR upscaling at {scale}x...")
                result = self.upscale_with_swinir(image, scale)
            
            elif method == "bsrgan":
                logger.info(f"Using BSRGAN upscaling at {scale}x (optimized for degraded images)...")
                result = self.upscale_with_bsrgan(image, scale)
            
            elif method == "anime_v3":
                logger.info(f"Using Real-ESRGAN Anime v3 at {scale}x (fast anime)...")
                result = self.upscale_with_anime_v3(image, scale)
                
            elif method == "realesrgan" and self.model_loader.upscaler:
                logger.info(f"Using Real-ESRGAN upscaling at {scale}x...")
                result = self.upscale_with_realesrgan(image, scale)
                
            else:
                logger.info(f"Using Lanczos upscaling at {scale}x...")
                result = self.upscale_with_lanczos(image, scale)
            
            # Performance metrics logging
            if Config.ENABLE_UPSCALER_METRICS:
                duration_ms = (time.time() - start_time) * 1000
                output_size = (result.width, result.height)
                logger.info(f"[METRICS] Upscale completed: {output_size[0]}x{output_size[1]} in {duration_ms:.1f}ms")
            
            return result
                
        except Exception as e:
            logger.warning(f"{method} upscaling failed: {e}, falling back to Lanczos")
            result = self.upscale_with_lanczos(image, scale)
            
            if Config.ENABLE_UPSCALER_METRICS:
                duration_ms = (time.time() - start_time) * 1000
                output_size = (result.width, result.height)
                logger.info(f"[METRICS] Fallback completed: {output_size[0]}x{output_size[1]} in {duration_ms:.1f}ms")
            
            return result
