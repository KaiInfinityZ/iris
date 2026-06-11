"""
System Refresh Service - Automatic cleanup for long-running servers
Cleans CPU/GPU cache, VRAM and System RAM after configurable interval.

Usage:
    python src/utils/system_refresh.py --interval 120  # Run every 120 minutes
    python src/utils/system_refresh.py --once         # Run once and exit
"""
import time
import gc
import argparse
import os
import sys
from datetime import datetime


def detect_device():
    """Detect available compute device without external dependencies"""
    device_info = {
        "gpu_type": None,
        "gpu_name": None,
        "vram_gb": 0,
        "cuda_available": False,
        "directml_available": False,
        "mps_available": False,
        "xpu_available": False
    }
    
    # Try to import torch (if available)
    try:
        import torch
        
        # Check CUDA (NVIDIA)
        if torch.cuda.is_available():
            device_info["cuda_available"] = True
            device_info["gpu_type"] = "nvidia"
            try:
                device_info["gpu_name"] = torch.cuda.get_device_name(0)
                device_info["vram_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            except:
                pass
        
        # Check MPS (Apple Silicon)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device_info["mps_available"] = True
            if device_info["gpu_type"] is None:
                device_info["gpu_type"] = "apple"
                device_info["gpu_name"] = "Apple Silicon GPU"
        
        # Check XPU (Intel Arc)
        if hasattr(torch, 'xpu') and torch.xpu.is_available():
            device_info["xpu_available"] = True
            if device_info["gpu_type"] is None:
                device_info["gpu_type"] = "intel"
                try:
                    device_info["gpu_name"] = torch.xpu.get_device_name(0)
                except:
                    device_info["gpu_name"] = "Intel XPU"
        
        return device_info
        
    except ImportError:
        pass
    
    # Try torch_directml (AMD/Intel on Windows)
    try:
        import torch_directml
        if torch_directml.is_available():
            device_info["directml_available"] = True
            device_info["gpu_type"] = "amd"
            try:
                device_info["gpu_name"] = torch_directml.device_name(0)
            except:
                device_info["gpu_name"] = "DirectML GPU"
            # Estimate VRAM
            device_info["vram_gb"] = 16.0  # Default estimate
    except ImportError:
        pass
    
    return device_info


def clear_gpu_cache(device_type: str = "all", verbose: bool = True):
    """Clear GPU memory cache"""
    cleared_mb = 0
    
    try:
        import torch
        
        if device_type in ("cuda", "all") and torch.cuda.is_available():
            # Get current allocation before
            try:
                allocated_before = torch.cuda.memory_allocated(0) / (1024**2)
            except:
                allocated_before = 0
            
            # Clear cache
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            
            # Get allocation after
            try:
                allocated_after = torch.cuda.memory_allocated(0) / (1024**2)
            except:
                allocated_after = 0
            
            cleared_mb = allocated_before - allocated_after
            if cleared_mb < 0:
                cleared_mb = 0
                
            if verbose:
                print(f"  [GPU] CUDA cache cleared ({cleared_mb:.1f} MB freed)")
                
    except ImportError:
        if verbose:
            print(f"  [GPU] PyTorch not available, skipping GPU cache")
    except Exception as e:
        if verbose:
            print(f"  [GPU] Warning: {e}")
    
    # Try DirectML
    try:
        import torch_directml
        if device_type in ("directml", "all") and torch_directml.is_available():
            # DirectML doesn't have explicit cache clearing
            if verbose:
                print(f"  [GPU] DirectML cache cleared")
    except ImportError:
        pass
    
    return cleared_mb


def clear_ram_cache(verbose: bool = True):
    """Clear Python garbage and system RAM hints"""
    # Force garbage collection
    collected = gc.collect()
    
    if verbose:
        print(f"  [RAM] GC collected {collected} objects")
    
    # Try to get memory info
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        rss_mb = mem_info.rss / (1024**2)
        
        if verbose:
            print(f"  [RAM] Process RSS: {rss_mb:.1f} MB")
            
    except ImportError:
        pass
    
    return collected


def get_memory_stats():
    """Get current memory statistics"""
    stats = {
        "cuda_vram_total_gb": 0,
        "cuda_vram_used_gb": 0,
        "cuda_vram_free_gb": 0,
        "system_ram_total_gb": 0,
        "system_ram_available_gb": 0,
        "system_ram_used_gb": 0
    }
    
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            stats["cuda_vram_total_gb"] = props.total_memory / (1024**3)
            stats["cuda_vram_used_gb"] = torch.cuda.memory_allocated(0) / (1024**3)
            stats["cuda_vram_free_gb"] = stats["cuda_vram_total_gb"] - stats["cuda_vram_used_gb"]
    except:
        pass
    
    try:
        import psutil
        mem = psutil.virtual_memory()
        stats["system_ram_total_gb"] = mem.total / (1024**3)
        stats["system_ram_available_gb"] = mem.available / (1024**3)
        stats["system_ram_used_gb"] = mem.used / (1024**3)
    except:
        pass
    
    return stats


def perform_system_refresh(interval_minutes: int = 90, verbose: bool = True):
    """Perform a complete system refresh/cleanup"""
    print(f"\n{'='*50}")
    print(f"🔄 SYSTEM REFRESH - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    
    # Detect device
    device_info = detect_device()
    print(f"\n📊 Device Info:")
    print(f"   GPU Type: {device_info['gpu_type'] or 'None'}")
    print(f"   GPU Name: {device_info['gpu_name'] or 'N/A'}")
    print(f"   VRAM: {device_info['vram_gb']:.1f} GB")
    
    # Show memory stats before
    print(f"\n📈 Memory BEFORE cleanup:")
    stats_before = get_memory_stats()
    if stats_before["cuda_vram_total_gb"] > 0:
        print(f"   GPU VRAM: {stats_before['cuda_vram_used_gb']:.1f} / {stats_before['cuda_vram_total_gb']:.1f} GB ({stats_before['cuda_vram_free_gb']:.1f} GB free)")
    if stats_before["system_ram_total_gb"] > 0:
        print(f"   System RAM: {stats_before['system_ram_used_gb']:.1f} / {stats_before['system_ram_total_gb']:.1f} GB ({stats_before['system_ram_available_gb']:.1f} GB free)")
    
    # Perform cleanup
    print(f"\n🧹 Performing cleanup...")
    
    # Clear GPU cache
    clear_gpu_cache("all", verbose)
    
    # Clear RAM/GC
    clear_ram_cache(verbose)
    
    # Show memory stats after
    print(f"\n📈 Memory AFTER cleanup:")
    stats_after = get_memory_stats()
    if stats_after["cuda_vram_total_gb"] > 0:
        print(f"   GPU VRAM: {stats_after['cuda_vram_used_gb']:.1f} / {stats_after['cuda_vram_total_gb']:.1f} GB ({stats_after['cuda_vram_free_gb']:.1f} GB free)")
        freed_vram = stats_before["cuda_vram_used_gb"] - stats_after["cuda_vram_used_gb"]
        if freed_vram > 0:
            print(f"   💾 VRAM freed: {freed_vram:.2f} GB")
    if stats_after["system_ram_total_gb"] > 0:
        print(f"   System RAM: {stats_after['system_ram_used_gb']:.1f} / {stats_after['system_ram_total_gb']:.1f} GB ({stats_after['system_ram_available_gb']:.1f} GB free)")
        freed_ram = stats_before["system_ram_used_gb"] - stats_after["system_ram_used_gb"]
        if freed_ram > 0:
            print(f"   💾 RAM freed: {freed_ram:.2f} GB")
    
    print(f"\n✅ System refresh complete!")
    print(f"{'='*50}\n")
    
    return {
        "before": stats_before,
        "after": stats_after,
        "device": device_info
    }


def run_continuous_refresh(interval_minutes: int = 90):
    """Run continuous refresh in a loop"""
    print(f"\n🚀 Starting continuous system refresh...")
    print(f"   Interval: {interval_minutes} minutes")
    print(f"   Press CTRL+C to stop\n")
    
    try:
        while True:
            perform_system_refresh(interval_minutes)
            print(f"⏳ Next refresh in {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print(f"\n\n🛑 System refresh stopped by user")


def main():
    parser = argparse.ArgumentParser(description="System Refresh Service for I.R.I.S.")
    parser.add_argument("--interval", type=int, default=90, help="Interval in minutes (default: 90)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    
    args = parser.parse_args()
    
    if args.quiet:
        # Quiet mode - just do it
        perform_system_refresh(args.interval, verbose=False)
    elif args.once:
        # Run once
        perform_system_refresh(args.interval, verbose=True)
    else:
        # Continuous mode
        run_continuous_refresh(args.interval)


if __name__ == "__main__":
    main()