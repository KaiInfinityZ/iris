"""
System Routes - Health, GPU info, version endpoints
"""
import subprocess
import time
import torch
from fastapi import APIRouter

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from src.api.services.pipeline import pipeline_service, MODEL_CONFIGS
from src.utils.logger import create_logger
from src.core.config import Config

logger = create_logger("SystemRoutes")
router = APIRouter(prefix="/api", tags=["system"])

# Track server start time for uptime
_server_start_time = time.time()
_total_generations = 0
_total_generation_time = 0.0


def _query_rocm_smi() -> dict:
    """
    Query AMD GPU metrics using rocm-smi.
    
    Returns:
        dict with temperature, power_draw, utilization, vram_used, vram_total
        or None if rocm-smi unavailable
    """
    try:
        # Get rocm-smi path from config
        rocm_smi_path = getattr(Config, 'ROCM_SMI_PATH', 'rocm-smi')
        
        # Query rocm-smi for GPU metrics
        result = subprocess.run(
            [rocm_smi_path, '--showtemp', '--showuse', '--showmeminfo', 'vram', '--showpower'],
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode != 0:
            logger.warning(f"rocm-smi returned non-zero exit code: {result.returncode}")
            return None
        
        # Parse the output
        return _parse_rocm_smi_output(result.stdout)
        
    except FileNotFoundError:
        logger.debug(f"rocm-smi not found at '{rocm_smi_path}' (expected on Windows/DirectML)")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("rocm-smi command timed out")
        return None
    except Exception as e:
        logger.warning(f"Error querying rocm-smi: {e}")
        return None


def _parse_rocm_smi_output(output: str) -> dict:
    """
    Parse rocm-smi command output.
    
    Args:
        output: Raw rocm-smi output string
    
    Returns:
        Parsed metrics dictionary
    """
    metrics = {
        "temperature_c": 0.0,
        "power_draw_w": 0.0,
        "utilization_percent": 0,
        "vram_used_gb": 0.0,
        "vram_total_gb": 0.0
    }
    
    try:
        lines = output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Parse temperature (e.g., "Temperature: 45.0 C")
            if 'temperature' in line.lower() or 'temp' in line.lower():
                try:
                    # Extract number before 'C' or 'c'
                    temp_str = line.split(':')[-1].strip()
                    temp_str = temp_str.replace('C', '').replace('c', '').strip()
                    metrics["temperature_c"] = float(temp_str)
                except:
                    pass
            
            # Parse power (e.g., "Average Graphics Package Power: 120.0 W")
            if 'power' in line.lower() and 'w' in line.lower():
                try:
                    # Extract number before 'W' or 'w'
                    power_str = line.split(':')[-1].strip()
                    power_str = power_str.replace('W', '').replace('w', '').strip()
                    metrics["power_draw_w"] = float(power_str)
                except:
                    pass
            
            # Parse GPU utilization (e.g., "GPU use (%): 75")
            if 'use' in line.lower() and '%' in line.lower():
                try:
                    util_str = line.split(':')[-1].strip()
                    util_str = util_str.replace('%', '').strip()
                    metrics["utilization_percent"] = int(float(util_str))
                except:
                    pass
            
            # Parse VRAM (e.g., "VRAM Total Memory (B): 17163091968" or "VRAM Used Memory (B): 1234567890")
            if 'vram' in line.lower() and 'total' in line.lower():
                try:
                    vram_str = line.split(':')[-1].strip()
                    vram_bytes = float(vram_str)
                    metrics["vram_total_gb"] = round(vram_bytes / (1024**3), 2)
                except:
                    pass
            
            if 'vram' in line.lower() and 'used' in line.lower():
                try:
                    vram_str = line.split(':')[-1].strip()
                    vram_bytes = float(vram_str)
                    metrics["vram_used_gb"] = round(vram_bytes / (1024**3), 2)
                except:
                    pass
        
        return metrics
        
    except Exception as e:
        logger.warning(f"Error parsing rocm-smi output: {e}")
        return metrics


def _get_amd_gpu_metrics() -> dict:
    """
    Get AMD GPU metrics with fallback.
    
    Tries rocm-smi first, falls back to PyTorch/DirectML if unavailable.
    Returns metrics in same format as NVIDIA metrics.
    """
    # Try rocm-smi first
    rocm_metrics = _query_rocm_smi()
    
    if rocm_metrics:
        # rocm-smi succeeded
        return {
            "temperature_c": rocm_metrics["temperature_c"],
            "power_draw_w": rocm_metrics["power_draw_w"],
            "utilization_percent": rocm_metrics["utilization_percent"],
            "vram_used_gb": rocm_metrics["vram_used_gb"],
            "vram_total_gb": rocm_metrics["vram_total_gb"],
            "vram_free_gb": round(rocm_metrics["vram_total_gb"] - rocm_metrics["vram_used_gb"], 2),
            "vram_percent": round((rocm_metrics["vram_used_gb"] / rocm_metrics["vram_total_gb"]) * 100, 1) if rocm_metrics["vram_total_gb"] > 0 else 0,
            "source": "rocm-smi"
        }
    else:
        # Fallback to PyTorch/DirectML
        logger.info("Using PyTorch fallback for AMD GPU metrics")
        try:
            # Check if CUDA (ROCm) is available
            if torch.cuda.is_available():
                vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                vram_allocated = torch.cuda.memory_allocated(0) / 1024**3
                vram_reserved = torch.cuda.memory_reserved(0) / 1024**3
                
                return {
                    "temperature_c": 0,  # Not available via PyTorch
                    "power_draw_w": 0.0,  # Not available via PyTorch
                    "utilization_percent": 0,  # Not available via PyTorch
                    "vram_used_gb": round(vram_reserved, 2),
                    "vram_total_gb": round(vram_total, 2),
                    "vram_free_gb": round(vram_total - vram_reserved, 2),
                    "vram_percent": round((vram_reserved / vram_total) * 100, 1) if vram_total > 0 else 0,
                    "source": "pytorch"
                }
            else:
                # DirectML fallback - use hardcoded values from pipeline_service
                # DirectML doesn't expose VRAM info through PyTorch API
                logger.info("Using DirectML fallback with static values")
                
                # Get VRAM info from pipeline_service if available
                vram_total_gb = 16.0  # Default for RX 9070
                vram_used_gb = 0.0
                
                # Try to get from pipeline service
                if hasattr(pipeline_service, 'device') and pipeline_service.device:
                    # Check if there's any VRAM usage we can estimate
                    if pipeline_service.pipe is not None:
                        # Model is loaded, estimate usage
                        vram_used_gb = 4.0  # Rough estimate for loaded model
                
                return {
                    "temperature_c": 0,
                    "power_draw_w": 0.0,
                    "utilization_percent": 0,
                    "vram_used_gb": vram_used_gb,
                    "vram_total_gb": vram_total_gb,
                    "vram_free_gb": round(vram_total_gb - vram_used_gb, 2),
                    "vram_percent": round((vram_used_gb / vram_total_gb) * 100, 1) if vram_total_gb > 0 else 0,
                    "source": "directml-static"
                }
        except Exception as e:
            logger.error(f"PyTorch fallback failed: {e}")
            # Return basic DirectML values
            return {
                "temperature_c": 0,
                "power_draw_w": 0.0,
                "utilization_percent": 0,
                "vram_used_gb": 0.0,
                "vram_total_gb": 16.0,  # RX 9070 has 16GB
                "vram_free_gb": 16.0,
                "vram_percent": 0.0,
                "source": "directml-fallback"
            }


def increment_generation_stats(gen_time: float = 0.0):
    """Called after each generation to update stats"""
    global _total_generations, _total_generation_time
    _total_generations += 1
    _total_generation_time += gen_time


@router.get("/health")
async def health_check():
    """Health check endpoint with stats"""
    uptime_seconds = time.time() - _server_start_time
    
    # Format uptime
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    if hours > 0:
        uptime_str = f"{hours}h {minutes}m"
    else:
        uptime_str = f"{minutes}m"
    
    # Convert device to string if it's a torch.device object
    device_str = str(pipeline_service.device) if pipeline_service.device else "unknown"
    
    return {
        "status": "healthy",
        "model_loaded": pipeline_service.pipe is not None,
        "device": device_str,
        "uptime": uptime_str,
        "stats": {
            "total_generations": _total_generations,
            "total_generation_time": round(_total_generation_time, 2)
        }
    }


@router.get("/system")
async def get_system_info():
    """Get system information"""
    info = {
        "gpu_name": "Unknown",
        "device": pipeline_service.device,
        "vram_total": 0.0,
        "vram_used": 0.0,
        "gpu_temp": 0.0,
        "dram_extension_enabled": pipeline_service.dram_config["enabled"],
        "dram_extension_available": False
    }
    
    if pipeline_service.device == "cuda":
        try:
            info["gpu_name"] = torch.cuda.get_device_name(0)
            vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            info["vram_total"] = vram_total
            info["vram_used"] = torch.cuda.memory_allocated(0) / 1024**3
            info["dram_extension_available"] = vram_total <= pipeline_service.dram_config["vram_threshold_gb"]
            
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader'],
                    capture_output=True, text=True, timeout=2
                )
                info["gpu_temp"] = float(result.stdout.strip())
            except:
                info["gpu_temp"] = 0
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
    
    return info


