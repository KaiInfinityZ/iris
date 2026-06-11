"""
Configuration management for I.R.I.S.
"""
from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]

env_path = BASE_DIR / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

class Config:
    """Central configuration management"""
    
    # Paths
    BASE_DIR = BASE_DIR
    STATIC_DIR = BASE_DIR / "static"
    OUTPUTS_DIR = BASE_DIR / "outputs"
    LOGS_DIR = BASE_DIR / "Logs"
    CONFIG_DIR = STATIC_DIR / "config"
    DATA_DIR = STATIC_DIR / "data"
    
    # Server settings
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    
    # Discord settings
    DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
    DISCORD_BOT_ID = os.getenv("DISCORD_BOT_ID", "0")
    DISCORD_BOT_OWNER_ID = os.getenv("DISCORD_BOT_OWNER_ID", "0")
    
    DISCORD_CHANNEL_NEW_IMAGES = int(os.getenv("DISCORD_CHANNEL_NEW_IMAGES", "0"))
    DISCORD_CHANNEL_VARIATIONS = int(os.getenv("DISCORD_CHANNEL_VARIATIONS", "0"))
    DISCORD_CHANNEL_UPSCALED = int(os.getenv("DISCORD_CHANNEL_UPSCALED", "0"))
    
    # Model settings
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "anime")
    
    # Local model paths (all in project root for clean server deployment)
    MODELS_DIR = BASE_DIR / "models"
    
    # HuggingFace models (diffusion models)
    HUGGINGFACE_MODELS_PATH = os.getenv("HUGGINGFACE_MODELS_PATH", str(MODELS_DIR / "huggingface"))
    
    # RealESRGAN upscaler models
    REALESRGAN_MODELS_PATH = os.getenv("REALESRGAN_MODELS_PATH", str(MODELS_DIR / "realesrgan"))
    
    # SwinIR upscaler models
    SWINIR_MODELS_PATH = os.getenv("SWINIR_MODELS_PATH", str(MODELS_DIR / "swinir"))
    
    # HuggingFace cache (HF_HOME) - where models are downloaded to
    HF_HOME = os.getenv("HF_HOME", str(MODELS_DIR / "hf_cache"))
    
    # Upscaler configuration
    DEFAULT_UPSCALER = os.getenv("DEFAULT_UPSCALER", "realesrgan")  # Options: swinir, realesrgan, lanczos
    ENABLE_SWINIR = os.getenv("ENABLE_SWINIR", "true").lower() == "true"
    
    # Upscaler scale settings
    MIN_UPSCALE_FACTOR = int(os.getenv("MIN_UPSCALE_FACTOR", "2"))
    MAX_UPSCALE_FACTOR = int(os.getenv("MAX_UPSCALE_FACTOR", "16"))
    
    # DRAM Extension
    DRAM_EXTENSION_ENABLED = os.getenv("DRAM_EXTENSION_ENABLED", "false").lower() == "true"
    VRAM_THRESHOLD_GB = float(os.getenv("VRAM_THRESHOLD_GB", "6"))
    MAX_DRAM_GB = int(os.getenv("MAX_DRAM_GB", "16"))
    
    # ROCm-specific settings for AMD GPUs
    ROCM_OPTIMIZATION_LEVEL = int(os.getenv("ROCM_OPTIMIZATION_LEVEL", "1"))
    # 0 = disabled, 1 = standard, 2 = aggressive
    
    ROCM_FORCE_FLOAT32 = os.getenv("ROCM_FORCE_FLOAT32", "false").lower() == "true"
    # Force float32 precision for compatibility
    
    ROCM_SMI_PATH = os.getenv("ROCM_SMI_PATH", "rocm-smi")
    # Custom path to rocm-smi executable
    
    ROCM_DEVICE_ID = int(os.getenv("ROCM_DEVICE_ID", "0"))
    # Select specific AMD GPU in multi-GPU systems
    
    # DirectML optimization settings for upscalers
    DIRECTML_OPTIMIZATION_LEVEL = int(os.getenv("DIRECTML_OPTIMIZATION_LEVEL", "1"))
    # 0 = disabled, 1 = standard (default), 2 = aggressive with DRAM extension
    
    # Upscaler tile size configuration based on VRAM
    UPSCALER_TILE_SIZE_LOW_VRAM = int(os.getenv("UPSCALER_TILE_SIZE_LOW_VRAM", "400"))
    # Tile size for GPUs with < 6GB VRAM
    
    UPSCALER_TILE_SIZE_HIGH_VRAM = int(os.getenv("UPSCALER_TILE_SIZE_HIGH_VRAM", "0"))
    # Tile size for GPUs with >= 6GB VRAM (0 = no tiling)
    
    UPSCALER_VRAM_THRESHOLD_GB = float(os.getenv("UPSCALER_VRAM_THRESHOLD_GB", "6.0"))
    # VRAM threshold to switch between tile sizes
    
    # Performance tracking
    ENABLE_UPSCALER_METRICS = os.getenv("ENABLE_UPSCALER_METRICS", "true").lower() == "true"
    # Enable detailed performance metrics logging for upscaling operations
    
    @classmethod
    def read_config_file(cls, filename: str) -> Optional[str]:
        """Read configuration from a file in static/config folder"""
        filepath = cls.CONFIG_DIR / filename
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return None
                return content
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Warning: Error reading config file {filename}: {e}")
            return None
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist"""
        try:
            cls.STATIC_DIR.mkdir(exist_ok=True)
            cls.OUTPUTS_DIR.mkdir(exist_ok=True)
            cls.LOGS_DIR.mkdir(exist_ok=True)
            cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Warning: Error creating directories: {e}")

try:
    Config.ensure_directories()
except Exception as e:
    print(f"Warning: Failed to ensure directories: {e}")
