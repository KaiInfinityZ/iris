"""
Settings Routes - Application settings management
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import time
from pathlib import Path

from src.core.config import Config
from src.utils.logger import create_logger

logger = create_logger("SettingsRoutes")
router = APIRouter(prefix="/api", tags=["settings"])

# Settings file path
SETTINGS_FILE = Config.BASE_DIR / "settings.json"

# Settings cache
_settings_cache = None
_settings_cache_time = 0
SETTINGS_CACHE_TTL = 2.0


class SettingsRequest(BaseModel):
    dramEnabled: Optional[bool] = None
    defaultModel: Optional[str] = None
    defaultUpscaler: Optional[str] = None
    maxUpscaleFactor: Optional[int] = None


def load_settings_from_file():
    """Load settings from settings.json file"""
    global _settings_cache, _settings_cache_time
    
    current_time = time.time()
    if _settings_cache and (current_time - _settings_cache_time) < SETTINGS_CACHE_TTL:
        return _settings_cache
    
    default_settings = {
        "dramEnabled": True,
        "defaultModel": "No Model",
        "defaultUpscaler": "realesrgan",
        "maxUpscaleFactor": 16
    }
    
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                file_settings = json.load(f)
                default_settings.update(file_settings)
                logger.info("Settings loaded from file")
        else:
            logger.info("No settings file found, using defaults")
    except Exception as e:
        logger.warning(f"Could not load settings.json: {e}")
    
    _settings_cache = default_settings
    _settings_cache_time = current_time
    return default_settings


def save_settings_to_file(settings: dict):
    """Save settings to settings.json file"""
    global _settings_cache, _settings_cache_time
    
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        # Update cache
        _settings_cache = settings
        _settings_cache_time = time.time()
        
        logger.info("Settings saved to file")
        return True
    except Exception as e:
        logger.error(f"Could not save settings.json: {e}")
        return False


@router.get("/settings")
async def get_settings():
    """Get current application settings"""
    settings = load_settings_from_file()
    return settings


@router.post("/settings")
async def save_settings(request: SettingsRequest):
    """Save application settings"""
    current_settings = load_settings_from_file()
    
    # Update only provided fields
    if request.dramEnabled is not None:
        current_settings["dramEnabled"] = request.dramEnabled
    if request.defaultModel is not None:
        current_settings["defaultModel"] = request.defaultModel
    if request.defaultUpscaler is not None:
        current_settings["defaultUpscaler"] = request.defaultUpscaler
    if request.maxUpscaleFactor is not None:
        current_settings["maxUpscaleFactor"] = request.maxUpscaleFactor
    
    success = save_settings_to_file(current_settings)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save settings")
    
    return {
        "success": True,
        "message": "Settings saved successfully",
        "settings": current_settings
    }


@router.get("/prompts-history")
async def get_prompts_history_legacy(limit: int = 50):
    """Legacy endpoint for prompt history (redirects to history API)"""
    # Import here to avoid circular imports
    from ..services.history import generation_history
    
    items = generation_history.get_all(limit=limit)
    # Extract just prompts for compatibility
    prompts = []
    for item in items:
        if 'prompt' in item:
            prompts.append({
                'prompt': item['prompt'],
                'timestamp': item.get('timestamp', ''),
                'id': item.get('id', '')
            })
    return {"history": prompts}