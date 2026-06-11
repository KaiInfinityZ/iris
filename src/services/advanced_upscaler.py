"""Advanced image upscaling service with flexible scaling for I.R.I.S."""
from PIL import Image
import torch
from pathlib import Path
import numpy as np
import cv2
from typing import List, Dict, Optional
import math

from ..utils.logger import create_logger
from ..core.config import Config

logger = create_logger("AdvancedUpscaler")


class AdvancedUpscalerService:
    """Handles advanced image upscaling operations with flexible scaling from 2x to 16x"""
    
    def __init__(self, local_model_loader):
        self.local_model_loader = local_model_loader
        self.min_scale = Config.MIN_UPSCALE_FACTOR
        self.max_scale = Config.MAX_UPSCALE_FACTOR
    
    def _has_black_artifacts(self, img_array: np.ndarray, threshold: float = 0.3) -> bool:
        """
        Detect black rectangular artifacts in upscaled image.
        
        Note: Disabled for DirectML as it causes false positives on dark images.
        
        Args:
            img_array: Image array (H, W, C) with values 0-255
            threshold: Fraction of black pixels to consider as artifact (0.0-1.0)
        
        Returns:
            False - artifact detection disabled to prevent false positives
        """
        # Artifact detection disabled - it was causing false positives
        # especially on dark images with DirectML
        return False
        
    def _validate_scale(self, scale: float) -> float:
        """Validate and clamp scale factor"""
        if scale < self.min_scale:
            logger.warning(f"Scale {scale} too small, using minimum {self.min_scale}")
            return self.min_scale
        elif scale > self.max_scale:
            logger.warning(f"Scale {scale} too large, using maximum {self.max_scale}")
            return self.max_scale
        return scale
    
    def _calculate_multi_stage_scaling(self, target_scale: float) -> List[float]:
        """Calculate optimal multi-stage scaling for large scale factors"""
        if target_scale <= 4:
            return [target_scale]
        
        # For scales > 4x, use multiple 4x passes followed by final adjustment
        stages = []
        remaining_scale = target_scale
        
        while remaining_scale > 4:
            stages.append(4.0)
            remaining_scale /= 4.0
            
        if remaining_scale > 1.0:
            stages.append(remaining_scale)
            
        return stages
    
    def upscale_with_realesrgan(self, image: Image.Image, scale: float = 2.0, model_name: str = None) -> Image.Image:
        """Upscale using RealESRGAN with flexible scaling"""
        scale = self._validate_scale(scale)
        
        upscaler = self.local_model_loader.get_upscaler_model(model_name)
        if not upscaler:
            raise RuntimeError("No RealESRGAN models available")
        
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
        if len(img_array.shape) != 3 or img_array.shape[2] != 3:
            raise ValueError(f"Expected RGB image with 3 channels, got shape {img_array.shape}")
        
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Calculate scaling stages for large scale factors
        scale_stages = self._calculate_multi_stage_scaling(scale)
        
        current_img = img_array
        for stage_scale in scale_stages:
            logger.info(f"Applying RealESRGAN scaling stage: {stage_scale}x")
            
            # RealESRGAN typically outputs 4x, so we need to adjust
            if stage_scale <= 4:
                output, _ = upscaler.enhance(current_img, outscale=stage_scale)
            else:
                # For scales > 4, use 4x and then resize
                output, _ = upscaler.enhance(current_img, outscale=4)
                if stage_scale != 4:
                    h, w = output.shape[:2]
                    new_h, new_w = int(h * stage_scale / 4), int(w * stage_scale / 4)
                    output = cv2.resize(output, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            
            # Artifact detection disabled - was causing false positives on dark images
            # The _has_black_artifacts function now always returns False
            
            current_img = output
        
        # Convert back to PIL
        output = cv2.cvtColor(current_img, cv2.COLOR_BGR2RGB)
        
        # Final validation
        if len(output.shape) != 3 or output.shape[2] != 3:
            raise ValueError(f"Output has unexpected shape: {output.shape}")
        
        return Image.fromarray(output)
    
    def upscale_with_lanczos(self, image: Image.Image, scale: float = 2.0) -> Image.Image:
        """Upscale using Lanczos interpolation with flexible scaling"""
        scale = self._validate_scale(scale)
        
        new_width = int(image.width * scale)
        new_height = int(image.height * scale)
        
        logger.info(f"Using Lanczos upscaling: {image.width}x{image.height} -> {new_width}x{new_height}")
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def upscale_with_bicubic(self, image: Image.Image, scale: float = 2.0) -> Image.Image:
        """Upscale using bicubic interpolation"""
        scale = self._validate_scale(scale)
        
        new_width = int(image.width * scale)
        new_height = int(image.height * scale)
        
        logger.info(f"Using bicubic upscaling: {image.width}x{image.height} -> {new_width}x{new_height}")
        return image.resize((new_width, new_height), Image.Resampling.BICUBIC)
    
    def upscale_with_nearest(self, image: Image.Image, scale: float = 2.0) -> Image.Image:
        """Upscale using nearest neighbor (good for pixel art)"""
        scale = self._validate_scale(scale)
        
        new_width = int(image.width * scale)
        new_height = int(image.height * scale)
        
        logger.info(f"Using nearest neighbor upscaling: {image.width}x{image.height} -> {new_width}x{new_height}")
        return image.resize((new_width, new_height), Image.Resampling.NEAREST)
    
    def get_available_methods(self) -> List[Dict]:
        """Get list of available upscaling methods"""
        methods = []
        
        # Add RealESRGAN models first (priority)
        available_models = self.local_model_loader.get_available_upscaler_models()
        if available_models:
            for model_name in available_models:
                methods.append({
                    "id": f"realesrgan_{model_name}",
                    "name": f"RealESRGAN ({model_name})",
                    "desc": f"AI upscaling with {model_name} model (CUDA/Tensor)",
                    "gpu": True,
                    "max_scale": self.max_scale,
                    "model_name": model_name
                })
        else:
            # Add default RealESRGAN method even if no local models (will download automatically)
            methods.append({
                "id": "realesrgan",
                "name": "RealESRGAN x4plus",
                "desc": "AI upscaling with RealESRGAN x4plus (CUDA/Tensor)",
                "gpu": True,
                "max_scale": self.max_scale,
                "model_name": "x4plus"
            })
        
        # Add CPU fallback methods
        methods.extend([
            {"id": "lanczos", "name": "Lanczos", "desc": "High-quality CPU interpolation", "gpu": False, "max_scale": self.max_scale},
            {"id": "bicubic", "name": "Bicubic", "desc": "Standard CPU interpolation", "gpu": False, "max_scale": self.max_scale},
            {"id": "nearest", "name": "Nearest Neighbor", "desc": "Pixel art preservation", "gpu": False, "max_scale": self.max_scale}
        ])
        
        return methods
    
    def get_supported_scales(self) -> List[float]:
        """Get list of supported scale factors"""
        scales = []
        
        # Integer scales from min to max
        for i in range(self.min_scale, min(self.max_scale + 1, 9)):
            scales.append(float(i))
        
        # Add some fractional scales for fine control
        fractional_scales = [1.5, 2.5, 3.5, 6.0, 8.0, 12.0, 16.0]
        for scale in fractional_scales:
            if self.min_scale <= scale <= self.max_scale and scale not in scales:
                scales.append(scale)
        
        return sorted(scales)
    
    def upscale(self, image: Image.Image, scale: float = 2.0, method: str = "realesrgan", model_name: str = None, post_process: str = "natural") -> Image.Image:
        """Upscale image using specified method with flexible scaling
        
        Args:
            image: Input PIL Image
            scale: Upscaling factor (2.0 to 16.0)
            method: Upscaling method ('realesrgan', 'lanczos', 'bicubic', 'nearest')
            model_name: Specific RealESRGAN model name (optional)
            post_process: 'natural' for subtle processing, 'sharp' for maximum sharpness
        
        Returns:
            Upscaled PIL Image
        """
        scale = self._validate_scale(scale)
        
        # Apply post-processing based on mode
        sharpen = post_process == "sharp"
        
        try:
            if method.startswith("realesrgan"):
                # Extract model name from method if provided
                if "_" in method:
                    model_name = method.split("_", 1)[1]
                
                logger.info(f"Using RealESRGAN upscaling at {scale}x with model: {model_name or 'default'}, post_process: {post_process}")
                result = self.upscale_with_realesrgan(image, scale, model_name)
                
                # Apply sharpening for "sharp" mode
                if sharpen:
                    result = self._apply_sharpening(result)
                
                return result
                
            elif method == "bicubic":
                logger.info(f"Using bicubic upscaling at {scale}x")
                result = self.upscale_with_bicubic(image, scale)
                if sharpen:
                    result = self._apply_sharpening(result)
                return result
                
            elif method == "nearest":
                logger.info(f"Using nearest neighbor upscaling at {scale}x")
                return self.upscale_with_nearest(image, scale)  # Nearest is already sharp
                
            else:  # Default to lanczos
                logger.info(f"Using Lanczos upscaling at {scale}x")
                result = self.upscale_with_lanczos(image, scale)
                if sharpen:
                    result = self._apply_sharpening(result)
                return result
                
        except Exception as e:
            logger.warning(f"{method} upscaling failed: {e}, falling back to Lanczos")
            return self.upscale_with_lanczos(image, scale)
    
    def _apply_sharpening(self, image: Image.Image) -> Image.Image:
        """Apply sharpening filter to image"""
        try:
            from PIL import ImageFilter
            # Apply unsharp mask for sharpening effect
            return image.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
        except Exception as e:
            logger.warning(f"Sharpening failed: {e}")
            return image
    
    def batch_upscale(self, images: List[Image.Image], scale: float = 2.0, method: str = "realesrgan", model_name: str = None) -> List[Image.Image]:
        """Batch upscale multiple images"""
        results = []
        
        for i, image in enumerate(images):
            logger.info(f"Processing image {i+1}/{len(images)}")
            try:
                upscaled = self.upscale(image, scale, method, model_name)
                results.append(upscaled)
            except Exception as e:
                logger.error(f"Failed to upscale image {i+1}: {e}")
                results.append(image)  # Return original on failure
                
        return results
    
    def get_memory_usage_estimate(self, image: Image.Image, scale: float, method: str) -> Dict:
        """Estimate memory usage for upscaling operation"""
        input_pixels = image.width * image.height
        output_pixels = int(input_pixels * (scale ** 2))
        
        # Rough estimates in MB
        input_size_mb = (input_pixels * 3 * 4) / (1024 * 1024)  # RGB float32
        output_size_mb = (output_pixels * 3 * 4) / (1024 * 1024)
        
        if method.startswith("realesrgan"):
            # GPU methods need additional memory for model weights and intermediate tensors
            model_memory_mb = 500  # Approximate model size
            working_memory_mb = output_size_mb * 2  # Intermediate tensors
            total_memory_mb = input_size_mb + output_size_mb + model_memory_mb + working_memory_mb
        else:
            # CPU methods
            total_memory_mb = input_size_mb + output_size_mb
        
        return {
            "input_size_mb": round(input_size_mb, 2),
            "output_size_mb": round(output_size_mb, 2),
            "total_memory_mb": round(total_memory_mb, 2),
            "gpu_required": method.startswith("realesrgan")
        }