@router.get("/gpu-info")
async def get_gpu_info():
    """Get detailed GPU, CPU, and RAM information"""
    info = {
        "gpu_name": "Unknown",
        "vram_total": 0.0,
        "vram_used": 0.0,
        "vram_free": 0.0,
        "vram_percent": 0.0,
        "gpu_temp": 0,
        "power_draw": 0.0,
        "gpu_utilization": 0,
        "status": "unknown",
        "vendor": "unknown",
        "metrics_source": "none",
        # CPU info
        "cpu_percent": 0.0,
        "cpu_freq": 0.0,
        "cpu_cores": 0,
        # RAM info
        "ram_total": 0.0,
        "ram_used": 0.0,
        "ram_free": 0.0,
        "ram_percent": 0.0,
        # System power (if available)
        "system_power": None
    }
    
    # Get CPU and RAM info using psutil
    if PSUTIL_AVAILABLE:
        try:
            # CPU
            info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            info["cpu_cores"] = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                info["cpu_freq"] = round(cpu_freq.current / 1000, 2)  # GHz
            
            # RAM
            ram = psutil.virtual_memory()
            info["ram_total"] = round(ram.total / (1024**3), 2)  # GB
            info["ram_used"] = round(ram.used / (1024**3), 2)  # GB
            info["ram_free"] = round(ram.available / (1024**3), 2)  # GB
            info["ram_percent"] = ram.percent
        except Exception as e:
            logger.warning(f"psutil error: {e}")
    
    # Check if GPU is available (CUDA or DirectML)
    device_str = str(pipeline_service.device) if pipeline_service.device else ""
    is_gpu_available = torch.cuda.is_available() or "privateuseone" in device_str.lower() or "dml" in device_str.lower()
    is_directml = "privateuseone" in device_str.lower() or "dml" in device_str.lower()
    
    logger.info(f"GPU Info Debug: device_str='{device_str}', torch.cuda.is_available()={torch.cuda.is_available()}, is_gpu_available={is_gpu_available}, is_directml={is_directml}")
    
    if is_gpu_available:
        try:
            # Get GPU name - special handling for DirectML
            if is_directml:
                # DirectML doesn't expose GPU name, use hardcoded AMD RX 9070
                gpu_name = "AMD Radeon RX 9070"
                info["vendor"] = "amd"
            else:
                gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "Unknown GPU"
                # Detect if AMD GPU
                is_amd = pipeline_service._detect_amd_gpu(gpu_name) if hasattr(pipeline_service, '_detect_amd_gpu') else False
                info["vendor"] = "amd" if is_amd else "nvidia"
            
            info["gpu_name"] = gpu_name
            info["status"] = "success"
            
            if info["vendor"] == "amd" or is_directml:
                # Use AMD-specific metrics
                logger.info("Using AMD/DirectML metrics path")
                amd_metrics = _get_amd_gpu_metrics()
                info["gpu_temp"] = int(amd_metrics["temperature_c"])
                info["power_draw"] = amd_metrics["power_draw_w"]
                info["gpu_utilization"] = amd_metrics["utilization_percent"]
                info["vram_used"] = amd_metrics["vram_used_gb"]
                info["vram_total"] = amd_metrics["vram_total_gb"]
                info["vram_free"] = amd_metrics["vram_free_gb"]
                info["vram_percent"] = amd_metrics["vram_percent"]
                info["metrics_source"] = amd_metrics["source"]
                logger.info(f"AMD Metrics: VRAM Total={info['vram_total']}GB, Used={info['vram_used']}GB, Source={info['metrics_source']}")
            else:
                # Use NVIDIA-specific metrics (nvidia-smi)
                logger.info("Using NVIDIA metrics path")
                info["metrics_source"] = "nvidia-smi"
                try:
                    result = subprocess.run(
                        ['nvidia-smi', '--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total', 
                         '--format=csv,noheader,nounits'],
                        capture_output=True, text=True, timeout=3
                    )
                    if result.returncode == 0:
                        parts = result.stdout.strip().split(',')
                        if len(parts) >= 5:
                            info["gpu_temp"] = int(float(parts[0].strip()))
                            try:
                                info["power_draw"] = float(parts[1].strip())
                            except:
                                info["power_draw"] = 0.0
                            info["gpu_utilization"] = int(float(parts[2].strip()))
                            # VRAM in MB from nvidia-smi, convert to GB
                            vram_used_mb = float(parts[3].strip())
                            vram_total_mb = float(parts[4].strip())
                            info["vram_used"] = round(vram_used_mb / 1024, 2)
                            info["vram_total"] = round(vram_total_mb / 1024, 2)
                            info["vram_free"] = round((vram_total_mb - vram_used_mb) / 1024, 2)
                            info["vram_percent"] = round((vram_used_mb / vram_total_mb) * 100, 1) if vram_total_mb > 0 else 0
                except FileNotFoundError:
                    # nvidia-smi not found, fallback to PyTorch values
                    info["metrics_source"] = "pytorch"
                    if torch.cuda.is_available():
                        vram_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
                        vram_reserved = torch.cuda.memory_reserved(0) / 1024**3
                        info["vram_total"] = round(vram_total, 2)
                        info["vram_used"] = round(vram_reserved, 2)
                        info["vram_free"] = round(vram_total - vram_reserved, 2)
                        info["vram_percent"] = round((vram_reserved / vram_total) * 100, 1) if vram_total > 0 else 0
                except Exception as e:
                    logger.warning(f"nvidia-smi error: {e}")
                    info["metrics_source"] = "pytorch"
                
        except Exception as e:
            logger.error(f"Error getting GPU info: {e}")
            info["status"] = "error"
    else:
        info["status"] = "no_gpu"
    
    return {"status": info["status"], "gpu": info}


