"""
Admin Routes - Server management endpoints for Admin Panel
"""
import os
import sys
import torch
import time
from datetime import datetime
from collections import deque
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.services.pipeline import pipeline_service
from src.api.services.model_scanner import ModelScanner
from src.utils.logger import create_logger

logger = create_logger("AdminRoutes")
router = APIRouter(prefix="/api/admin", tags=["admin"])

# In-memory log storage (last 100 entries)
_log_buffer = deque(maxlen=100)
_server_start_time = time.time()


def add_log(level: str, message: str):
    """Add a log entry to the buffer"""
    _log_buffer.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message
    })


# Initialize with startup log
add_log("INFO", "Admin routes initialized")


@router.get("/logs")
async def get_logs(limit: int = 50):
    """Get recent server logs"""
    logs = list(_log_buffer)[-limit:]
    return {"logs": logs, "total": len(_log_buffer)}


@router.post("/clear-cache")
async def clear_cache():
    """Clear CUDA cache to free GPU memory"""
    try:
        if torch.cuda.is_available():
            # Get memory before
            before = torch.cuda.memory_allocated() / 1024**2
            
            # Clear cache
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            
            # Get memory after
            after = torch.cuda.memory_allocated() / 1024**2
            freed = before - after
            
            add_log("INFO", f"CUDA cache cleared. Freed {freed:.1f} MB")
            logger.info(f"CUDA cache cleared. Freed {freed:.1f} MB")
            
            return {
                "success": True,
                "message": f"Cache cleared. Freed {freed:.1f} MB",
                "memory_before_mb": round(before, 2),
                "memory_after_mb": round(after, 2),
                "freed_mb": round(freed, 2)
            }
        else:
            return {
                "success": False,
                "message": "CUDA not available"
            }
    except Exception as e:
        add_log("ERROR", f"Failed to clear cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/restart")
