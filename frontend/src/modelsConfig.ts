/**
 * Models Configuration - Centralized model definitions for I.R.I.S. Frontend
 */

export interface Resolution {
  width: number
  height: number
}

export interface ModelConfig {
  key: string
  id: string
  description: string
  tier: string
  vram_gb: number
  architecture: string
  pipeline: string
  recommended_steps: number
  recommended_cfg: number
  default_resolution: Resolution
  supports_negative_prompt: boolean
  prompt_style: string
  token_limit: number | null
  lora_supported: boolean
  hf_url: string
  enabled: boolean
}

// Extended model info for UI display
export interface ModelInfo extends ModelConfig {
  best_for: string
  quality_stars: number
  speed_stars: number
  notes: string
}

export interface ModelsConfigData {
  models: Record<string, ModelInfo>
  metadata: {
    version: string
    last_updated: string
    tiers: Record<string, string>
    notes: Record<string, string>
  }
}

// Default model configurations (fallback if API unavailable)
export const defaultModelsConfig: ModelsConfigData = {
  models: {
    'cagliostrolab_animagine-xl-4.0': {
      key: 'cagliostrolab_animagine-xl-4.0',
      id: 'cagliostrolab/animagine-xl-4.0',
      description: 'Animagine XL 4.0',
      tier: 'S',
      vram_gb: 8,
      architecture: 'SDXL',
      pipeline: 'StableDiffusionXLPipeline',
      recommended_steps: 35,
      recommended_cfg: 7.5,
      default_resolution: { width: 1024, height: 1024 },
      supports_negative_prompt: true,
      prompt_style: 'Danbooru tags',
      token_limit: 77,
      lora_supported: true,
      hf_url: 'https://huggingface.co/cagliostrolab/animagine-xl-4.0',
      enabled: true,
      best_for: 'High-quality anime art, SDXL-based',
      quality_stars: 5,
      speed_stars: 3,
      notes: 'Auto-detected model'
    },
    'ojimi_anime-kawai-diffusion': {
      key: 'ojimi_anime-kawai-diffusion',
      id: 'Ojimi/anime-kawai-diffusion',
      description: 'Anime Kawaii Diffusion',
      tier: 'A',
      vram_gb: 2,
      architecture: 'SD 1.5',
      pipeline: 'StableDiffusionPipeline',
      recommended_steps: 28,
      recommended_cfg: 7.5,
      default_resolution: { width: 512, height: 768 },
      supports_negative_prompt: true,
      prompt_style: 'Danbooru tags',
      token_limit: 77,
      lora_supported: true,
      hf_url: 'https://huggingface.co/Ojimi/anime-kawai-diffusion',
      enabled: true,
      best_for: 'Cute anime style, kawaii characters',
      quality_stars: 4,
      speed_stars: 5,
      notes: 'Lightweight SD 1.5 fine-tune for kawaii anime art. Requires ~2GB VRAM.'
    },
    'lykon_dreamshaper-8': {
      key: 'lykon_dreamshaper-8',
      id: 'Lykon/dreamshaper-8',
      description: 'DreamShaper 8',
      tier: 'S',
      vram_gb: 3.5,
      architecture: 'SD 1.5',
      pipeline: 'StableDiffusionPipeline',
      recommended_steps: 30,
      recommended_cfg: 7.5,
      default_resolution: { width: 512, height: 768 },
      supports_negative_prompt: true,
      prompt_style: 'Natural language or Danbooru tags',
      token_limit: 77,
      lora_supported: true,
      hf_url: 'https://huggingface.co/Lykon/dreamshaper-8',
      enabled: true,
      best_for: 'Everything - anime, realistic, fantasy',
      quality_stars: 5,
      speed_stars: 4,
      notes: 'Auto-detected model'
    },
    'onomaai_illustrious-xl': {
      key: 'onomaai_illustrious-xl',
      id: 'OnomaAIResearch/Illustrious-xl-early-release-v0',
      description: 'Illustrious XL v1.0',
      tier: 'S',
      vram_gb: 7,
      architecture: 'SDXL',
      pipeline: 'StableDiffusionXLPipeline',
      recommended_steps: 28,
      recommended_cfg: 7.0,
      default_resolution: { width: 1024, height: 1024 },
      supports_negative_prompt: true,
      prompt_style: 'Danbooru tags',
      token_limit: 77,
      lora_supported: true,
      hf_url: 'https://huggingface.co/OnomaAIResearch/Illustrious-xl-early-release-v0',
      enabled: true,
      best_for: 'High-quality anime/illustration SDXL',
      quality_stars: 5,
      speed_stars: 3,
      notes: 'High-quality anime/illustration SDXL model by OnomaAI. Trained on Danbooru2023. Supports up to 1536x1536 natively.'
    },
    'astraliteheart_pony-diffusion-v6-xl': {
      key: 'astraliteheart_pony-diffusion-v6-xl',
      id: 'AstraliteHeart/pony-diffusion-v6-xl',
      description: 'Pony Diffusion V6 XL',
      tier: 'S',
      vram_gb: 7,
      architecture: 'SDXL',
      pipeline: 'StableDiffusionXLPipeline',
      recommended_steps: 25,
      recommended_cfg: 7.0,
      default_resolution: { width: 1024, height: 1024 },
      supports_negative_prompt: true,
      prompt_style: 'Score tags (score_9, score_8_up)',
      token_limit: 77,
      lora_supported: true,
      hf_url: 'https://huggingface.co/AstraliteHeart/pony-diffusion-v6-xl',
      enabled: true,
      best_for: 'Versatile SDXL anime/character model',
      quality_stars: 5,
      speed_stars: 4,
      notes: 'Versatile SDXL anime/character model. Requires score tags at prompt start. Large LoRA community.'
    },
    'anima_anima-2b': {
      key: 'anima_anima-2b',
      id: 'AnimaLab/anima',
      description: 'Anima 2B',
      tier: 'A',
      vram_gb: 4,
      architecture: 'Transformer (Cosmos-based)',
      pipeline: 'DiffusionPipeline',
      recommended_steps: 20,
      recommended_cfg: 5.0,
      default_resolution: { width: 768, height: 1024 },
      supports_negative_prompt: false,
      prompt_style: 'Natural language',
      token_limit: null,
      lora_supported: false,
      hf_url: 'https://huggingface.co/AnimaLab/anima',
      enabled: true,
      best_for: 'Lightweight transformer-based anime model',
      quality_stars: 4,
      speed_stars: 5,
      notes: 'Lightweight 2B transformer-based anime model. No UNet. No negative prompt support. Fast inference.'
    },
    'hakurei_waifu-diffusion': {
      key: 'hakurei_waifu-diffusion',
      id: 'hakurei/waifu-diffusion',
      description: 'Waifu Diffusion',
      tier: 'B',
      vram_gb: 3.5,
      architecture: 'SD 1.5',
      pipeline: 'StableDiffusionPipeline',
      recommended_steps: 28,
      recommended_cfg: 7.5,
      default_resolution: { width: 512, height: 768 },
      supports_negative_prompt: true,
      prompt_style: 'Danbooru tags',
      token_limit: 77,
      lora_supported: true,
      hf_url: 'https://huggingface.co/hakurei/waifu-diffusion',
      enabled: true,
      best_for: 'Classic anime style, waifus',
      quality_stars: 3,
      speed_stars: 5,
      notes: 'Auto-detected model'
    }
  },
  metadata: {
    version: '2.0.0',
    last_updated: '2026-06-10',
    tiers: {
      'S': 'Best Quality & Versatility',
      'A': 'High Quality',
      'B': 'Good Quality, Fast',
      'C': 'Experimental'
    },
    notes: {
      vram_requirements: 'Approximate VRAM at 512x768 resolution',
      sdxl_warning: 'SDXL models (>8GB VRAM) may cause instability on 16GB systems',
      optimization_note: 'All models support memory optimizations (VAE slicing/tiling, CPU offload)'
    }
  }
}

