# 🌌 I.R.I.S.
### Intelligent Rendering & Image Synthesis

**A modular, local-first AI image generation engine — built to be forked, extended, and owned.**

I.R.I.S. is an **open-source AI image generation platform** designed as a **foundation**, not a locked product.  
Think of it as **Linux for AI image generation**:

> You get a fully working system —  
> but *you* decide how it evolves.

⚠️ **Runs entirely on your own hardware**  
No cloud. No accounts. No telemetry. No vendor lock-in.

---

![Python](https://img.shields.io/badge/python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-green)
![React](https://img.shields.io/badge/React-18-61dafb)
![WebSockets](https://img.shields.io/badge/WebSockets-realtime-purple)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)
![Status](https://img.shields.io/badge/status-v1.2.0-brightgreen)

---

## ✨ Core Philosophy

- 🧠 **Local-first** — everything runs on your machine
- 🔓 **Open Source** — modify, fork, redistribute
- 🧩 **Modular architecture** — UI, backend, models are replaceable
- 🧪 **Experiment-friendly** — designed for tinkering & research
- 🚀 **Production-capable** — APIs, WebSockets, scaling-ready

This repository provides a **fully functional reference implementation**, not a closed product.

---

## 🖼️ Feature Overview

### Core Features
- **Modern React Frontend** — Responsive UI built with React 18 & Tailwind CSS
- **Plugin System** — Install, manage, and use custom AI models via ZIP packages
- **Advanced Image Upscaler** — AI-powered upscaling from 2x to 16x with multiple models
- **Local Model Management** — Load models from local directories (HuggingFace Hub format)
- **Multiple AI models** (anime, realistic, pixel art, SDXL)
- **Text-to-Image** generation with real-time progress
- **WebSocket streaming** for live updates
- **Persistent prompt history** (server-side)
- **Multi-GPU support** (NVIDIA CUDA, AMD ROCm, Intel Arc XPU, Apple MPS, CPU)

### Advanced Features
- **DRAM Extension** — System RAM fallback for low VRAM GPUs (4GB+)
- **Multiple Upscalers** — Real-ESRGAN, Anime v3, Tile Mode, Lanczos
- **Custom resolutions** (256×256 → 2048×2048)
- **Hardware monitoring** — CPU, RAM, GPU power draw
- **Device switching** — Switch between GPU/CPU at runtime
- **Discord bot integration** — Auto-post generated images
- **Discord Rich Presence** — Show generation status

---

## 🚀 Quick Start

### Requirements
- Python 3.9 – 3.11
- GPU recommended (4 GB VRAM minimum)
- CUDA 11.8+ / ROCm 5.6+ / oneAPI (optional, CPU mode supported)

### Installation
```bash
git clone https://github.com/KaiTooast/iris.git
cd iris

python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt

# Build React frontend
build_frontend.bat  # Windows
# or manually: cd frontend && npm install && npm run build

# Optional: Copy environment template
cp .env.example .env
```

### Run
```bash
# Windows (use venv python directly)
.\venv\Scripts\python.exe src/start.py

# Linux / macOS
python src/start.py

# Server Modes
python src/start.py                 # React frontend (default)
python src/start.py --mode react    # React frontend (explicit)
python src/start.py --mode api      # API only (no frontend)

# Without Discord bot
python src/start.py --no-bot
```

🌐 **Frontend:** [http://localhost:8000](http://localhost:8000)  
🔍 **Upscaler:** [http://localhost:8000/upscaler](http://localhost:8000/upscaler)  
🔐 **Admin Panel:** [http://localhost:8000/admin](http://localhost:8000/admin)

---

## 🧩 Project Structure

```
iris/
├── src/                    # Backend & core logic
│   ├── api/                # FastAPI server & routes
│   │   ├── server.py       # Main server (generation, upscaling, settings)
│   │   ├── middleware/     # Rate limiting
│   │   ├── routes/         # API endpoints (system, devices)
│   │   └── services/       # NSFW filter, pipeline, history, queue
│   ├── core/               # Model loading & generation
│   ├── services/           # Discord bot
│   ├── utils/              # Logging, file management
│   └── start.py            # Entry point
│
├── frontend/               # Modern React Web UI
│   ├── src/
│   │   ├── pages/          # HomePage, GeneratePage, GalleryPage, SettingsPage
│   │   ├── components/     # Reusable components
│   │   ├── store/          # Zustand state management
│   │   └── lib/            # API utilities
│   ├── package.json
│   └── vite.config.js
│
├── static/                 # Static assets & runtime data
│   ├── css/                # Stylesheets
│   ├── js/                 # JavaScript
│   ├── config/             # Bot config files
│   └── data/               # History (prompts_history.json)
│
├── assets/                 # Static assets (thumbnails, icons)
│   └── thumbnails/         # Model thumbnails (WebP)
│
├── outputs/                # Generated images
├── Logs/                   # Runtime logs
├── docs/                   # Documentation
│
├── settings.json           # Runtime settings
└── requirements.txt        # Python dependencies
```

---

## ⚙️ Configuration

### settings.json
```json
{
  "dramEnabled": true,
  "vramThreshold": 6,
  "maxDram": 16,
  "discordEnabled": false
}
```

| Setting | Description |
|---------|-------------|
| `dramEnabled` | Use system RAM when VRAM is low |
| `vramThreshold` | VRAM threshold (GB) to enable DRAM Extension |
| `maxDram` | Maximum system RAM to use (GB) |
| `discordEnabled` | Auto-start Discord bot |

### .env (optional)
```env
HOST=0.0.0.0
PORT=8000
DEFAULT_MODEL=anime_kawai

# Discord Bot (optional)
DISCORD_BOT_TOKEN=your_token
DISCORD_CHANNEL_NEW_IMAGES=channel_id
DISCORD_CHANNEL_VARIATIONS=channel_id
DISCORD_CHANNEL_UPSCALED=channel_id
```

---

## 🖥️ Hardware Reference

### NVIDIA GPUs

| Tier | GPU | VRAM | Notes |
|------|-----|------|-------|
| **Minimum** | NVIDIA GTX 1650 | 4 GB | The birthplace. Small models, DRAM Extension recommended. |
| **Sweet Spot** | **AMD Radeom RX 9070** | 16 GB | Best Price to Performance. |
| **Advanced** | NVIDIA RTX 4070 Super | 12 GB | Faster inference, still VRAM-limited. |
| **Professional** | NVIDIA RTX 3090 Ti / 4090 | 24 GB | No-compromise local AI & SDXL. |
| **God Tier** | **NVIDIA RTX 5090** | 32 GB | Near Industrial scale. (Overkill for most) |

### AMD Radeon GPUs

| Tier | GPU | VRAM | Architecture | AI Accelerators | Notes |
|------|-----|------|--------------|-----------------|-------|
| **Minimum** | AMD RX 5700 XT | 8 GB | RDNA1 | None | Entry-level AMD support. DRAM Extension recommended. |
| **Good** | AMD RX 6800 XT | 16 GB | RDNA2 | None | Solid performance for SD 1.5 models. |
| **Recommended** | AMD RX 7800 XT | 16 GB | RDNA3 | Matrix Cores | Excellent AI performance with Matrix Cores. |
| **High-End** | AMD RX 7900 XTX | 24 GB | RDNA3 | Matrix Cores | SDXL-ready with Matrix Core acceleration. |
| **Latest** | **AMD RX 9070 XT** | 16 GB | RDNA4 | Enhanced AI Accelerators | Next-gen AI acceleration, optimized for diffusion models. |

> 💡 **AMD GPU Note:** RDNA3+ GPUs (RX 7000/9000 series) include dedicated Matrix Cores for AI workloads, providing significant performance improvements over RDNA1/2. RDNA4 (RX 9000 series) features enhanced AI accelerators specifically optimized for diffusion models.

> 💡 **Developer Note:** I.R.I.S. was **developed and tested on a GTX 1650**, proving functionality on low-end hardware.

---

## 🔌 Plugin System

I.R.I.S. features a **flexible plugin system** that allows you to install, manage, and use custom AI models without modifying source code.

### What are Plugins?

Plugins are **ZIP packages** containing:
- `manifest.json` — Model metadata and HuggingFace repository reference
- `thumbnail.webp` — Preview image for the UI

### Plugin Management

Access the **Plugin Manager** at [http://localhost:8000/plugins](http://localhost:8000/plugins)

**Features:**
- 📦 **Install plugins** via drag-and-drop ZIP upload
- ✅ **Enable/disable** plugins without uninstalling
- 🗑️ **Uninstall** plugins with one click
- 📥 **Automatic model downloads** from HuggingFace
- 🔍 **Search and filter** by model type, base, or status
- 🖼️ **Visual thumbnails** for easy identification

### Creating a Plugin

1. **Create manifest.json:**
```json
{
  "name": "My Custom Model",
  "description": "A custom AI model for specific use cases",
  "version": "1.0.0",
  "thumbnail": "thumbnail.webp",
  "hf_repo": "author/model-repo-id",
  "type": "txt2img",
  "base": "sd1.5",
  "recommended_steps": 30,
  "recommended_cfg": 7.5,
  "supports_negative_prompt": true
}
```

2. **Add a thumbnail** (512×512 or 768×768 WebP image)

3. **Package as ZIP:**
```bash
zip my-model-plugin.zip manifest.json thumbnail.webp
```

4. **Install via Plugin Manager UI**

### Manifest Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Display name (max 100 chars) |
| `description` | string | ❌ | Short description (max 500 chars) |
| `version` | string | ✅ | Semantic version (X.Y.Z) |
| `thumbnail` | string | ❌ | Thumbnail filename |
| `hf_repo` | string | ✅ | HuggingFace repo (author/model) |
| `type` | string | ✅ | `txt2img` or `img2img` |
| `base` | string | ✅ | `sd1.5`, `sd2.1`, `sdxl`, or `flux` |
| `recommended_steps` | integer | ❌ | Default steps (1-200) |
| `recommended_cfg` | number | ❌ | Default CFG scale (1-30) |
| `supports_negative_prompt` | boolean | ❌ | Negative prompt support |

### Plugin API Endpoints

```bash
# List all plugins
GET /api/plugins/list

# Install plugin
POST /api/plugins/install
Content-Type: multipart/form-data
Body: file=plugin.zip

# Enable plugin
POST /api/plugins/enable/{plugin_id}

# Disable plugin
POST /api/plugins/disable/{plugin_id}

# Uninstall plugin
DELETE /api/plugins/uninstall/{plugin_id}

# Get plugin details
GET /api/plugins/{plugin_id}

# WebSocket for download progress
WS /ws/download/{plugin_id}
```

### Starter Plugins

I.R.I.S. comes with **11 pre-installed plugins**:
- Dreamshaper 8 (versatile allround model)
- Anime Kawai Diffusion
- Abyssorangemix3 (semi-realistic anime)
- Counterfeit V3.0 (detailed illustrations)
- Openjourney (artistic style)
- Pixel Art Diffusion
- Anything V5 (classic anime)
- Stable Diffusion 2.1 (realistic photos)
- Waifu Diffusion
- Stable Diffusion 3.5 Medium (AMD GPU optimized)
- Animagine XL 3.1 (high-quality anime SDXL)

📖 **[View Plugin Development Guide](docs/PLUGIN_DEVELOPMENT.md)** - Complete guide for creating custom plugins.

---

## 🔌 API & WebSocket Support

- REST API for generation, gallery, system info
- WebSocket streams for:
  - Generation progress
  - Model download progress
  - Gallery updates
  - Multi-page synchronization

Perfect for **custom frontends**, automation, or external clients.

📖 **[View Full API Documentation](docs/API.md)** - Complete reference for REST endpoints, WebSocket messages, and error handling.

---

## 🧠 Designed for Modification

You are explicitly encouraged to:

* Replace the frontend entirely
* Add your own models or pipelines
* Build a token or subscription system
* Deploy in a private or public datacenter
* Run on NVIDIA, AMD, or Intel GPUs (experimental)
* Fork this into a commercial or closed product

**I.R.I.S. does not enforce a business model.**

---

## � License

**Creative Commons Attribution 4.0 (CC BY 4.0)**

You may use, modify, redistribute, and commercialize this project —
**attribution is required.**

See `LICENSE` for details.

---

## 🤝 Contributing

Contributions are welcome — from small fixes to major architectural changes.

Please read **CONTRIBUTING.md** before submitting a pull request.

---

## 🌍 Final Note

I.R.I.S. is not built to compete with cloud AI platforms.

It exists to **give control back** to developers and creators.

If you value:
- ownership over subscriptions
- experimentation over lock-in
- transparency over black boxes

then this project is for you.
