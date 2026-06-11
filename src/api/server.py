"""
I.R.I.S. Server - Main FastAPI Application
Refactored modular architecture
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
import torch
import os
import gc
import json
import time
import io
import base64
import asyncio
import subprocess
import numpy as np
from datetime import datetime

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Services
from src.api.services.pipeline import pipeline_service, MODEL_CONFIGS
from src.api.services.history import generation_history
from src.api.services.queue import generation_queue

# Routes
from src.api.routes import system, gallery, queue, history, templates, admin, upscaler, settings

# Utils
from src.core.config import Config
from src.core.local_model_loader import LocalModelLoader
from src.core.memory_manager import clear_cache, get_memory_stats
from src.utils.logger import create_logger
from src.utils.file_manager import FileManager

# Exceptions
from src.core.exceptions import (
    IRISException,
    ModelLoadError,
    VRAMExhaustedError,
    GenerationError,
    QueueFullError,
    InvalidParameterError,
    ModelNotLoadedError
)

logger = create_logger("IRISServer")

# Paths
BASE_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = BASE_DIR / "assets"
STATIC_DIR = BASE_DIR / "static"
REACT_DIST_DIR = BASE_DIR / "frontend" / "dist"

# WebSocket clients
connected_clients = []
gallery_clients = []

# Stats
generation_stats = {
    "total_images": 0,
    "total_time": 0
}

# Settings Cache (reduces disk reads on frequent polling)
_settings_cache = None
_settings_cache_time = 0
SETTINGS_CACHE_TTL = 2.0  # Cache settings for 2 seconds

# Server start time for health check
_server_start_time = None

# Local model loader instance
local_model_loader = None

# Discord Bot Process (global for shutdown handling)
_discord_bot_process = None

# Bot Status File for communication
BOT_STATUS_FILE = BASE_DIR / "static" / "data" / "bot_status.json"

def update_bot_status_file(status: str, details: str = None):
    """Update bot status file for Discord bot to read"""
    try:
        BOT_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        status_data = {
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "total_generated": generation_stats["total_images"]
        }
        with open(BOT_STATUS_FILE, 'w') as f:
            json.dump(status_data, f)
    except Exception as e:
        logger.error(f"Failed to update bot status file: {e}")


def _patch_torchvision_compat():
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
        logger.info("Applied torchvision compatibility patch")


def _free_vram_for_upscaling():
    """Free VRAM by temporarily offloading the diffusion model
    
    This is crucial for low VRAM GPUs (4-6GB) where the diffusion model
    takes up most of the available memory.
    """
    import gc
    
    freed_mb = 0
    
    if not torch.cuda.is_available():
        return freed_mb
    
    try:
        # Get initial VRAM usage
        initial_allocated = torch.cuda.memory_allocated(0) / (1024**2)
        
        # Move diffusion pipeline to CPU if loaded
        if pipeline_service.pipe is not None:
            try:
                pipeline_service.pipe.to("cpu")
                logger.info("Moved diffusion pipeline to CPU for upscaling")
            except Exception as e:
                logger.warning(f"Could not move pipeline to CPU: {e}")
        
        if pipeline_service.img2img_pipe is not None:
            try:
                pipeline_service.img2img_pipe.to("cpu")
            except Exception:
                pass
        
        # Clear CUDA cache
        torch.cuda.empty_cache()
        gc.collect()
        
        # Calculate freed memory
        final_allocated = torch.cuda.memory_allocated(0) / (1024**2)
        freed_mb = initial_allocated - final_allocated
        
        if freed_mb > 100:
            logger.info(f"Freed {freed_mb:.0f}MB VRAM for upscaling")
        
    except Exception as e:
        logger.warning(f"VRAM cleanup failed: {e}")
    
    return freed_mb


def _restore_vram_after_upscaling():
    """Restore diffusion model to GPU after upscaling"""
    if not torch.cuda.is_available() or pipeline_service.device != "cuda":
        return
    
    try:
        if pipeline_service.pipe is not None:
            pipeline_service.pipe.to(pipeline_service.device)
            logger.info("Restored diffusion pipeline to GPU")
        
        if pipeline_service.img2img_pipe is not None:
            pipeline_service.img2img_pipe.to(pipeline_service.device)
            
    except Exception as e:
        logger.warning(f"Could not restore pipeline to GPU: {e}")


async def _load_upscaler(use_cpu: bool = False, tile_size: int = 256):
    """Load Real-ESRGAN upscaler
    
    Args:
        use_cpu: Force CPU mode (slower but no VRAM needed)
        tile_size: Tile size for processing (smaller = less VRAM, 0 = no tiling)
    """
    try:
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
        
        device = "cpu" if use_cpu else pipeline_service.device
        use_half = False if use_cpu else (pipeline_service.dtype == torch.float16)
        
        # Use the general x4plus model (more reliable URL)
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        pipeline_service.upscaler = RealESRGANer(
            scale=4,
            model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
            model=model,
            tile=tile_size,  # Tiling reduces VRAM usage significantly
            tile_pad=10,
            pre_pad=0,
            half=use_half,
            device=device
        )
        mode_str = "CPU" if use_cpu else f"CUDA (tile={tile_size})"
        logger.success(f"Real-ESRGAN upscaler loaded ({mode_str})")
    except Exception as e:
        logger.warning(f"Real-ESRGAN not available: {e}")
        pipeline_service.upscaler = None


async def _load_upscaler_anime_v3(use_cpu: bool = False, tile_size: int = 256):
    """Load Real-ESRGAN Anime v3 upscaler (faster, optimized for anime)
    
    Args:
        use_cpu: Force CPU mode (slower but no VRAM needed)
        tile_size: Tile size for processing (smaller = less VRAM, 0 = no tiling)
    """
    if hasattr(pipeline_service, 'upscaler_anime') and pipeline_service.upscaler_anime:
        return  # Already loaded
    try:
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
        
        device = "cpu" if use_cpu else pipeline_service.device
        use_half = False if use_cpu else (pipeline_service.dtype == torch.float16)
        
        # Anime v3 uses smaller model (6 blocks instead of 23)
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
        pipeline_service.upscaler_anime = RealESRGANer(
            scale=4,
            model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth',
            model=model,
            tile=tile_size,  # Tiling reduces VRAM usage
            tile_pad=10,
            pre_pad=0,
            half=use_half,
            device=device
        )
        mode_str = "CPU" if use_cpu else f"CUDA (tile={tile_size})"
        logger.success(f"Real-ESRGAN Anime v3 upscaler loaded ({mode_str})")
    except Exception as e:
        logger.warning(f"Anime v3 upscaler not available: {e}")
        pipeline_service.upscaler_anime = None


async def _load_upscaler_bsrgan(use_cpu: bool = False, tile_size: int = 256):
    """Load BSRGAN-style upscaler (optimized for compressed/degraded images)
    
    Uses Real-ESRGAN x4plus with tile-based processing for better handling
    of compression artifacts and degraded images.
    
    Args:
        use_cpu: Force CPU mode (slower but no VRAM needed)
        tile_size: Tile size for processing (smaller = less VRAM)
    """
    if hasattr(pipeline_service, 'upscaler_bsrgan') and pipeline_service.upscaler_bsrgan:
        return  # Already loaded
    try:
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer
        
        device = "cpu" if use_cpu else pipeline_service.device
        use_half = False if use_cpu else (pipeline_service.dtype == torch.float16)
        
        # Use Real-ESRGAN x4plus with tile processing for degraded images
        # Tiling helps with compression artifacts by processing smaller regions
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        pipeline_service.upscaler_bsrgan = RealESRGANer(
            scale=4,
            model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
            model=model,
            tile=tile_size if tile_size > 0 else 256,  # Smaller tiles = better for degraded images
            tile_pad=32,  # More padding for smoother transitions
            pre_pad=10,
            half=use_half,
            device=device
        )
        mode_str = "CPU" if use_cpu else f"CUDA (tile={tile_size})"
        logger.success(f"BSRGAN-style upscaler loaded ({mode_str})")
    except Exception as e:
        # Fallback: use same as Real-ESRGAN
        logger.warning(f"BSRGAN upscaler failed, using Real-ESRGAN as fallback: {e}")
        pipeline_service.upscaler_bsrgan = pipeline_service.upscaler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for FastAPI startup and shutdown"""
    global _server_start_time, local_model_loader
    _server_start_time = datetime.now()
    
    logger.info("Starting I.R.I.S. Server...")
    logger.info("=" * 70)
    
    try:
        # Apply torchvision compatibility patch for Real-ESRGAN
        _patch_torchvision_compat()
        
        # Initialize local model loader
        local_model_loader = LocalModelLoader()
        
        # Initialize upscaler routes with model loader
        from src.api.routes.upscaler import init_upscaler_routes
        init_upscaler_routes(local_model_loader)
        
        # Scan and load local models
        models = local_model_loader.scan_local_models()
        logger.info(f"Found {len(models['diffusion'])} diffusion models and {len(models['upscaler'])} upscaler models")
        
        # Load RealESRGAN models
        await local_model_loader.load_realesrgan_models()
        
        # Detect device and show system information
        logger.info("=" * 70)
        logger.info("SYSTEM INFORMATION")
        logger.info("=" * 70)
        
        # Show OS and Python version
        import platform
        import sys
        os_name = platform.system()
        if os_name == "Darwin":
            os_name = "macOS"
        logger.info(f"OS: {os_name} {platform.release()}")
        logger.info(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        logger.info(f"PyTorch: {torch.__version__}")
        
        # Show CPU information
        try:
            import psutil
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            ram = psutil.virtual_memory()
            logger.info(f"CPU: {cpu_count} cores @ {cpu_freq.current / 1000:.2f} GHz" if cpu_freq else f"CPU: {cpu_count} cores")
            logger.info(f"RAM: {ram.total / (1024**3):.1f} GB total, {ram.available / (1024**3):.1f} GB available")
        except ImportError:
            logger.warning("psutil not available - CPU/RAM info unavailable")
        
        # Detect device
        pipeline_service.detect_device()
        
        # Show GPU information
        device_str = str(pipeline_service.device)
        if "privateuseone" in device_str or "dml" in device_str.lower():
            # DirectML device
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
                    logger.info(f"GPU: {gpu_name} (DirectML)")
                    
                    # Try to get VRAM info from DirectML
                    try:
                        import torch_directml
                        # DirectML doesn't expose VRAM directly, estimate from system
                        logger.info(f"Compute Device: DirectML (privateuseone:0)")
                    except:
                        pass
            except:
                logger.info(f"GPU: DirectML device detected")
        elif device_str == "cuda":
            try:
                gpu_name = torch.cuda.get_device_name(0)
                vram_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                logger.info(f"GPU: {gpu_name}")
                logger.info(f"VRAM: {vram_total:.1f} GB")
            except:
                logger.info(f"GPU: CUDA device")
        elif device_str == "cpu":
            logger.info("GPU: None (CPU mode)")
        else:
            logger.info(f"Compute Device: {device_str}")
        
        logger.info(f"Precision: {pipeline_service.dtype}")
        logger.info("=" * 70)
        
        # Models will be loaded on-demand when generating images
        logger.info("Models will be loaded on-demand (lazy loading)")
        
        # Pre-load Real-ESRGAN upscaler (legacy support)
        await _load_upscaler()
        
        # Setup queue callback
        generation_queue.set_process_callback(process_queue_item)
        
        logger.info("=" * 70)
        logger.info("Server ready at http://localhost:8000")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        raise
    
    yield
    
    # Shutdown: Stop Discord bot if running
    global _discord_bot_process
    if _discord_bot_process is not None and _discord_bot_process.poll() is None:
        logger.info("Stopping Discord bot on shutdown...")
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(_discord_bot_process.pid)], 
                              capture_output=True, timeout=5)
            else:
                _discord_bot_process.kill()
                _discord_bot_process.wait(timeout=2)
            logger.success("Discord bot stopped")
        except Exception as e:
            logger.error(f"Error stopping Discord bot: {e}")
        finally:
            _discord_bot_process = None
    
    logger.info("Shutting down I.R.I.S. Server...")
    pipeline_service.cleanup()


