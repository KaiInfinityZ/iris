"""API routes for advanced image upscaling"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from PIL import Image
import io
import os
from pathlib import Path
from typing import Optional, List
import json
from datetime import datetime

from ...services.advanced_upscaler import AdvancedUpscalerService
from ...core.local_model_loader import LocalModelLoader
from ...utils.logger import create_logger

logger = create_logger("UpscalerAPI")

router = APIRouter(prefix="/api/upscaler", tags=["upscaler"])

# Global instances (will be initialized in main app)
upscaler_service: Optional[AdvancedUpscalerService] = None
model_loader: Optional[LocalModelLoader] = None


def init_upscaler_routes(local_model_loader: LocalModelLoader):
    """Initialize upscaler routes with model loader"""
    global upscaler_service, model_loader
    model_loader = local_model_loader
    upscaler_service = AdvancedUpscalerService(local_model_loader)


@router.get("/methods")
async def get_upscaling_methods():
    """Get available upscaling methods"""
    if not upscaler_service:
        raise HTTPException(status_code=500, detail="Upscaler service not initialized")
    
    methods = upscaler_service.get_available_methods()
    scales = upscaler_service.get_supported_scales()
    
    return {
        "methods": methods,
        "supported_scales": scales,
        "min_scale": upscaler_service.min_scale,
        "max_scale": upscaler_service.max_scale
    }


@router.get("/models")
async def get_available_models():
    """Get available RealESRGAN models"""
    if not model_loader:
        raise HTTPException(status_code=500, detail="Model loader not initialized")
    
    models = model_loader.get_available_upscaler_models()
    return {"models": models}


@router.post("/upscale")
async def upscale_image(
    file: UploadFile = File(...),
    scale: float = Form(2.0),
    method: str = Form("realesrgan"),
    model_name: Optional[str] = Form(None),
    format: str = Form("PNG"),
    post_process: str = Form("natural")
):
    """Upscale an uploaded image"""
    if not upscaler_service:
        raise HTTPException(status_code=500, detail="Upscaler service not initialized")
    
    try:
        # Validate file type
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Load image
        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        logger.info(f"Upscaling image: {image.width}x{image.height} -> {scale}x with {method}")
        
        # Upscale image with post-processing
        upscaled_image = upscaler_service.upscale(
            image=image,
            scale=scale,
            method=method,
            model_name=model_name,
            post_process=post_process
        )
        
        # Save to upscaled folder
        BASE_DIR = Path(__file__).resolve().parents[3]
        upscaled_dir = BASE_DIR / "outputs" / "upscaled"
        upscaled_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"upscale_{timestamp}_x{scale}.{format.lower()}"
        filepath = upscaled_dir / filename
        
        upscaled_image.save(filepath, format=format.upper(), quality=95)
        logger.info(f"Saved upscaled image to: {filepath}")
        
        # Also save to main outputs for gallery visibility
        main_output = BASE_DIR / "outputs" / filename
        upscaled_image.save(main_output, format=format.upper(), quality=95)
        
        # Convert to bytes
        output_buffer = io.BytesIO()
        upscaled_image.save(output_buffer, format=format.upper(), quality=95)
        output_buffer.seek(0)
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(output_buffer.read()),
            media_type=f"image/{format.lower()}",
            headers={
                "Content-Disposition": f"attachment; filename=upscaled_{scale}x.{format.lower()}",
                "X-Original-Size": f"{image.width}x{image.height}",
                "X-Upscaled-Size": f"{upscaled_image.width}x{upscaled_image.height}",
                "X-Scale-Factor": str(scale),
                "X-Method": method,
                "X-Saved-Path": str(filepath)
            }
        )
        
    except Exception as e:
        logger.error(f"Upscaling failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upscaling failed: {str(e)}")


@router.post("/batch-upscale")
async def batch_upscale_images(
    files: List[UploadFile] = File(...),
    scale: float = Form(2.0),
    method: str = Form("realesrgan"),
    model_name: Optional[str] = Form(None)
):
    """Batch upscale multiple images"""
    if not upscaler_service:
        raise HTTPException(status_code=500, detail="Upscaler service not initialized")
    
    if len(files) > 10:  # Limit batch size
        raise HTTPException(status_code=400, detail="Maximum 10 files per batch")
    
    try:
        images = []
        
        # Load all images
        for file in files:
            if not file.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not an image")
            
            image_data = await file.read()
            image = Image.open(io.BytesIO(image_data))
            
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            images.append(image)
        
        # Batch upscale
        upscaled_images = upscaler_service.batch_upscale(
            images=images,
            scale=scale,
            method=method,
            model_name=model_name
        )
        
        # Create ZIP file with results
        import zipfile
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, upscaled_image in enumerate(upscaled_images):
                img_buffer = io.BytesIO()
                upscaled_image.save(img_buffer, format="PNG", quality=95)
                img_buffer.seek(0)
                
                original_name = files[i].filename or f"image_{i}"
                name_without_ext = original_name.rsplit('.', 1)[0]
                zip_file.writestr(f"{name_without_ext}_upscaled_{scale}x.png", img_buffer.read())
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=upscaled_batch_{scale}x.zip"}
        )
        
    except Exception as e:
        logger.error(f"Batch upscaling failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch upscaling failed: {str(e)}")


@router.post("/estimate-memory")
async def estimate_memory_usage(
    width: int = Form(...),
    height: int = Form(...),
    scale: float = Form(2.0),
    method: str = Form("realesrgan")
):
    """Estimate memory usage for upscaling operation"""
    if not upscaler_service:
        raise HTTPException(status_code=500, detail="Upscaler service not initialized")
    
    try:
        # Create dummy image for estimation
        dummy_image = Image.new("RGB", (width, height))
        
        estimate = upscaler_service.get_memory_usage_estimate(
            image=dummy_image,
            scale=scale,
            method=method
        )
        
        return estimate
        
    except Exception as e:
        logger.error(f"Memory estimation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Memory estimation failed: {str(e)}")


@router.get("/status")
async def get_upscaler_status():
    """Get upscaler service status"""
    if not upscaler_service or not model_loader:
        return {"status": "not_initialized"}
    
    available_models = model_loader.get_available_upscaler_models()
    methods = upscaler_service.get_available_methods()
    
    return {
        "status": "ready",
        "available_models": len(available_models),
        "available_methods": len(methods),
        "cuda_available": torch.cuda.is_available(),
        "device": model_loader.device if model_loader else "unknown"
    }