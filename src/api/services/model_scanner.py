"""
Model Scanner - Automatically discover and manage models
"""
import json
from pathlib import Path
from typing import Dict, List
from src.utils.logger import create_logger
from src.core.config import Config

logger = create_logger("ModelScanner")


class ModelScanner:
    """Scan and manage available models dynamically"""
    
    # Known model metadata (can be extended)
    KNOWN_MODELS = {
        "Ojimi/anime-kawai-diffusion": {
            "description": "Anime Kawaii Diffusion",
            "tier": "A",
            "vram_gb": 3.5,
            "quality_stars": 4,
            "speed_stars": 4,
            "best_for": "Cute anime style, kawaii characters",
            "recommended_steps": 28,
            "recommended_cfg": 7.5,
            "model_type": "sd15"
        },
        "tensorart/stable-diffusion-3.5-medium-turbo": {
            "description": "Stable Diffusion 3.5 Medium Turbo",
            "tier": "S",
            "vram_gb": 10,
            "quality_stars": 5,
            "speed_stars": 5,
            "best_for": "Fast high-quality generations",
            "recommended_steps": 20,
            "recommended_cfg": 4.5,
            "model_type": "sd3"
        },
        "Lykon/dreamshaper-8": {
            "description": "DreamShaper 8",
            "tier": "S",
            "vram_gb": 3.5,
            "quality_stars": 5,
            "speed_stars": 4,
            "best_for": "Everything - anime, realistic, fantasy",
            "recommended_steps": 30,
            "recommended_cfg": 7.5,
            "model_type": "sd15"
        },
        "stablediffusionapi/anything-v5": {
            "description": "Anything V5",
            "tier": "B",
            "vram_gb": 3.5,
            "quality_stars": 3,
            "speed_stars": 5,
            "best_for": "Quick generations, flat anime style",
            "recommended_steps": 25,
            "recommended_cfg": 7.0,
            "model_type": "sd15"
        },
        "stablediffusionapi/counterfeit-v30": {
            "description": "Counterfeit V3.0",
            "tier": "A",
            "vram_gb": 3.5,
            "quality_stars": 4,
            "speed_stars": 4,
            "best_for": "Digital art, detailed illustrations",
            "recommended_steps": 30,
            "recommended_cfg": 7.5,
            "model_type": "sd15"
        },
        "prompthero/openjourney": {
            "description": "OpenJourney",
            "tier": "A",
            "vram_gb": 3.5,
            "quality_stars": 4,
            "speed_stars": 4,
            "best_for": "Midjourney-like artistic style",
            "recommended_steps": 30,
            "recommended_cfg": 7.0,
            "model_type": "sd15"
        },
        "hakurei/waifu-diffusion": {
            "description": "Waifu Diffusion",
            "tier": "B",
            "vram_gb": 3.5,
            "quality_stars": 3,
            "speed_stars": 5,
            "best_for": "Classic anime style, waifus",
            "recommended_steps": 28,
            "recommended_cfg": 7.5,
            "model_type": "sd15"
        },
        "cagliostrolab/animagine-xl-4.0": {
            "description": "Animagine XL 4.0",
            "tier": "S",
            "vram_gb": 8,
            "quality_stars": 5,
            "speed_stars": 3,
            "best_for": "High-quality anime art, SDXL-based",
            "recommended_steps": 35,
            "recommended_cfg": 7.5,
            "model_type": "sdxl"
        },
        "nerijs/pixel-art-xl": {
            "description": "Pixel Art XL",
            "tier": "C",
            "vram_gb": 4,
            "quality_stars": 3,
            "speed_stars": 3,
            "best_for": "Pixel art style images",
            "recommended_steps": 30,
            "recommended_cfg": 7.0,
            "model_type": "sd15"
        },
        "stablediffusionapi/pixel-art-diffusion-xl": {
            "description": "Pixel Art Diffusion XL",
            "tier": "C",
            "vram_gb": 6,
            "quality_stars": 3,
            "speed_stars": 3,
            "best_for": "Pixel art style, SDXL-based",
            "recommended_steps": 30,
            "recommended_cfg": 7.0,
            "model_type": "sdxl"
        },
        "stalkeryga/HentaiDiffusion": {
            "description": "Hentai Diffusion",
            "tier": "B",
            "vram_gb": 3.5,
            "quality_stars": 4,
            "speed_stars": 4,
            "best_for": "Adult anime art (18+)",
            "recommended_steps": 28,
            "recommended_cfg": 7.5,
            "model_type": "sd15"
        },
        "purplesmartai/pony-v7-base": {
            "description": "Pony Diffusion V7",
            "tier": "A",
            "vram_gb": 8,
            "quality_stars": 4,
            "speed_stars": 3,
            "best_for": "Anthropomorphic and furry art",
            "recommended_steps": 30,
            "recommended_cfg": 7.5,
            "model_type": "sdxl"
        },
        "SeeSee21/Z-Anime": {
            "description": "Z-Anime",
            "tier": "A",
            "vram_gb": 9,
            "quality_stars": 5,
            "speed_stars": 3,
            "best_for": "High-quality anime art with modern aesthetics",
            "recommended_steps": 28,
            "recommended_cfg": 7.5,
            "model_type": "sd3",
            "subfolder": "diffusers"
        },
    }
    
    @staticmethod
    def scan_local_models() -> List[Dict]:
        """
        Scan local models directory and return list of found models.
        
        Returns:
            List of dicts with model info: {model_id, local_path, key}
        """
        # HuggingFace stores models in the hub subdirectory
        models_path = Path(Config.HUGGINGFACE_MODELS_PATH) / "hub"
        found_models = []
        
        if not models_path.exists():
            logger.warning(f"Models directory not found: {models_path}")
            return []
        
        # Scan for models--org--name directories
        for model_dir in models_path.glob("models--*"):
            if not model_dir.is_dir():
                continue
            
            # Parse directory name: models--org--name -> org/name
            dir_name = model_dir.name
            if not dir_name.startswith("models--"):
                continue
            
            parts = dir_name.replace("models--", "").split("--")
            if len(parts) < 2:
                continue
            
            model_id = "/".join(parts)
            
            # Generate key (org_name format)
            key = "_".join(parts).lower()
            
            # Check if model has actual files (snapshots directory)
            snapshots_dir = model_dir / "snapshots"
            if not snapshots_dir.exists():
                logger.debug(f"Skipping {model_id}: no snapshots directory")
                continue
            
            found_models.append({
                "model_id": model_id,
                "local_path": str(model_dir),
                "key": key
            })
        
        return found_models
    
    @staticmethod
    def generate_model_config(model_id: str, key: str, enabled: bool = True) -> Dict:
        """
        Generate configuration for a model.
        
        Args:
            model_id: HuggingFace model ID (e.g., "Ojimi/anime-kawai-diffusion")
            key: Model key for internal use (e.g., "ojimi_anime_kawai_diffusion")
            enabled: Whether model should be enabled by default
        
        Returns:
            Model configuration dict
        """
        # Get known metadata or use defaults
        metadata = ModelScanner.KNOWN_MODELS.get(model_id, {})
        
        config = {
            "id": model_id,
            "description": metadata.get("description", f"Model: {model_id}"),
            "tier": metadata.get("tier", "C"),
            "vram_gb": metadata.get("vram_gb", 4.0),
            "quality_stars": metadata.get("quality_stars", 3),
            "speed_stars": metadata.get("speed_stars", 3),
            "best_for": metadata.get("best_for", "General image generation"),
            "notes": metadata.get("notes", "Auto-detected model"),
            "recommended_steps": metadata.get("recommended_steps", 30),
            "recommended_cfg": metadata.get("recommended_cfg", 7.5),
            "supports_negative_prompt": True,
            "model_type": metadata.get("model_type", "sd15"),
        }
        
        # Add subfolder if specified
        if "subfolder" in metadata:
            config["subfolder"] = metadata["subfolder"]
        
        # Mark as disabled if not enabled
        if not enabled:
            config["disabled"] = True
        
        return config
    
    @staticmethod
    def load_enabled_models() -> Dict[str, bool]:
        """
        Load enabled/disabled state from models.json
        
        Returns:
            Dict mapping model keys to enabled state
        """
        config_path = Config.CONFIG_DIR / "models.json"
        
        if not config_path.exists():
            return {}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                models = data.get("models", {})
                
                enabled_states = {}
                for key, config in models.items():
                    # Skip entries starting with _ (disabled placeholder)
                    if key.startswith("_"):
                        continue
                    
                    # Check if disabled
                    is_enabled = not config.get("disabled", False)
                    enabled_states[key] = is_enabled
                
                return enabled_states
        except Exception as e:
            logger.error(f"Failed to load enabled models: {e}")
            return {}
    
    @staticmethod
    def update_models_json(auto_discovered: bool = True):
        """
        Update models.json with scanned models.
        
        Args:
            auto_discovered: If True, add all found models. If False, only update existing.
        """
        config_path = Config.CONFIG_DIR / "models.json"
        
        # Load existing config
        existing_data = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load existing models.json: {e}")
        
        # Get current enabled states
        enabled_states = ModelScanner.load_enabled_models()
        
        # Scan local models
        found_models = ModelScanner.scan_local_models()
        
        logger.info(f"Found {len(found_models)} models in local directory")
        
        # Build new models dict
        models = {}
        
        for model_info in found_models:
            key = model_info["key"]
            model_id = model_info["model_id"]
            
            # Check if model should be enabled
            is_enabled = enabled_states.get(key, auto_discovered)
            
            # Generate config
            config = ModelScanner.generate_model_config(model_id, key, is_enabled)
            models[key] = config
        
        # Preserve metadata
        metadata = existing_data.get("metadata", {
            "version": "1.0.0",
            "last_updated": "auto-generated",
            "tiers": {
                "S": "Best Quality & Versatility",
                "A": "High Quality",
                "B": "Good Quality, Fast",
                "C": "Experimental"
            },
            "notes": {
                "vram_requirements": "Approximate VRAM at 512x768 resolution",
                "auto_discovery": "Models auto-discovered from local directory",
                "optimization_note": "All models support memory optimizations"
            }
        })
        
        # Write updated config
        output = {
            "models": models,
            "metadata": metadata
        }
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            logger.success(f"Updated models.json with {len(models)} models")
            return True
        except Exception as e:
            logger.error(f"Failed to write models.json: {e}")
            return False
    
    @staticmethod
    def set_model_enabled(model_key: str, enabled: bool) -> bool:
        """
        Enable or disable a specific model.
        
        Args:
            model_key: Model key (e.g., "anime_kawai")
            enabled: True to enable, False to disable
        
        Returns:
            True if successful
        """
        config_path = Config.CONFIG_DIR / "models.json"
        
        if not config_path.exists():
            logger.error("models.json not found")
            return False
        
        try:
            # Load config
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            models = data.get("models", {})
            
            if model_key not in models:
                logger.error(f"Model {model_key} not found in config")
                return False
            
            # Update disabled flag
            if enabled:
                models[model_key].pop("disabled", None)
            else:
                models[model_key]["disabled"] = True
            
            # Save config
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Model {model_key} {'enabled' if enabled else 'disabled'}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update model state: {e}")
            return False
