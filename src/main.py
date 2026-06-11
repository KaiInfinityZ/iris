#!/usr/bin/env python3
"""
I.R.I.S. Universal Starter
==========================
Intelligent Rendering & Image Synthesis

Usage:
    python src/main.py                          # Default: --mode react --device auto
    python src/main.py --mode api               # API only (no frontend)
    python src/main.py --mode react             # API + React frontend (default)
    python src/main.py --device cpu             # Force CPU mode
    python src/main.py --device gpu             # Force GPU mode (DirectML/CUDA)
    python src/main.py --no-bot                 # Disable Discord bot
    python src/main.py --open-ip                # Allow external access (domain/network)
    python src/main.py --host 192.168.1.100     # Bind to specific IP
    python src/main.py --port 3000              # Use custom port

Modes:
    api     - Only API server, no frontend (for external frontends)
    react   - API + React frontend (default)

Device Modes:
    auto    - Auto-detect best device (default)
    cpu     - Force CPU mode (slow, but supports all models)
    gpu     - Force GPU mode (DirectML/CUDA/ROCm)
    cuda    - Force CUDA/ROCm (NVIDIA/AMD)
    mps     - Force Apple Silicon (Metal)

Network Options:
    --open-ip    - Bind to 0.0.0.0 for external/domain access
    --host       - Custom host address (e.g., 192.168.1.100)
    --port       - Custom port (default: 8000)

Examples for Domain/External Access:
    python src/main.py --open-ip                # Allows access from any IP
    python src/main.py --open-ip --port 80      # Public access on port 80
    python src/main.py --host 0.0.0.0 --port 443  # HTTPS with custom port

Press CTRL+C to exit | CTRL+R to restart (Windows)
"""

import sys
import subprocess
import os
import signal
import time
import json
import threading
import argparse
from pathlib import Path

# Windows keyboard input
if sys.platform == 'win32':
    import msvcrt

current_processes = []
shutdown_in_progress = False
restart_requested = False

def signal_handler(sig, frame):
    """Handle CTRL+C gracefully"""
    global shutdown_in_progress
    
    if shutdown_in_progress:
        print("\n[IRIS] Force shutdown...")
        for process in current_processes:
            try:
                process.kill()
            except:
                pass
        sys.exit(1)
    
    shutdown_in_progress = True
    print("\n\n[IRIS] Shutting down all services...")
    print("[IRIS] Press CTRL+C again to force immediate shutdown")
    
    for process in current_processes:
        try:
            process.send_signal(signal.SIGINT)
        except:
            pass
    
    start_wait = time.time()
    all_stopped = False
    
    while time.time() - start_wait < 10:
        all_stopped = True
        for process in current_processes:
            if process.poll() is None:
                all_stopped = False
                break
        
        if all_stopped:
            break
        time.sleep(0.5)
    
    if not all_stopped:
        print("[IRIS] Forcing shutdown...")
        for process in current_processes:
            try:
                process.kill()
            except:
                pass
    
    print("[IRIS] All services stopped")
    sys.exit(0)

def print_banner(mode, device='auto', open_ip=False, custom_host=None, custom_port=None):
    """Print I.R.I.S. startup banner"""
    mode_labels = {
        'api': 'API Only',
        'react': 'API + React Frontend'
    }
    device_labels = {
        'auto': 'Auto-Detect',
        'cpu': 'CPU (Forced)',
        'gpu': 'GPU (Forced)',
        'cuda': 'CUDA/ROCm (Forced)',
        'mps': 'Apple Silicon (Forced)',
        'privateuseone': 'DirectML (Forced)'
    }
    device_label = device_labels.get(device, device)
    
    # Determine network mode
    if custom_host:
        network_label = f"Custom ({custom_host})"
    elif open_ip:
        network_label = "External (0.0.0.0)"
    else:
        network_label = "Local Only"
    
    banner = f"""
    ╔══════════════════════════════════════════════════╗
    ║                                                  ║
    ║              I.R.I.S. v1.2.0                     ║
    ║   Intelligent Rendering & Image Synthesis        ║
    ║                                                  ║
    ║   Mode: {mode_labels.get(mode, mode):<40} ║
    ║   Device: {device_label:<38} ║
    ║   Network: {network_label:<37} ║
    ║                                                  ║
    ╚══════════════════════════════════════════════════╝
    """
    try:
        print(banner)
    except UnicodeEncodeError:
        # Fallback for Windows console encoding issues
        print(f"\n    I.R.I.S. v1.2.0 - Intelligent Rendering & Image Synthesis")
        print(f"    Mode: {mode_labels.get(mode, mode)}")
        print(f"    Device: {device_label}")
        print(f"    Network: {network_label}\n")

def load_settings():
    """Load settings from settings.json"""
    project_root = Path(__file__).resolve().parents[1]
    settings_path = project_root / "settings.json"
    
    default_settings = {
        "discordEnabled": False,
        "dramEnabled": False,
        "vramThreshold": 6,
        "maxDram": 8
    }
    
    if settings_path.exists():
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
                return {**default_settings, **settings}
        except Exception as e:
            print(f"[WARN] Could not load settings.json: {e}")
    
    return default_settings