async def restart_server():
    """Signal server restart (handled by start.py)"""
    try:
        add_log("WARN", "Server restart requested via Admin Panel")
        logger.warning("Server restart requested via Admin Panel")
        
        # Write restart signal file that start.py can watch
        signal_file = os.path.join(os.path.dirname(__file__), "..", "..", "..", "restart_signal")
        with open(signal_file, "w") as f:
            f.write(str(time.time()))
        
        return {
            "success": True,
            "message": "Restart signal sent. Server will restart shortly."
        }
    except Exception as e:
        add_log("ERROR", f"Failed to send restart signal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_admin_stats():
    """Get detailed admin statistics"""
    uptime_seconds = time.time() - _server_start_time
    
    # Format uptime
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    if hours > 0:
        uptime_str = f"{hours}h {minutes}m"
    else:
        uptime_str = f"{minutes}m"
    
    stats = {
        "uptime": uptime_str,
        "uptime_seconds": round(uptime_seconds, 0),
        "model_loaded": pipeline_service.pipe is not None,
        "current_model": pipeline_service.current_model,
        "device": pipeline_service.device,
        "total_generations": getattr(pipeline_service, 'total_generations', 0),
        "log_count": len(_log_buffer)
    }
    
    # GPU stats
    if torch.cuda.is_available():
        stats["gpu_name"] = torch.cuda.get_device_name(0)
        stats["vram_total_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
        stats["vram_used_gb"] = round(torch.cuda.memory_allocated(0) / 1024**3, 2)
        stats["vram_reserved_gb"] = round(torch.cuda.memory_reserved(0) / 1024**3, 2)
    
    return stats


@router.post("/gc")
async def run_garbage_collection():
    """Run Python garbage collection"""
    import gc
    
    try:
        before = len(gc.get_objects())
        collected = gc.collect()
        after = len(gc.get_objects())
        
        add_log("INFO", f"GC collected {collected} objects")
        
        return {
            "success": True,
            "collected": collected,
            "objects_before": before,
            "objects_after": after
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unload-model")
async def unload_model():
    """Unload the current model to free memory"""
    try:
        if pipeline_service.pipe is not None:
            model_name = pipeline_service.current_model
            
            # Delete pipeline
            del pipeline_service.pipe
            pipeline_service.pipe = None
            pipeline_service.current_model = None
            
            # Clear CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            add_log("INFO", f"Model '{model_name}' unloaded")
            logger.info(f"Model '{model_name}' unloaded via Admin Panel")
            
            return {
                "success": True,
                "message": f"Model '{model_name}' unloaded successfully"
            }
        else:
            return {
                "success": False,
                "message": "No model currently loaded"
            }
    except Exception as e:
        add_log("ERROR", f"Failed to unload model: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Model Management Endpoints
# ============================================

class ModelEnableRequest(BaseModel):
    model_key: str
    enabled: bool


@router.get("/models/scan")
async def scan_models():
    """Scan local directory for models and update models.json"""
    try:
        found_models = ModelScanner.scan_local_models()
        success = ModelScanner.update_models_json(auto_discovered=True)
        
        if success:
            add_log("INFO", f"Model scan completed: {len(found_models)} models found")
            return {
                "success": True,
                "models_found": len(found_models),
                "models": [m["model_id"] for m in found_models]
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update models.json")
    except Exception as e:
        add_log("ERROR", f"Model scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/list")
async def list_models():
    """List all models with their enabled/disabled status"""
    try:
        import json
        from src.core.config import Config
        
        config_path = Config.CONFIG_DIR / "models.json"
        
        if not config_path.exists():
            return {"models": []}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        models = data.get("models", {})
        
        # Format for frontend
        model_list = []
        for key, config in models.items():
            model_list.append({
                "key": key,
                "id": config["id"],
                "description": config["description"],
                "tier": config["tier"],
                "vram_gb": config["vram_gb"],
                "enabled": not config.get("disabled", False),
                "model_type": config.get("model_type", "sd15"),
                "quality_stars": config.get("quality_stars", 3),
                "speed_stars": config.get("speed_stars", 3)
            })
        
        return {"models": model_list}
    except Exception as e:
        add_log("ERROR", f"Failed to list models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/enable")
async def enable_model(request: ModelEnableRequest):
    """Enable or disable a specific model"""
    try:
        success = ModelScanner.set_model_enabled(request.model_key, request.enabled)
        
        if success:
            status = "enabled" if request.enabled else "disabled"
            add_log("INFO", f"Model {request.model_key} {status}")
            return {
                "success": True,
                "message": f"Model {request.model_key} {status}"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Model {request.model_key} not found")
    except HTTPException:
        raise
    except Exception as e:
        add_log("ERROR", f"Failed to update model: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/models/{model_key}")
async def delete_model(model_key: str):
    """Delete a model from disk (use with caution!)"""
    try:
        import shutil
        from src.core.config import Config
        
        # First disable the model
        ModelScanner.set_model_enabled(model_key, False)
        
        # Find model directory
        models_path = Path(Config.HUGGINGFACE_MODELS_PATH)
        
        # Convert key back to directory name (e.g., ojimi_anime-kawai-diffusion -> models--Ojimi--anime-kawai-diffusion)
        parts = model_key.split("_")
        dir_name = f"models--{parts[0]}--{'_'.join(parts[1:])}"
        model_dir = models_path / dir_name
        
        if not model_dir.exists():
            raise HTTPException(status_code=404, detail=f"Model directory not found: {model_dir}")
        
        # Delete directory
        shutil.rmtree(model_dir)
        
        add_log("WARNING", f"Model {model_key} deleted from disk")
        logger.warning(f"Model {model_key} deleted from disk via Admin Panel")
        
        return {
            "success": True,
            "message": f"Model {model_key} deleted from disk"
        }
    except HTTPException:
        raise
    except Exception as e:
        add_log("ERROR", f"Failed to delete model: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