# Create FastAPI app
app = FastAPI(
    title="I.R.I.S. API",
    version="1.2.0",
    description="Intelligent Rendering & Image Synthesis",
    lifespan=lifespan
)

# Rate Limiting
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from src.api.middleware.rate_limit import limiter, rate_limit_exceeded_handler
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    logger.success("Rate limiting enabled")
except ImportError:
    logger.warning("slowapi not installed - rate limiting disabled")

# Mount static directories
try:
    # Don't mount /assets here - will be handled by React asset serving
    # app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
    logger.success(f"Assets directory available: {ASSETS_DIR}")
except Exception as e:
    logger.warning(f"Assets directory issue: {e}")

try:
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.success(f"Static mounted: {STATIC_DIR}")
except Exception as e:
    logger.warning(f"Failed to mount static: {e}")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(system.router)
app.include_router(gallery.router)
app.include_router(queue.router)
app.include_router(history.router)
app.include_router(templates.router)
app.include_router(admin.router)
app.include_router(upscaler.router)
app.include_router(settings.router)


# ============ Exception Handlers ============

@app.exception_handler(IRISException)
async def iris_exception_handler(request: Request, exc: IRISException):
    """Handle all I.R.I.S. custom exceptions"""
    status_codes = {
        "vram_exhausted": 507,
        "model_load_error": 503,
        "model_not_loaded": 503,
        "queue_full": 429,
        "invalid_parameter": 400,
        "generation_error": 500
    }
    status_code = status_codes.get(exc.code, 500)
    return JSONResponse(status_code=status_code, content=exc.to_dict())


@app.exception_handler(VRAMExhaustedError)
async def vram_exception_handler(request: Request, exc: VRAMExhaustedError):
    """Handle VRAM exhaustion with cleanup"""
    # Use centralized memory cleanup
    clear_cache("cuda", synchronize=True)
    return JSONResponse(
        status_code=507,
        content={
            **exc.to_dict(),
            "suggestion": "Try reducing resolution or steps, or enable DRAM extension"
        }
    )


# ============ React Frontend Routes ============
# Serve React production build

# Check if React frontend should be served (controlled by IRIS_SERVE_REACT env var)
serve_react = os.environ.get("IRIS_SERVE_REACT", "0") == "1"