// Helper functions
export function getModelConfig(modelKey: string): ModelInfo | undefined {
  return defaultModelsConfig.models[modelKey]
}

export function getAllModels(): ModelInfo[] {
  return Object.values(defaultModelsConfig.models).filter(m => m.enabled)
}

export function getModelsByType(type: 'sd15' | 'sdxl' | 'transformer'): ModelInfo[] {
  const typeMap: Record<string, string> = {
    'sd15': 'SD 1.5',
    'sdxl': 'SDXL',
    'transformer': 'Transformer'
  }
  return getAllModels().filter(m => m.architecture === typeMap[type])
}

export function supportsNegativePrompt(modelKey: string): boolean {
  const model = getModelConfig(modelKey)
  return model?.supports_negative_prompt ?? true
}

export function getDefaultResolution(modelKey: string): Resolution {
  const model = getModelConfig(modelKey)
  return model?.default_resolution ?? { width: 512, height: 768 }
}

export function getDefaultSteps(modelKey: string): number {
  const model = getModelConfig(modelKey)
  return model?.recommended_steps ?? 28
}

export function getDefaultCfg(modelKey: string): number {
  const model = getModelConfig(modelKey)
  return model?.recommended_cfg ?? 7.5
}

export function getMaxResolution(architecture: string): Resolution {
  switch (architecture) {
    case 'SD 1.5':
      return { width: 512, height: 768 }
    case 'SDXL':
      return { width: 1536, height: 1536 }
    case 'Transformer (Cosmos-based)':
      return { width: 1024, height: 1024 }
    default:
      return { width: 1024, height: 1024 }
  }
}

export function getVramRequirement(architecture: string): string {
  switch (architecture) {
    case 'SD 1.5':
      return '~2-4GB VRAM'
    case 'SDXL':
      return '~6-8GB VRAM'
    case 'Transformer (Cosmos-based)':
      return '~4GB VRAM'
    default:
      return '~4GB VRAM'
  }
}

export function getTokenLimitInfo(modelKey: string): string {
  const model = getModelConfig(modelKey)
  if (!model) return '77 tokens'
  if (model.token_limit === null) return 'Unlimited'
  return `${model.token_limit} tokens`
}