def start_web_server(mode='react', device='auto', host=None, port=None, open_ip=False):
    """Start FastAPI Web UI Server with specified mode and device"""
    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)
    
    # Set environment variables based on mode and device
    env = os.environ.copy()
    env["IRIS_MODE"] = mode
    
    # Set device mode
    if device != 'auto':
        env["IRIS_DEVICE"] = device
        print(f"[DEVICE] Forcing device mode: {device}")
    
    # Determine host
    if host:
        # Custom host specified
        final_host = host
    elif open_ip:
        # Open IP mode - bind to all interfaces
        final_host = "0.0.0.0"
    else:
        # Default to env var or localhost
        final_host = env.get("HOST", "0.0.0.0")
    
    # Determine port
    if port:
        final_port = str(port)
    else:
        final_port = env.get("PORT", "8000")
    
    # Update environment
    env["HOST"] = final_host
    env["PORT"] = final_port
    
    # Determine what to enable
    enable_react = mode == 'react'
    
    if enable_react:
        env["IRIS_SERVE_REACT"] = "1"
    
    print("\n[WEB] Starting I.R.I.S. Server...")
    print(f"      Mode: {mode}")
    print(f"      Device: {device}")
    
    # Show network info
    if final_host == "0.0.0.0":
        print(f"      Host: 0.0.0.0 (External access enabled)")
        print(f"      API:   http://localhost:{final_port}/api")
        
        # Get all network interfaces and their IP addresses
        import socket
        try:
            hostname = socket.gethostname()
            # Get all IP addresses for this host
            ip_addresses = []
            try:
                # Get all addresses for the hostname
                addrs = socket.getaddrinfo(hostname, None, socket.AF_INET)
                for addr in addrs:
                    ip = addr[4][0]
                    if ip not in ip_addresses and ip != '127.0.0.1':
                        ip_addresses.append(ip)
            except:
                pass
            
            # Also try to get the default network IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                default_ip = s.getsockname()[0]
                s.close()
                if default_ip not in ip_addresses and default_ip != '127.0.0.1':
                    ip_addresses.insert(0, default_ip)
            except:
                pass
            
            # Display all found IPs
            if ip_addresses:
                for ip in ip_addresses:
                    print(f"             http://{ip}:{final_port}/api")
            else:
                print(f"             http://<your-local-ip>:{final_port}/api")
        except:
            print(f"             http://<your-local-ip>:{final_port}/api")
        
        if enable_react:
            react_dist = project_root / "frontend" / "dist"
            if react_dist.exists():
                print(f"      React: http://localhost:{final_port}")
                if ip_addresses:
                    for ip in ip_addresses:
                        print(f"             http://{ip}:{final_port}")
                else:
                    print(f"             http://<your-local-ip>:{final_port}")
            else:
                print(f"      React: [!] Build missing - run 'npm run build' in frontend/")
    else:
        print(f"      Host: {final_host}")
        print(f"      API:   http://{final_host}:{final_port}/api")
        
        if enable_react:
            react_dist = project_root / "frontend" / "dist"
            if react_dist.exists():
                print(f"      React: http://{final_host}:{final_port}")
            else:
                print(f"      React: [!] Build missing - run 'npm run build' in frontend/")
    
    if mode == 'api':
        print(f"      [No frontend - API only mode]")
    
    print()

    process = subprocess.Popen([
        sys.executable,
        "-m", "uvicorn",
        "src.api.server:app",
        "--host", final_host,
        "--port", final_port,
    ], env=env)

    current_processes.append(process)
    return process

def start_discord_bot():
    """Start Discord Bot with Rich Presence"""
    print("[BOT] Starting Discord Bot...")
    print("      Rich Presence will show generation status\n")
    
    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)
    
    process = subprocess.Popen([sys.executable, "src/services/bot.py"])
    current_processes.append(process)
    return process

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='I.R.I.S. - Intelligent Rendering & Image Synthesis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  api     Only API server, no frontend (for development with external frontend)
  react   API + React frontend (default)

Device Modes:
  auto    Auto-detect best device (default)
  cpu     Force CPU mode (slow, but supports all models including Z-Anime)
  gpu     Force GPU mode (DirectML/CUDA/ROCm auto-detect)
  cuda    Force CUDA/ROCm (NVIDIA/AMD)
  mps     Force Apple Silicon (Metal)

Network Options:
  --open-ip    Bind to 0.0.0.0 for external access (domain/network)
  --host       Custom host address (overrides --open-ip)
  --port       Custom port (default: 8000)