if serve_react and REACT_DIST_DIR.exists():
    logger.info(f"React frontend enabled, serving from {REACT_DIST_DIR}")
    
    # Serve assets - prioritize React assets, fallback to general assets
    @app.get("/assets/{asset_path:path}")
    async def serve_assets(asset_path: str):
        """Serve assets - React assets first, then general assets"""
        # Try React assets first
        react_asset = REACT_DIST_DIR / "assets" / asset_path
        if react_asset.exists():
            # Determine MIME type based on extension
            if asset_path.endswith('.js'):
                return FileResponse(react_asset, media_type="application/javascript")
            elif asset_path.endswith('.css'):
                return FileResponse(react_asset, media_type="text/css")
            elif asset_path.endswith('.ico'):
                return FileResponse(react_asset, media_type="image/x-icon")
            else:
                return FileResponse(react_asset)
        
        # Fallback to general assets
        general_asset = ASSETS_DIR / asset_path
        if general_asset.exists():
            if asset_path.endswith('.ico'):
                return FileResponse(general_asset, media_type="image/x-icon")
            else:
                return FileResponse(general_asset)
        
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Serve React app root
    @app.get("/")
    async def serve_react_root():
        """Serve React SPA root"""
        index_path = REACT_DIST_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="React build not found")
    
    # Serve React app for specific frontend routes (not catch-all)
    @app.get("/{path}")
    async def serve_react_pages(path: str):
        """Serve React SPA for frontend routes"""
        # Only serve React for known frontend routes
        frontend_routes = ['generate', 'gallery', 'upscaler', 'dashboard', 'settings', 'admin']
        
        if path in frontend_routes:
            index_path = REACT_DIST_DIR / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
        
        # For unknown routes, return 404
        raise HTTPException(status_code=404, detail="Not found")
elif serve_react and not REACT_DIST_DIR.exists():
    logger.warning(f"React build not found at {REACT_DIST_DIR}")
    logger.info("Run 'npm run build' in frontend/ to build React frontend")
    
    # Fallback: serve general assets only
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
else:
    logger.info("API-only mode - React frontend disabled")
    # In API-only mode, serve general assets only
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    favicon_path = ASSETS_DIR / "fav.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon not found")


# ============ Generation ============

