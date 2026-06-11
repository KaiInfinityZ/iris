"""
Models Configuration - Centralized model definitions for I.R.I.S.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Model configuration dataclass"""
    id: str
    description: str
    tier: str
    vram_gb: float
    recommended_steps: int
    recommended_cfg: float
    supports_negative_prompt: bool
    model_type: str
    architecture: str
    pipeline: str
    default_resolution: Dict[str, int]
    prompt_style: str
    token_limit: Optional[int]
    lora_supported: bool
    hf_url: str
    enabled: bool = True
    
    @classmethod
    def from_dict(cls, key: str, data: Dict[str, Any]) -> 'ModelConfig':
        """Create ModelConfig from dictionary"""
        return cls(
            id=data.get('id', ''),
            description=data.get('description', ''),
            tier=data.get('tier', 'B'),
            vram_gb=data.get('vram_gb', 3.5),
            recommended_steps=data.get('recommended_steps', 28),
            recommended_cfg=data.get('recommended_cfg', 7.5),
            supports_negative_prompt=data.get('supports_negative_prompt', True),
            model_type=data.get('model_type', 'sd15'),
            architecture=data.get('architecture', 'SD 1.5'),
            pipeline=data.get('pipeline', 'StableDiffusionPipeline'),
            default_resolution=data.get('default_resolution', {'width': 512, 'height': 768}),
            prompt_style=data.get('prompt_style', 'Natural language'),
            token_limit=data.get('token_limit', 77),
            lora_supported=data.get('lora_supported', True),
            hf_url=data.get('hf_url', ''),
            enabled=not data.get('disabled', False)
        )


class ModelsConfig:
    """Manages model configurations"""
    
    def __init__(self):
        self._configs: Dict[str, ModelConfig] = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load model configurations from JSON file"""
        config_path = Path(__file__).parent.parent.parent.parent / "static" / "config" / "models.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            models = data.get('models', {})
            
            for key, config_data in models.items():
                if not key.startswith('_') and not config_data.get('disabled', False):
                    self._configs[key] = ModelConfig.from_dict(key, config_data)
                    
        except Exception as e:
            print(f"Error loading model configs: {e}")
            # Fallback to empty configs
    
    def get(self, model_key: str) -> Optional[ModelConfig]:
        """Get model config by key"""
        return self._configs.get(model_key)
    
    def get_all(self) -> Dict[str, ModelConfig]:
        """Get all model configurations"""
        return self._configs.copy()
    
    def get_enabled(self) -> List[ModelConfig]:
        """Get all enabled model configurations"""
        return [cfg for cfg in self._configs.values() if cfg.enabled]
    
    def get_by_model_type(self, model_type: str) -> List[ModelConfig]:
        """Get models by type (sd15, sdxl, transformer)"""
        return [cfg for cfg in self._configs.values() 
                if cfg.model_type == model_type and cfg.enabled]
    
    def supports_negative_prompt(self, model_key: str) -> bool:
        """Check if model supports negative prompts"""
        config = self.get(model_key)
        return config.supports_negative_prompt if config else False
    
    def get_default_resolution(self, model_key: str) -> Dict[str, int]:
        """Get default resolution for a model"""
        config = self.get(model_key)
        return config.default_resolution if config else {'width': 512, 'height': 768}
    
    def get_default_steps(self, model_key: str) -> int:
        """Get default steps for a model"""
        config = self.get(model_key)
        return config.recommended_steps if config else 28
    
    def get_default_cfg(self, model_key: str) -> float:
        """Get default CFG scale for a model"""
        config = self.get(model_key)
        return config.recommended_cfg if config else 7.5
    
    def get_pipeline(self, model_key: str) -> str:
        """Get pipeline class name for a model"""
        config = self.get(model_key)
        return config.pipeline if config else 'StableDiffusionPipeline'
    
    def get_info(self, model_key: str) -> Optional[Dict[str, Any]]:
        """Get full model info for frontend display"""
        config = self.get(model_key)
        if not config:
            return None
        
        return {
            'key': model_key,
            'id': config.id,
            'description': config.description,
            'tier': config.tier,
            'vram_gb': config.vram_gb,
            'architecture': config.architecture,
            'pipeline': config.pipeline,
            'recommended_steps': config.recommended_steps,
            'recommended_cfg': config.recommended_cfg,
            'default_resolution': config.default_resolution,
            'supports_negative_prompt': config.supports_negative_prompt,
            'prompt_style': config.prompt_style,
            'token_limit': config.token_limit,
            'lora_supported': config.lora_supported,
            'hf_url': config.hf_url,
            'enabled': config.enabled
        }


# Singleton instance
models_config = ModelsConfig()


def get_model_config(model_key: str) -> Optional[ModelConfig]:
    """Helper function to get model config"""
    return models_config.get(model_key)


def get_all_models() -> Dict[str, ModelConfig]:
    """Helper function to get all models"""
    return models_config.get_all()


def get_model_info(model_key: str) -> Optional[Dict[str, Any]]:
    """Helper function to get model info for frontend"""
    return models_config.get_info(model_key)


def check_negative_prompt_support(model_key: str, negative_prompt: str) -> tuple[bool, str]:
    """
    Check if negative prompt can be used with the model.
    
    Returns:
        tuple: (can_use_negative_prompt, warning_message)
    """
    if not negative_prompt:
        return False, ""
    
    config = models_config.get(model_key)
    if not config:
        return True, ""
    
    if not config.supports_negative_prompt:
        return False, f"Model {config.description} does not support negative prompts. Ignoring negative_prompt."
    
    return True, ""