@router.get("/version")
async def get_version_info():
    """Get version information"""
    import sys
    import platform
    
    # Detect OS
    os_name = platform.system()
    if os_name == "Darwin":
        os_name = "macOS"
    
    # Convert device to string if it's a torch.device object
    device_str = str(pipeline_service.device) if pipeline_service.device else "unknown"
    
    version_info = {
        "iris_version": "1.2.0",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "pytorch_version": torch.__version__,
        "cuda_version": torch.version.cuda if torch.cuda.is_available() else "CPU",
        "current_model": pipeline_service.current_model,
        "device": device_str,
        "os": os_name
    }
    
    # Add ROCm version if AMD GPU detected
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        is_amd = pipeline_service._detect_amd_gpu(gpu_name)
        
        if is_amd:
            # Try to get ROCm version
            try:
                rocm_smi_path = getattr(Config, 'ROCM_SMI_PATH', 'rocm-smi')
                result = subprocess.run(
                    [rocm_smi_path, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    # Parse ROCm version from output
                    for line in result.stdout.split('\n'):
                        if 'version' in line.lower():
                            version_info["rocm_version"] = line.split(':')[-1].strip()
                            break
                    if "rocm_version" not in version_info:
                        version_info["rocm_version"] = "Unknown"
                else:
                    version_info["rocm_version"] = "Unknown"
            except:
                version_info["rocm_version"] = "Not available"
        else:
            version_info["rocm_version"] = None
    else:
        version_info["rocm_version"] = None
    
    return version_info


def estimate_model_size(model_name: str) -> float:
    """
    Estimate model size based on architecture.
    
    Args:
        model_name: Key from MODEL_CONFIGS
        
    Returns:
        Estimated size in GB
    """
    model_id = MODEL_CONFIGS[model_name]["id"]
    
    # FLUX models: ~24GB
    if "flux" in model_id.lower():
        return 24.0
    
    # Z-Anime: ~10GB (includes Qwen text encoder + transformer)
    if "z-anime" in model_id.lower():
        return 10.0
    
    # SDXL models: ~12GB
    sdxl_keywords = ["xl", "sdxl", "pony", "stable-diffusion-3"]
    if any(kw in model_id.lower() for kw in sdxl_keywords):
        return 12.0
    
    # SD 1.5 models: ~5GB
    return 5.0


@router.get("/models")
async def get_available_models():
    """Get list of available models with download status and parameter information"""
    models = []
    for key, config in MODEL_CONFIGS.items():
        models.append({
            "id": key,
            "name": config["id"].split("/")[-1],
            "description": config["description"],
            "huggingface_id": config["id"],
            "is_loaded": pipeline_service.current_model == key,
            "is_downloaded": pipeline_service.is_model_downloaded(key),
            "recommended_steps": config.get("recommended_steps"),
            "recommended_cfg": config.get("recommended_cfg"),
            "supports_negative_prompt": config.get("supports_negative_prompt"),
            "estimated_size_gb": estimate_model_size(key)
        })
    return {"models": models}


@router.get("/rpc-status")
async def get_rpc_status():
    """Get RPC status (placeholder)"""
    return {
        "connected": True,
        "status": "ready",
        "details": "Ready for requests"
    }


@router.get("/devices")
async def get_available_devices():
    """Get list of available compute devices"""
    devices = pipeline_service.get_available_devices()
    return {
        "devices": devices,
        "current_device": pipeline_service.device,
        "forced_device": pipeline_service.forced_device
    }


@router.post("/device")
async def switch_device(device: str):
    """Switch between GPU and CPU mode"""
    try:
        result = await pipeline_service.switch_device(device)
        return result
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to switch device: {str(e)}")