def generate_filename(prefix: str, seed: int, steps: int = None) -> str:
    """Generate filename with metadata"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parts = [prefix, timestamp, str(seed)]
    if steps:
        parts.append(f"s{steps}")
    return "_".join(parts) + ".png"


async def process_queue_item(item) -> dict:
    """Process a single queue item"""
    return await generate_image_internal(
        prompt=item.prompt,
        negative_prompt=item.negative_prompt,
        width=item.width,
        height=item.height,
        steps=item.steps,
        cfg_scale=item.cfg_scale,
        seed=item.seed,
        style=item.style
    )


async def generate_image_internal(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 768,
    steps: int = None,
    cfg_scale: float = None,
    seed: int = -1,
    style: str = "anime_kawai",
    progress_callback=None
) -> dict:
    """Internal generation function with optional progress callback"""
    logger.info(f"generate_image_internal called with prompt: {prompt[:50]}...")
    
    # Lazy loading: Load model on-demand if not loaded or different model requested
    if pipeline_service.pipe is None or pipeline_service.current_model != style:
        logger.info(f"Loading model on-demand: {style}")
        try:
            await pipeline_service.load_model(style)
        except Exception as e:
            logger.error(f"Failed to load model {style}: {e}")
            raise ModelNotLoadedError(f"Failed to load model {style}: {e}")
    
    # Get model configuration for recommended parameters
    from src.api.services.pipeline import MODEL_CONFIGS
    # Use first available model as fallback if style not found
    fallback_model = next(iter(MODEL_CONFIGS.keys())) if MODEL_CONFIGS else None
    model_config = MODEL_CONFIGS.get(style, MODEL_CONFIGS.get(fallback_model) if fallback_model else {})
    
    # Apply recommended parameters if not specified by user
    if steps is None:
        steps = model_config["recommended_steps"]
        logger.info(f"Using recommended steps for {style}: {steps}")
    else:
        logger.info(f"User specified steps: {steps} (overriding recommended: {model_config['recommended_steps']})")
    
    if cfg_scale is None:
        cfg_scale = model_config["recommended_cfg"]
        logger.info(f"Using recommended CFG scale for {style}: {cfg_scale}")
    else:
        logger.info(f"User specified CFG scale: {cfg_scale} (overriding recommended: {model_config['recommended_cfg']})")
    
    # Parameter validation warnings
    parameter_warnings = []
    
    # Handle negative prompt based on model support
    # Only pass negative_prompt if model supports it AND field is non-empty
    supports_negative = model_config.get("supports_negative_prompt", True)
    effective_negative_prompt = negative_prompt if (supports_negative and negative_prompt) else ""
    
    if not supports_negative and negative_prompt:
        warning_msg = f"Model {style} does not support negative prompts. Ignoring negative_prompt."
        logger.warning(warning_msg)
        parameter_warnings.append(warning_msg)
    
    # Check if current model is FLUX
    is_flux = pipeline_service.current_model and "flux" in pipeline_service.current_model.lower()
    
    # Validate parameters for FLUX models (warn but don't adjust)
    if is_flux:
        logger.info("FLUX model detected - validating parameters")
        
        # Warn if steps > 50 for FLUX models
        if steps > 50:
            warning_msg = f"FLUX models work best with 4 steps. You specified {steps} steps, which may not improve quality and will be slower. Consider using 4 steps for optimal results."
            logger.warning(warning_msg)
            parameter_warnings.append(warning_msg)
        
        # Warn if cfg_scale > 2.0 for FLUX models
        if cfg_scale > 2.0:
            warning_msg = f"FLUX models work best with guidance_scale=1.0. You specified {cfg_scale}, which may produce suboptimal results. Consider using 1.0 for optimal results."
            logger.warning(warning_msg)
            parameter_warnings.append(warning_msg)
    
    # Update bot status - generating
    update_bot_status_file("generating", prompt[:50])
    
    # Validate parameters
    if width < 256 or width > 4096:
        raise InvalidParameterError("width", width, "Must be between 256 and 4096")
    if height < 256 or height > 4096:
        raise InvalidParameterError("height", height, "Must be between 256 and 4096")
    if steps < 1 or steps > 150:
        raise InvalidParameterError("steps", steps, "Must be between 1 and 150")
    if cfg_scale < 1 or cfg_scale > 30:
        raise InvalidParameterError("cfg_scale", cfg_scale, "Must be between 1 and 30")
    
    # VRAM pre-check and auto-adjustment
    vram_check = pipeline_service.check_vram_availability(width, height, steps)
    if not vram_check["can_generate"]:
        if vram_check.get("adjusted_params"):
            # Use adjusted parameters
            adj = vram_check["adjusted_params"]
            width, height, steps = adj["width"], adj["height"], adj["steps"]
            logger.warning(f"Auto-adjusted params due to VRAM: {width}x{height}, {steps} steps")
        else:
            raise VRAMExhaustedError(
                required_gb=vram_check.get("estimated_vram_gb", 0),
                available_gb=vram_check.get("available_vram_gb", 0)
            )
    else:
        # Still apply safe params (but not for FLUX)
        if not is_flux:
            width, height, steps = pipeline_service.get_safe_params(width, height, steps)
    
    # Prepare seed
    if seed is None or seed == -1:
        seed = np.random.randint(0, 2147483647)
    
    generator = torch.Generator(pipeline_service.device).manual_seed(seed)
    logger.info(f"Generator created with seed: {seed}")
    
    # Build prompt - handle negative prompt based on model support
    # For FLUX models, negative prompts are not supported
    # For SDXL, we always need a valid negative prompt string (not empty)
    if is_flux:
        # FLUX doesn't need prompt engineering
        full_prompt = prompt
        neg_prompt = None  # FLUX doesn't use negative prompts
    elif style == "pixel_art":
        full_prompt = f"pixel art, 16-bit style, {prompt}"
        neg_prompt = f"smooth, anti-aliased, {negative_prompt}" if negative_prompt else "smooth, anti-aliased"
    else:
        full_prompt = f"masterpiece, best quality, {prompt}"
        # Always provide a valid negative prompt for SDXL models to avoid None errors
        if model_config.get("model_type") == "sdxl":
            # SDXL requires a valid negative prompt
            neg_prompt = negative_prompt if negative_prompt else "lowres, bad anatomy, worst quality"
        elif supports_negative and not negative_prompt:
            neg_prompt = "lowres, bad anatomy, worst quality"
        elif not supports_negative:
            neg_prompt = None  # Model doesn't support negative prompts
        else:
            neg_prompt = negative_prompt
    
    start_time = time.time()
    logger.info(f"Starting generation: {width}x{height}, {steps} steps, cfg={cfg_scale}")
    
    if pipeline_service.device == "cuda":
        torch.cuda.empty_cache()
        logger.info("CUDA cache cleared")
    
    # Get the event loop BEFORE entering the thread executor
    main_loop = asyncio.get_event_loop()
    
    # Progress callback wrapper for diffusers
    def diffusers_callback(pipe, step_index, timestep, callback_kwargs):
        if progress_callback:
            progress = int((step_index + 1) / steps * 100)
            try:
                # Use the main loop reference captured before thread execution
                main_loop.call_soon_threadsafe(
                    lambda p=progress, s=step_index, ts=timestep: asyncio.ensure_future(
                        progress_callback({
                            "step": s + 1,
                            "total_steps": steps,
                            "progress": p,
                            "timestep": float(ts) if ts is not None else 0
                        }),
                        loop=main_loop
                    )
                )
            except Exception:
                pass  # Ignore callback errors
        return callback_kwargs
    
    try:
        # Run generation in thread pool to not block the event loop
        # Prepare kwargs with callback if supported
        pipe_kwargs = {
            "prompt": full_prompt,
            "num_inference_steps": steps,
            "guidance_scale": cfg_scale,
            "width": width,
            "height": height,
            "generator": generator
        }
        
        # Add negative_prompt only for non-FLUX models and when supported
        if not is_flux and neg_prompt is not None:
            pipe_kwargs["negative_prompt"] = neg_prompt
        
        # Add callback for progress updates (diffusers >= 0.25.0)
        if progress_callback:
            pipe_kwargs["callback_on_step_end"] = diffusers_callback
        
        logger.info("Calling pipeline.pipe()...")
        result = await main_loop.run_in_executor(
            None,
            lambda: pipeline_service.pipe(**pipe_kwargs)
        )
        logger.info("Pipeline completed successfully")
    except RuntimeError as e:
        logger.error(f"RuntimeError during generation: {e}")
        error_msg = str(e).lower()
        if "out of memory" in error_msg or "cuda" in error_msg:
            # Get VRAM info if available
            if torch.cuda.is_available():
                total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                used = torch.cuda.memory_allocated(0) / (1024**3)
                raise VRAMExhaustedError(required_gb=used + 2, available_gb=total - used)
            raise VRAMExhaustedError()
        raise GenerationError(reason=str(e), seed=seed)
    
    generation_time = time.time() - start_time
    image = result.images[0]
    
    # Save
    filename = generate_filename("gen", seed, steps)
    os.makedirs("outputs", exist_ok=True)
    image.save(f"outputs/{filename}")
    
    # Log to history
    generation_history.add(
        filename=filename,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        width=width,
        height=height,
        steps=steps,
        cfg_scale=cfg_scale,
        style=style,
        model=pipeline_service.current_model or "anime_kawai",
        generation_time=generation_time
    )
    
    # Update stats
    generation_stats["total_images"] += 1
    generation_stats["total_time"] += generation_time
    
    # Update bot status - back to idle
    update_bot_status_file("idle", f"Generated: {filename}")
    
    # Convert to base64
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    response = {
        "success": True,
        "image": f"data:image/png;base64,{img_str}",
        "seed": seed,
        "generation_time": round(generation_time, 2),
        "filename": filename,
        "width": width,
        "height": height
    }
    
    # Add parameter warnings to response metadata if any
    if parameter_warnings:
        response["warnings"] = parameter_warnings
    
    return response


# ============ WebSocket Generation ============

@app.websocket("/ws/generate")
async def websocket_generate(websocket: WebSocket):
    """WebSocket endpoint for real-time generation with progress updates"""
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info("WebSocket client connected")
    
    try:
        while True:
            logger.info("Waiting for WebSocket message...")
            data = await websocket.receive_text()
            logger.info(f"Received WebSocket message: {data[:100]}...")
            request_data = json.loads(data)
            
            await websocket.send_json({"type": "started", "message": "Generation started"})
            logger.info("Sent 'started' message to client")
            
            try:
                # Progress callback for real-time updates (both download and generation)
                async def send_progress(progress_data):
                    try:
                        # Determine message type based on progress_data
                        msg_type = progress_data.get('type', 'progress')
                        
                        # For download messages, send them directly
                        if msg_type in ['download_start', 'download_progress', 'download_complete', 'download_error', 'download_waiting']:
                            await websocket.send_json(progress_data)
                        else:
                            # For generation progress, wrap in progress type
                            await websocket.send_json({
                                "type": "progress",
                                **progress_data
                            })
                    except Exception:
                        pass  # Client may have disconnected
                
                # Load model if different from current (with download progress)
                # Normalize model ID: convert hyphens to underscores for backend compatibility
                requested_model = request_data.get("style", "anime_kawai").replace("-", "_")
                if pipeline_service.current_model != requested_model:
                    logger.info(f"Loading model {requested_model}...")
                    await pipeline_service.load_model(requested_model, progress_callback=send_progress)
                
                # Generate with progress callback
                logger.info("Starting generate_image_internal...")
                logger.info(f"Params: prompt={request_data.get('prompt', '')[:50]}, width={request_data.get('width')}, height={request_data.get('height')}, steps={request_data.get('steps')}")
                result = await generate_image_internal(
                    prompt=request_data.get("prompt", ""),
                    negative_prompt=request_data.get("negative_prompt", ""),
                    width=request_data.get("width", 512),
                    height=request_data.get("height", 768),
                    steps=request_data.get("steps"),
                    cfg_scale=request_data.get("cfg_scale"),
                    seed=request_data.get("seed", -1),
                    style=request_data.get("style", "anime_kawai"),
                    progress_callback=send_progress
                )
                
                await websocket.send_json({
                    "type": "completed",
                    **result
                })
                
                # Broadcast to gallery
                for client in gallery_clients:
                    try:
                        await client.send_json({
                            "status": "complete",
                            "filename": result["filename"]
                        })
                    except:
                        pass
                
            except Exception as e:
                import traceback
                logger.error(f"Generation error: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_msg = str(e)
                error_type = "generic"
                
                if "out of memory" in error_msg.lower():
                    error_type = "cuda_oom"
                    if pipeline_service.device == "cuda":
                        torch.cuda.empty_cache()
                
                await websocket.send_json({
                    "type": "error",
                    "error_type": error_type,
                    "message": error_msg
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


@app.websocket("/ws/gallery-progress")
async def websocket_gallery_progress(websocket: WebSocket):
    """WebSocket for gallery progress updates"""
    await websocket.accept()
    gallery_clients.append(websocket)
    
    try:
        while True:
            await websocket.receive_text()
            await asyncio.sleep(1)
    except:
        pass
    finally:
        if websocket in gallery_clients:
            gallery_clients.remove(websocket)


# ============ Legacy API Endpoints ============
# These maintain backward compatibility with existing frontend

from pydantic import BaseModel
from typing import Optional


class GenerationRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = ""
    style: str = "anime_kawai"
    seed: Optional[int] = -1
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    width: int = 512
    height: int = 768


# Try to import limiter for rate limiting
try:
    from src.api.middleware.rate_limit import limiter, RATE_LIMITS
    _has_rate_limit = True
except ImportError:
    _has_rate_limit = False


@app.post("/api/generate")
async def api_generate(request: GenerationRequest, req: Request):
    """REST API generation endpoint"""
    # Apply rate limit if available
    if _has_rate_limit:
        await limiter.check(RATE_LIMITS["generate"], req)
    
    try:
        result = await generate_image_internal(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            width=request.width,
            height=request.height,
            steps=request.steps,
            cfg_scale=request.cfg_scale,
            seed=request.seed,
            style=request.style
        )
        return result
    except (ModelNotLoadedError, VRAMExhaustedError, 
            InvalidParameterError, GenerationError) as e:
        # Custom exceptions are handled by exception handlers
        raise e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/prompts-history")
async def get_prompts_history(limit: int = 50):
    """Get prompt history from prompts_history.json"""
    try:
        history_file = BASE_DIR / "static" / "data" / "prompts_history.json"
        if not history_file.exists():
            return {"history": []}
        
        with open(history_file, 'r', encoding='utf-8') as f:
            all_history = json.load(f)
        
        # Deduplicate by prompt and get unique entries (most recent first)
        seen_prompts = set()
        unique_history = []
        
        # Reverse to get most recent first
        for entry in reversed(all_history):
            prompt = entry.get('prompt', '').strip()
            if prompt and prompt not in seen_prompts:
                seen_prompts.add(prompt)
                # Normalize the entry format
                settings = entry.get('settings', {})
                unique_history.append({
                    "prompt": prompt,
                    "negativePrompt": settings.get('negative_prompt', ''),
                    "seed": settings.get('seed'),
                    "steps": settings.get('steps'),
                    "cfg": settings.get('cfg_scale'),
                    "width": settings.get('width'),
                    "height": settings.get('height'),
                    "style": settings.get('style'),
                    "timestamp": entry.get('timestamp')
                })
                if len(unique_history) >= limit:
                    break
        
        return {"history": unique_history}
    except Exception as e:
        logger.error(f"Failed to load prompts history: {e}")
        return {"history": []}


@app.get("/api/stats")
async def get_stats():
    """Get generation statistics"""
    return {
        "total_images": generation_stats["total_images"],
        "total_time": round(generation_stats["total_time"], 2)
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring
    
    Returns server status, uptime, and component health.
    Useful for load balancers, monitoring tools, and debugging.
    """
    global _server_start_time
    
    # Calculate uptime
    uptime_seconds = 0
    uptime_str = "unknown"
    if _server_start_time:
        uptime_delta = datetime.now() - _server_start_time
        uptime_seconds = int(uptime_delta.total_seconds())
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        uptime_str = f"{hours}h {minutes}m {seconds}s"
    
    # Check component health
    model_loaded = pipeline_service.pipe is not None
    model_name = pipeline_service.current_model if model_loaded else None
    
    # GPU status
    gpu_available = torch.cuda.is_available()
    gpu_info = None
    if gpu_available:
        try:
            gpu_info = {
                "name": torch.cuda.get_device_name(0),
                "vram_total_gb": round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2),
                "vram_used_gb": round(torch.cuda.memory_allocated(0) / (1024**3), 2),
                "vram_free_gb": round((torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)) / (1024**3), 2)
            }
        except Exception:
            pass
    
    # Upscaler status
    upscaler_loaded = pipeline_service.upscaler is not None
    
    # Queue status
    queue_size = len(generation_queue.queue) if hasattr(generation_queue, 'queue') else 0
    
    # Overall health status
    is_healthy = model_loaded and (gpu_available or pipeline_service.device == "cpu")
    
    return {
        "status": "healthy" if is_healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "components": {
            "model": {
                "loaded": model_loaded,
                "name": model_name,
                "device": pipeline_service.device
            },
            "gpu": {
                "available": gpu_available,
                "info": gpu_info
            },
            "upscaler": {
                "loaded": upscaler_loaded
            },
            "queue": {
                "size": queue_size,
                "processing": generation_queue.is_processing if hasattr(generation_queue, 'is_processing') else False
            }
        },
        "stats": {
            "total_generations": generation_stats["total_images"],
            "total_generation_time": round(generation_stats["total_time"], 2)
        }
    }