Examples:
  python src/main.py                          # Start with React frontend, auto-detect device
  python src/main.py --mode api               # API only for React dev server
  python src/main.py --device cpu             # Force CPU mode (for Z-Anime)
  python src/main.py --device gpu             # Force GPU mode (DirectML/CUDA)
  python src/main.py --open-ip                # Allow external access (0.0.0.0)
  python src/main.py --host 192.168.1.100     # Bind to specific IP
  python src/main.py --port 3000              # Use custom port
  python src/main.py --open-ip --port 80      # Public access on port 80
        """
    )
    parser.add_argument(
        '--mode', '-m',
        choices=['api', 'react'],
        default='react',
        help='Server mode (default: react)'
    )
    parser.add_argument(
        '--device', '-d',
        choices=['auto', 'cpu', 'gpu', 'cuda', 'mps', 'privateuseone'],
        default='auto',
        help='Device mode (default: auto)'
    )
    parser.add_argument(
        '--no-bot',
        action='store_true',
        help='Disable Discord bot even if enabled in settings'
    )
    parser.add_argument(
        '--open-ip',
        action='store_true',
        help='Bind to 0.0.0.0 for external/domain access (allows connections from any IP)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default=None,
        help='Custom host address to bind to (e.g., 192.168.1.100 or 0.0.0.0)'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=None,
        help='Custom port to bind to (default: 8000 or PORT env var)'
    )
    return parser.parse_args()

def main():
    """Main entry point"""
    global restart_requested, shutdown_in_progress
    
    args = parse_args()
    
    print_banner(args.mode, args.device, args.open_ip, args.host, args.port)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Load settings
    settings = load_settings()
    discord_enabled = settings.get("discordEnabled", False) and not args.no_bot
    
    # Show startup info
    print(f"    [CONFIG] Mode: {args.mode}")
    print(f"    [CONFIG] Device: {args.device}")
    print(f"    [CONFIG] Discord Bot: {'Enabled' if discord_enabled else 'Disabled'}")
    print(f"    [CONFIG] DRAM Extension: {'Enabled' if settings.get('dramEnabled') else 'Disabled'}")
    
    # Show network config
    if args.open_ip:
        print(f"    [CONFIG] Network: External access enabled (0.0.0.0)")
    elif args.host:
        print(f"    [CONFIG] Host: {args.host}")
    else:
        print(f"    [CONFIG] Network: Local only (localhost)")
    
    if args.port:
        print(f"    [CONFIG] Port: {args.port}")
    
    print()
    print("    [TIP] Press CTRL+C to exit | CTRL+R to restart")
    print()
    
    # Start keyboard listener for CTRL+R (Windows only)
    if sys.platform == 'win32':
        def keyboard_listener():
            global restart_requested, shutdown_in_progress
            try:
                while not shutdown_in_progress:
                    try:
                        if msvcrt.kbhit():
                            key = msvcrt.getch()
                            # CTRL+R = \x12 (18 decimal)
                            if key == b'\x12':
                                print("\n[IRIS] Restart requested (CTRL+R)...")
                                restart_requested = True
                                # Terminate processes
                                for process in current_processes:
                                    try:
                                        # Use taskkill for reliable termination on Windows
                                        subprocess.run(
                                            ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                                            capture_output=True,
                                            timeout=5
                                        )
                                    except:
                                        try:
                                            process.terminate()
                                        except:
                                            pass
                                break
                    except Exception:
                        pass
                    time.sleep(0.05)
            except Exception as e:
                print(f"[WARN] Keyboard listener error: {e}")
        
        kb_thread = threading.Thread(target=keyboard_listener, daemon=True)
        kb_thread.start()
    
    while True:
        restart_requested = False
        current_processes.clear()
        shutdown_in_progress = False
        
        # Clean up any old restart signal file
        project_root = Path(__file__).resolve().parents[1]
        signal_file = project_root / "restart_signal"
        if signal_file.exists():
            signal_file.unlink()
        
        try:
            # Start web server with specified mode and device
            web_process = start_web_server(
                mode=args.mode, 
                device=args.device,
                host=args.host,
                port=args.port,
                open_ip=args.open_ip
            )
            
            # Start Discord bot if enabled
            bot_process = None
            if discord_enabled:
                time.sleep(0.5)
                bot_process = start_discord_bot()
            
            # Wait for processes - check periodically for restart
            while True:
                # Check if restart was requested via CTRL+R
                if restart_requested:
                    break
                
                # Check if restart was requested via Admin Panel (signal file)
                if signal_file.exists():
                    print("\n[IRIS] Restart requested via Admin Panel...")
                    signal_file.unlink()
                    restart_requested = True
                    break
                
                # Check if web process ended
                if web_process.poll() is not None:
                    break
                    
                time.sleep(0.2)
            
            # If restart requested, clean up and continue
            if restart_requested:
                print("[IRIS] Restarting services...")
                # Make sure all processes are stopped
                for process in current_processes:
                    if process.poll() is None:
                        try:
                            if sys.platform == 'win32':
                                subprocess.run(
                                    ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                                    capture_output=True,
                                    timeout=5
                                )
                            else:
                                process.terminate()
                        except:
                            pass
                
                # Wait for processes to end
                for process in current_processes:
                    try:
                        process.wait(timeout=3)
                    except:
                        pass
                
                time.sleep(1)
                print("[IRIS] Starting fresh...\n")
                continue
            else:
                break
                
        except KeyboardInterrupt:
            if restart_requested:
                continue
            break

if __name__ == "__main__":
    main()