# ============ Settings API ============

# Settings storage (in-memory, persisted to file)
SETTINGS_FILE = BASE_DIR / "settings.json"
app_settings = {
    "dramEnabled": False,
    "vramThreshold": 6,
    "maxDram": 16,
    "discordEnabled": False
}

def load_settings_from_file():
    """Load settings from file on startup"""
    global app_settings
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r') as f:
                app_settings.update(json.load(f))
            logger.info("Settings loaded from file")
    except Exception as e:
        logger.warning(f"Could not load settings: {e}")

def save_settings_to_file():
    """Save settings to file"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(app_settings, f, indent=2)
        logger.info("Settings saved to file")
    except Exception as e:
        logger.warning(f"Could not save settings: {e}")

# Load settings on module import
load_settings_from_file()


class SettingsRequest(BaseModel):
    dramEnabled: Optional[bool] = False
    vramThreshold: Optional[int] = 6
    maxDram: Optional[int] = 16
    discordEnabled: Optional[bool] = False


@app.get("/api/settings")
async def get_settings():
    """Get current application settings (cached for performance)"""
    global _settings_cache, _settings_cache_time
    
    current_time = time.time()
    
    # Return cached settings if still valid
    if _settings_cache is not None and (current_time - _settings_cache_time) < SETTINGS_CACHE_TTL:
        return _settings_cache
    
    # Build fresh response and cache it
    _settings_cache = {
        "success": True,
        "settings": app_settings
    }
    _settings_cache_time = current_time
    
    return _settings_cache


@app.post("/api/settings")
async def save_settings(request: SettingsRequest):
    """Save application settings"""
    global app_settings, _settings_cache
    
    # Invalidate cache
    _settings_cache = None
    
    # Check if Discord setting changed
    discord_changed = app_settings.get("discordEnabled") != request.discordEnabled
    
    app_settings.update({
        "dramEnabled": request.dramEnabled,
        "vramThreshold": request.vramThreshold,
        "maxDram": request.maxDram,
        "discordEnabled": request.discordEnabled
    })
    
    # Apply DRAM extension setting to pipeline
    if request.dramEnabled:
        pipeline_service.dram_config["enabled"] = True
        pipeline_service.dram_config["vram_threshold_gb"] = request.vramThreshold
        pipeline_service.dram_config["max_dram_gb"] = request.maxDram
        logger.info(f"DRAM extension enabled (threshold: {request.vramThreshold}GB, max: {request.maxDram}GB)")
    else:
        pipeline_service.dram_config["enabled"] = False
    
    # Apply Discord Bot setting - start/stop bot when setting changes
    if discord_changed:
        discord_result = await handle_discord_bot(request.discordEnabled)
        logger.info(f"Discord bot: {'Starting' if request.discordEnabled else 'Stopping'} - {discord_result.get('message', '')}")
    
    # Save to file
    save_settings_to_file()
    
    return {
        "success": True,
        "message": "Settings saved successfully"
    }


# Discord Bot Process Management
# Note: _discord_bot_process is defined at module level for shutdown handling

async def handle_discord_bot(enabled: bool):
    """Start or stop the Discord bot based on settings"""
    global _discord_bot_process
    
    if enabled:
        # Check if bot is already running
        if _discord_bot_process is not None and _discord_bot_process.poll() is None:
            logger.info("Discord bot is already running")
            return {"success": True, "message": "Bot already running"}
        
        # Check if bot token is configured
        bot_token = os.getenv('DISCORD_BOT_TOKEN')
        logger.info(f"Discord bot token from env: {'Found' if bot_token else 'Not found'}")
        
        if not bot_token:
            token_file = BASE_DIR / "static" / "config" / "bot_token.txt"
            if token_file.exists():
                with open(token_file, 'r') as f:
                    bot_token = f.read().strip()
                logger.info("Discord bot token loaded from file")
        
        if not bot_token:
            logger.warning("Discord bot token not configured - bot cannot start")
            return {"success": False, "message": "Bot token not configured"}
        
        # Start the bot in a subprocess
        try:
            import sys
            bot_script = BASE_DIR / "src" / "services" / "bot.py"
            logger.info(f"Starting Discord bot from: {bot_script}")
            
            if not bot_script.exists():
                logger.error(f"Bot script not found: {bot_script}")
                return {"success": False, "message": "Bot script not found"}
            
            # Start bot in same terminal (output visible), but in new process group
            # so Ctrl+C doesn't propagate to it
            if os.name == 'nt':
                _discord_bot_process = subprocess.Popen(
                    [sys.executable, str(bot_script)],
                    cwd=str(BASE_DIR),
                    stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                _discord_bot_process = subprocess.Popen(
                    [sys.executable, str(bot_script)],
                    cwd=str(BASE_DIR),
                    stdin=subprocess.DEVNULL,
                    start_new_session=True
                )
            
            logger.success(f"Discord bot started (PID: {_discord_bot_process.pid})")
            return {"success": True, "message": "Bot started", "pid": _discord_bot_process.pid}
        except Exception as e:
            logger.error(f"Failed to start Discord bot: {e}")
            return {"success": False, "message": str(e)}
    else:
        # Force stop the bot immediately
        if _discord_bot_process is not None:
            pid = _discord_bot_process.pid
            logger.info(f"Force stopping Discord bot (PID: {pid})...")
            try:
                if os.name == 'nt':
                    # Windows: Force kill immediately with taskkill /F /T
                    # /F = Force, /T = Kill child processes too
                    import subprocess
                    result = subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(pid)], 
                        capture_output=True, 
                        timeout=3
                    )
                    if result.returncode != 0:
                        # Fallback: try terminate then kill
                        _discord_bot_process.terminate()
                        try:
                            _discord_bot_process.wait(timeout=1)
                        except:
                            _discord_bot_process.kill()
                else:
                    # Unix: SIGKILL (immediate, no cleanup)
                    import signal
                    os.kill(pid, signal.SIGKILL)
                    _discord_bot_process.wait(timeout=2)
                logger.success(f"Discord bot force stopped (PID: {pid})")
            except Exception as e:
                logger.error(f"Error stopping Discord bot: {e}")
                # Last resort: try to kill anyway
                try:
                    _discord_bot_process.kill()
                except:
                    pass
            finally:
                _discord_bot_process = None
        return {"success": True, "message": "Bot stopped"}


class DiscordBotRequest(BaseModel):
    enabled: bool


@app.post("/api/discord-bot")
async def control_discord_bot(request: DiscordBotRequest):
    """Start or stop the Discord bot"""
    result = await handle_discord_bot(request.enabled)
    
    # Update settings
    app_settings["discordEnabled"] = request.enabled
    save_settings_to_file()
    
    return result


@app.get("/api/discord-bot/status")
async def get_discord_bot_status():
    """Get Discord bot status"""
    global _discord_bot_process
    
    if _discord_bot_process is None:
        return {"running": False, "status": "stopped"}
    
    poll_result = _discord_bot_process.poll()
    if poll_result is None:
        return {"running": True, "status": "running", "pid": _discord_bot_process.pid}
    else:
        _discord_bot_process = None
        return {"running": False, "status": "stopped", "exit_code": poll_result}


@app.get("/api/vram-status")
async def get_vram_status():
    """Get current VRAM status and availability"""
    return pipeline_service.get_vram_status()


@app.post("/api/vram-check")
async def check_vram_for_generation(width: int = 512, height: int = 768, steps: int = 35):
    """Pre-check if generation parameters will fit in VRAM"""
    return pipeline_service.check_vram_availability(width, height, steps)


# ============ Variation API ============

class VariationRequest(BaseModel):
    filename: str
    strength: Optional[float] = 0.5  # 0.0 = identical, 1.0 = completely different
    steps: Optional[int] = 35
    cfg_scale: Optional[float] = 7.0
    seed: Optional[int] = -1  # -1 = random


@app.post("/api/variation")
async def create_variation(request: VariationRequest):
    """Create a variation of an existing image using img2img
    
    Uses the original image as a starting point and applies noise based on strength.
    Lower strength = closer to original, higher strength = more different.
    """
    from PIL import Image
    
    # Find the image
    image_path = Path("outputs") / request.filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Lazy loading: Load default model if not loaded
    if pipeline_service.pipe is None:
        logger.info("Loading default model on-demand for variation")
        try:
            await pipeline_service.load_model("anime_kawai")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise ModelNotLoadedError(f"Failed to load model: {e}")
    
    try:
        # Load original image
        init_image = Image.open(image_path).convert("RGB")
        width, height = init_image.size
        
        # Prepare seed
        seed = request.seed
        if seed is None or seed == -1:
            seed = np.random.randint(0, 2147483647)
        
        generator = torch.Generator(pipeline_service.device).manual_seed(seed)
        
        # Try to get original prompt from history
        original_prompt = "masterpiece, best quality"
        original_negative = "lowres, bad anatomy, worst quality"
        
        # Look up in generation history
        history_file = BASE_DIR / "static" / "data" / "generation_history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    for entry in history:
                        if entry.get("filename") == request.filename:
                            original_prompt = f"masterpiece, best quality, {entry.get('prompt', '')}"
                            original_negative = entry.get('negative_prompt', original_negative)
                            break
            except:
                pass
        
        start_time = time.time()
        
        if pipeline_service.device == "cuda":
            torch.cuda.empty_cache()
        
        # Check if pipeline supports img2img
        # For standard diffusers pipelines, we need to use the img2img variant
        try:
            from diffusers import StableDiffusionImg2ImgPipeline, AutoPipelineForImage2Image
            
            # Try to create img2img pipeline from existing components
            img2img_pipe = AutoPipelineForImage2Image.from_pipe(pipeline_service.pipe)
            
            result = img2img_pipe(
                prompt=original_prompt,
                negative_prompt=original_negative,
                image=init_image,
                strength=request.strength,
                num_inference_steps=request.steps,
                guidance_scale=request.cfg_scale,
                generator=generator
            )
            
        except Exception as e:
            logger.warning(f"AutoPipeline failed, trying manual img2img: {e}")
            # Fallback: Use noise injection method
            # This works with any text2img pipeline
            
            from diffusers import DDIMScheduler
            import torch.nn.functional as F
            
            # Encode the image to latent space
            with torch.no_grad():
                # Resize to match VAE requirements
                target_size = (height // 8 * 8, width // 8 * 8)
                init_image_resized = init_image.resize((target_size[1], target_size[0]), Image.Resampling.LANCZOS)
                
                # Convert to tensor
                init_tensor = torch.from_numpy(np.array(init_image_resized)).float() / 255.0
                init_tensor = init_tensor.permute(2, 0, 1).unsqueeze(0)
                init_tensor = init_tensor.to(pipeline_service.device)
                init_tensor = 2.0 * init_tensor - 1.0  # Normalize to [-1, 1]
                
                # Encode to latent
                latents = pipeline_service.pipe.vae.encode(init_tensor).latent_dist.sample()
                latents = latents * pipeline_service.pipe.vae.config.scaling_factor
                
                # Add noise based on strength
                noise = torch.randn_like(latents, generator=generator)
                
                # Calculate timestep from strength
                num_inference_steps = request.steps
                timestep_start = int(num_inference_steps * request.strength)
                
                # Use scheduler to add noise
                scheduler = pipeline_service.pipe.scheduler
                scheduler.set_timesteps(num_inference_steps)
                timesteps = scheduler.timesteps[timestep_start:]
                
                if len(timesteps) > 0:
                    noisy_latents = scheduler.add_noise(latents, noise, timesteps[:1])
                else:
                    noisy_latents = latents
            
            # Generate with noisy latents
            result = pipeline_service.pipe(
                prompt=original_prompt,
                negative_prompt=original_negative,
                num_inference_steps=request.steps,
                guidance_scale=request.cfg_scale,
                generator=generator,
                latents=noisy_latents if request.strength > 0 else None,
                width=width,
                height=height
            )
        
        generation_time = time.time() - start_time
        image = result.images[0]
        
        # Generate filename with var_ prefix
        filename = generate_filename("var", seed, request.steps)
        image.save(f"outputs/{filename}")
        
        logger.info(f"Created variation of {request.filename} -> {filename} (strength: {request.strength}, {generation_time:.1f}s)")
        
        # Convert to base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return {
            "success": True,
            "image": f"data:image/png;base64,{img_str}",
            "filename": filename,
            "seed": seed,
            "strength": request.strength,
            "generation_time": round(generation_time, 2),
            "original": request.filename
        }
        
    except Exception as e:
        logger.error(f"Variation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Upscale API ============

class UpscaleRequest(BaseModel):
    filename: str
    scale: Optional[int] = 2
    method: Optional[str] = "realesrgan"


@app.post("/api/upscale")
async def upscale_image(request: UpscaleRequest):
    """Upscale an image using various methods with smart VRAM management
    
    Features:
    - Automatic VRAM cleanup before upscaling (moves diffusion model to CPU)
    - Tiled processing for lower VRAM usage
    - CPU fallback if CUDA OOM occurs
    - Automatic restoration of diffusion model after upscaling
    """
    from PIL import Image
    import cv2
    
    # Validate scale
    if request.scale not in [2, 4, 8]:
        raise HTTPException(status_code=400, detail="Scale must be 2, 4, or 8")
    
    # Find the image
    image_path = Path("outputs") / request.filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    vram_freed = False
    
    try:
        # Load image
        img = Image.open(image_path)
        original_size = img.size
        
        # Upscale based on method
        method = request.method.lower()
        
        if method == "lanczos":
            # Simple Lanczos upscaling (always available, no GPU needed)
            new_width = img.width * request.scale
            new_height = img.height * request.scale
            upscaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            used_method = "lanczos"
            
        elif method == "realesrgan":
            upscaled, used_method = await _upscale_with_smart_vram(
                img, request.scale, "realesrgan", _load_upscaler, 
                lambda: pipeline_service.upscaler
            )
            vram_freed = True
                
        elif method == "anime_v3":
            upscaled, used_method = await _upscale_with_smart_vram(
                img, request.scale, "anime_v3", _load_upscaler_anime_v3,
                lambda: pipeline_service.upscaler_anime
            )
            vram_freed = True
                
        elif method == "bsrgan":
            upscaled, used_method = await _upscale_with_smart_vram(
                img, request.scale, "bsrgan", _load_upscaler_bsrgan,
                lambda: pipeline_service.upscaler_bsrgan
            )
            vram_freed = True
                
        else:
            # Default to Lanczos
            new_width = img.width * request.scale
            new_height = img.height * request.scale
            upscaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            used_method = "lanczos"
        
        # Generate new filename
        base_name = request.filename.rsplit('.', 1)[0]
        new_filename = f"up{request.scale}x_{base_name}.png"
        new_path = Path("outputs") / new_filename
        
        # Save upscaled image
        upscaled.save(new_path, "PNG")
        
        # Convert to base64 for response
        buffered = io.BytesIO()
        upscaled.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        logger.info(f"Upscaled {request.filename} from {original_size} to {upscaled.size} using {used_method}")
        
        return {
            "success": True,
            "image": f"data:image/png;base64,{img_str}",
            "filename": new_filename,
            "method": used_method,
            "original_size": list(original_size),
            "new_size": list(upscaled.size)
        }
        
    except Exception as e:
        logger.error(f"Upscale failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Always restore diffusion model to GPU after upscaling
        if vram_freed:
            _restore_vram_after_upscaling()


async def _upscale_with_smart_vram(img, scale: int, method_name: str, loader_func, get_upscaler_func):
    """Smart upscaling with VRAM management and fallbacks
    
    Strategy:
    1. Try WITHOUT tiling first (tile=0) for best quality
    2. If OOM: Try with large tiles (512px)
    3. If still OOM: Free VRAM and retry with medium tiles (256px)
    4. If still OOM: Use CPU mode
    5. If all fails: Fall back to Lanczos
    """
    import cv2
    from PIL import Image
    
    # Handle alpha channel - convert RGBA to RGB
    if img.mode == 'RGBA':
        logger.debug("Converting RGBA to RGB for upscaling")
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != 'RGB':
        logger.debug(f"Converting {img.mode} to RGB for upscaling")
        img = img.convert('RGB')
    
    img_array = np.array(img)
    
    # Validate input
    if len(img_array.shape) != 3 or img_array.shape[2] != 3:
        raise ValueError(f"Expected RGB image with 3 channels, got shape {img_array.shape}")
    
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    
    # Strategy 1: Try WITHOUT tiling (best quality, no tile artifacts)
    try:
        # ALWAYS reload upscaler with tile=0 for best quality
        await loader_func(use_cpu=False, tile_size=0)  # tile=0 means no tiling
        upscaler = get_upscaler_func()
        
        if upscaler:
            logger.info(f"Attempting {method_name} without tiling (best quality)...")
            output, _ = upscaler.enhance(img_array, outscale=scale)
            output = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
            return Image.fromarray(output), method_name
            
    except RuntimeError as e:
        if "out of memory" in str(e).lower() or "CUDA" in str(e):
            logger.warning(f"{method_name} OOM without tiling, trying with large tiles...")
        else:
            raise
    
    # Strategy 2: Try with large tiles (512px) - reduces tile artifacts
    try:
        await loader_func(use_cpu=False, tile_size=512)
        upscaler = get_upscaler_func()
        
        if upscaler:
            logger.info(f"Attempting {method_name} with 512px tiles...")
            output, _ = upscaler.enhance(img_array, outscale=scale)
            output = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
            return Image.fromarray(output), method_name
            
    except RuntimeError as e:
        if "out of memory" in str(e).lower() or "CUDA" in str(e):
            logger.warning(f"{method_name} OOM with 512px tiles, trying with VRAM cleanup...")
        else:
            raise
    
    # Strategy 3: Free VRAM and retry with medium tiles (256px)
    try:
        _free_vram_for_upscaling()
        
        # Reload upscaler with medium tiles
        await loader_func(use_cpu=False, tile_size=256)
        upscaler = get_upscaler_func()
        
        if upscaler:
            logger.info(f"Attempting {method_name} with 256px tiles after VRAM cleanup...")
            output, _ = upscaler.enhance(img_array, outscale=scale)
            output = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
            return Image.fromarray(output), method_name
            
    except RuntimeError as e:
        if "out of memory" in str(e).lower() or "CUDA" in str(e):
            logger.warning(f"{method_name} still OOM, trying CPU mode...")
        else:
            raise
    
    # Strategy 4: Use CPU mode (slower but guaranteed to work)
    try:
        await loader_func(use_cpu=True, tile_size=0)
        upscaler = get_upscaler_func()
        
        if upscaler:
            logger.info(f"Using CPU mode for {method_name} (this may take a while)...")
            output, _ = upscaler.enhance(img_array, outscale=scale)
            output = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
            return Image.fromarray(output), f"{method_name}_cpu"
            
    except Exception as e:
        logger.warning(f"{method_name} CPU mode failed: {e}")
    
    # Strategy 5: Fall back to Lanczos
    logger.warning(f"All {method_name} attempts failed, using Lanczos fallback")
    new_width = img.width * scale
    new_height = img.height * scale
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS), "lanczos"


def _has_black_artifacts_server(img_array: np.ndarray, threshold: float = 0.3) -> bool:
    """
    Detect black rectangular artifacts in upscaled image.
    
    Args:
        img_array: Image array (H, W, C) with values 0-255
        threshold: Fraction of black pixels to consider as artifact (0.0-1.0)
    
    Returns:
        True if significant black artifacts detected
    """
    import cv2
    
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


# ============ Server Control ============

@app.post("/api/server/restart")
async def restart_server():
    """Trigger server restart by touching a file (for uvicorn --reload)"""
    import asyncio
    
    # Update bot status
    update_bot_status_file("restarting")
    
    logger.info("Server restart requested...")
    
    # Touch this file to trigger uvicorn reload
    async def do_restart():
        await asyncio.sleep(0.5)  # Give time for response to be sent
        # Touch server.py to trigger reload
        Path(__file__).touch()
    
    asyncio.create_task(do_restart())
    
    return {"success": True, "message": "Server restarting..."}


# ============ Admin Endpoints ============

@app.get("/api/admin/logs")
async def get_admin_logs():
    """Get recent server logs for admin panel"""
    logs = []
    
    # Try to read from log file if exists
    log_file = BASE_DIR / "Logs" / "server.log"
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-100:]  # Last 100 lines
                for line in lines:
                    # Parse log line format: "HH:MM:SS LEVEL message"
                    parts = line.strip().split(' ', 2)
                    if len(parts) >= 3:
                        logs.append({
                            "time": parts[0],
                            "level": parts[1].replace('✓', 'INFO').replace('✗', 'ERROR').replace('⚠', 'WARN'),
                            "message": parts[2] if len(parts) > 2 else ""
                        })
        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
    
    # If no log file, return recent in-memory logs
    if not logs:
        logs = [
            {"time": time.strftime("%H:%M:%S"), "level": "INFO", "message": "Server is running"},
            {"time": time.strftime("%H:%M:%S"), "level": "INFO", "message": f"Model: {pipeline_service.current_model or 'anime_kawai'}"},
            {"time": time.strftime("%H:%M:%S"), "level": "INFO", "message": f"Device: {pipeline_service.device}"},
        ]
    
    return {"logs": logs}


@app.post("/api/admin/clear-cache")
async def clear_cache():
    """Clear CUDA cache and other caches"""
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            logger.info("CUDA cache cleared by admin")
        
        # Clear settings cache
        global _settings_cache, _settings_cache_time
        _settings_cache = None
        _settings_cache_time = 0
        
        return {"success": True, "message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return {"success": False, "message": str(e)}


@app.post("/api/admin/restart")
async def admin_restart():
    """Admin restart endpoint - same as server restart"""
    return await restart_server()


@app.get("/api/admin/system")
async def get_admin_system_info():
    """Get detailed system information for admin panel"""
    import platform
    
    info = {
        "python_version": platform.python_version(),
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    
    # GPU info
    if torch.cuda.is_available():
        info["gpu"] = {
            "name": torch.cuda.get_device_name(0),
            "vram_total": f"{torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB",
            "vram_used": f"{torch.cuda.memory_allocated(0) / (1024**3):.2f} GB",
            "vram_free": f"{(torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)) / (1024**3):.2f} GB",
            "cuda_version": torch.version.cuda,
        }
    
    # Model info
    info["model"] = {
        "current": pipeline_service.current_model or "anime_kawai",
        "device": pipeline_service.device,
        "loaded": pipeline_service.pipe is not None,
    }
    
    # Stats
    info["stats"] = generation_stats
    
    return info


@app.get("/api/gpu-info")
async def get_gpu_info():
    """Get detailed GPU and system information for dashboard"""
    import psutil
    
    gpu_data = {
        "gpu_name": "Unknown",
        "gpu_utilization": 0,
        "gpu_temp": 0,
        "vram_used": 0,
        "vram_total": 0,
        "vram_free": 0,
        "power_draw": 0,
        "cpu_percent": 0,
        "cpu_freq": 0,
        "cpu_cores": 0,
        "ram_used": 0,
        "ram_total": 0,
        "ram_percent": 0,
    }
    
    # CPU info
    try:
        gpu_data["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        gpu_data["cpu_cores"] = psutil.cpu_count(logical=False) or psutil.cpu_count()
        freq = psutil.cpu_freq()
        if freq:
            gpu_data["cpu_freq"] = freq.current / 1000  # Convert to GHz
    except Exception:
        pass
    
    # RAM info
    try:
        mem = psutil.virtual_memory()
        gpu_data["ram_total"] = mem.total / (1024**3)
        gpu_data["ram_used"] = mem.used / (1024**3)
        gpu_data["ram_percent"] = mem.percent
    except Exception:
        pass
    
    # GPU info via PyTorch
    if torch.cuda.is_available():
        try:
            gpu_data["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            gpu_data["vram_total"] = props.total_memory / (1024**3)
            gpu_data["vram_used"] = torch.cuda.memory_allocated(0) / (1024**3)
            gpu_data["vram_free"] = gpu_data["vram_total"] - gpu_data["vram_used"]
        except Exception:
            pass
    
    # Try to get GPU utilization and temp via nvidia-smi (Windows/Linux)
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,temperature.gpu,power.draw', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            if len(parts) >= 3:
                gpu_data["gpu_utilization"] = float(parts[0].strip())
                gpu_data["gpu_temp"] = float(parts[1].strip())
                gpu_data["power_draw"] = float(parts[2].strip())
    except Exception:
        pass
    
    return {"gpu": gpu_data}
