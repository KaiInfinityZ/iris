import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { getModelsList } from '../lib/api'
import { 
  type ModelInfo, 
  getModelConfig, 
  getDefaultResolution, 
  getDefaultSteps, 
  getDefaultCfg,
  supportsNegativePrompt 
} from '../modelsConfig'

// Types
export interface Model {
  id: string
  name: string
  image: string
  // Extended model info
  architecture?: string
  vram_gb?: number
  supports_negative_prompt?: boolean
  default_resolution?: { width: number; height: number }
  recommended_steps?: number
  recommended_cfg?: number
  prompt_style?: string
  token_limit?: number | null
  lora_supported?: boolean
  hf_url?: string
}

export interface Resolution {
  value: string
  label: string
  sublabel: string
  icon: string
}

export interface QualityPreset {
  name: string
  desc: string
  steps: number
  cfg: number
}

export interface Settings {
  model: string
  prompt: string
  negativePrompt: string
  resolution: string
  customWidth: number
  customHeight: number
  steps: number
  cfg: number
  seed: number | null
  seedLocked: boolean
  qualityPreset: string
}

export interface Generation {
  isGenerating: boolean
  progress: number
  currentStep: number
  totalSteps: number
  status: string
  currentImage: string | null
  sessionImages: string[]
}

// User override flags for model defaults
export interface UserOverrides {
  userOverrideSteps: boolean
  userOverrideCfg: boolean
  userOverrideResolution: boolean
}

export interface StoreState {
  settings: Settings
  generation: Generation
  models: Model[]
  modelsLoading: boolean
  // User override flags - track when user manually edits values
  userOverrides: UserOverrides
  // Current model config from modelsConfig
  currentModelConfig: ModelInfo | null
  setModel: (model: string) => void
  setPrompt: (prompt: string) => void
  setNegativePrompt: (negativePrompt: string) => void
  setResolution: (resolution: string) => void
  setCustomDimensions: (width: number, height: number) => void
  setCustomWidth: (customWidth: number) => void
  setCustomHeight: (customHeight: number) => void
  setSteps: (steps: number, isUserOverride?: boolean) => void
  setCfg: (cfg: number, isUserOverride?: boolean) => void
  setSeed: (seed: number | null) => void
  toggleSeedLock: () => void
  setQualityPreset: (preset: string) => void
  setGenerating: (isGenerating: boolean) => void
  setProgress: (progress: number, currentStep: number, totalSteps: number, status: string) => void
  setCurrentImage: (currentImage: string | null) => void
  addSessionImage: (image: string) => void
  randomizeSeed: () => void
  loadModels: () => Promise<void>
  setModels: (models: Model[]) => void
  // Reset overrides when model changes
  resetUserOverrides: () => void
  // Apply model defaults
  applyModelDefaults: (modelId: string) => void
}

export const models: Model[] = [
  // Models are now loaded dynamically from the API
  // Fallback models if API is unavailable:
  { id: 'tensorart_stable-diffusion-3.5-medium-turbo', name: 'SD 3.5 Medium Turbo', image: '/assets/thumbnails/thumbnail-sd-3.5-medium.webp' },
  { id: 'ojimi_anime-kawai-diffusion', name: 'Anime Kawaii Diffusion', image: '/assets/thumbnails/thumbnail-anime-kawaii-diffusion.webp' },
]

// Thumbnail map for model keys
const modelThumbnails: Record<string, string> = {
  'tensorart_stable-diffusion-3.5-medium-turbo': '/assets/thumbnails/thumbnail-sd-3.5-medium.webp',
  'ojimi_anime-kawai-diffusion': '/assets/thumbnails/thumbnail-anime-kawaii-diffusion.webp',
  'lykon_dreamshaper-8': '/assets/thumbnails/thumbnail-dreamshaper-8.webp',
  'stablediffusionapi_anything-v5': '/assets/thumbnails/thumbnail-anything-v5.webp',
  'stablediffusionapi_counterfeit-v30': '/assets/thumbnails/thumbnail-counterfeit-v3.0.webp',
  'prompthero_openjourney': '/assets/thumbnails/thumbnail-openjourney.webp',
  'hakurei_waifu-diffusion': '/assets/thumbnails/thumbnail-waifu-diffusion.webp',
  'seesee21_z-anime': '/assets/thumbnails/thumbnail-z-anime.webp',
  'nerijs_pixel-art-xl': '/assets/thumbnails/thumbnail-pixel-art-diffusion.webp',
}

export const resolutions: Resolution[] = [
  { value: '512x512', label: '1:1', sublabel: '512x512', icon: 'square' },
  { value: '512x768', label: '2:3', sublabel: '512×768', icon: 'portrait-narrow' },
  { value: '768x512', label: '3:2', sublabel: '768×512', icon: 'landscape-narrow' },
  { value: '768x1024', label: '3:4', sublabel: '768×1024', icon: 'portrait' },
  { value: '1024x768', label: '4:3', sublabel: '1024×768', icon: 'landscape' },
  { value: '720x1280', label: '9:16', sublabel: '720×1280', icon: 'portrait-tall' },
  { value: '1024x1024', label: 'HD', sublabel: '1024x1024', icon: 'square' },
  { value: 'custom', label: 'Custom', sublabel: 'manual', icon: 'custom' },
]

export const qualityPresets: Record<string, QualityPreset> = {
  fast: { name: 'Fast (Draft)', desc: '15 steps • Quick preview', steps: 15, cfg: 7 },
  balanced: { name: 'Balanced', desc: '35 steps • Good quality', steps: 35, cfg: 10 },
  high: { name: 'High Quality', desc: '50 steps • Detailed output', steps: 50, cfg: 12 },
  extreme: { name: 'Extreme', desc: '100 steps • Maximum quality', steps: 100, cfg: 15 },
}

export const useStore = create<StoreState>()(
  persist(
    (set, get) => ({
      settings: {
        model: 'ojimi_anime-kawai-diffusion',
        prompt: 'masterpiece, best quality, ultra-detailed, high resolution, cinematic lighting, 1girl, anime girl with cyan hair, cat ears, fox tail, wearing white tactical jacket, black pleated skirt, futuristic city background, soft bokeh, glowing eyes',
        negativePrompt: 'lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, deformed',
        resolution: '512x768',
        customWidth: 512,
        customHeight: 768,
        steps: 28,
        cfg: 7.5,
        seed: null,
        seedLocked: false,
        qualityPreset: 'balanced',
      },
      generation: {
        isGenerating: false,
        progress: 0,
        currentStep: 0,
        totalSteps: 0,
        status: 'Ready',
        currentImage: null,
        sessionImages: [],
      },
      models: [...models], // Start with fallback models
      modelsLoading: false,
      // Initialize user overrides
      userOverrides: {
        userOverrideSteps: false,
        userOverrideCfg: false,
        userOverrideResolution: false,
      },
      // Initialize current model config
      currentModelConfig: null,
      // Set model - loads defaults and resets user overrides
      setModel: (modelId) => {
        const modelConfig = getModelConfig(modelId)
        if (modelConfig) {
          set((state) => ({ 
            settings: { 
              ...state.settings, 
              model: modelId,
              steps: modelConfig.recommended_steps,
              cfg: modelConfig.recommended_cfg,
              resolution: `${modelConfig.default_resolution.width}x${modelConfig.default_resolution.height}`,
              customWidth: modelConfig.default_resolution.width,
              customHeight: modelConfig.default_resolution.height,
            },
            // Reset user overrides when model changes
            userOverrides: {
              userOverrideSteps: false,
              userOverrideCfg: false,
              userOverrideResolution: false,
            },
            // Store current model config
            currentModelConfig: modelConfig,
          }))
        } else {
          set((state) => ({ 
            settings: { ...state.settings, model: modelId },
            userOverrides: {
              userOverrideSteps: false,
              userOverrideCfg: false,
              userOverrideResolution: false,
            },
          }))
        }
      },
      setPrompt: (prompt) => set((state) => ({ settings: { ...state.settings, prompt } })),
      setNegativePrompt: (negativePrompt) => set((state) => ({ settings: { ...state.settings, negativePrompt } })),
      setResolution: (resolution) => set((state) => ({ settings: { ...state.settings, resolution } })),
      setCustomDimensions: (width, height) => set((state) => ({ 
        settings: { ...state.settings, customWidth: width, customHeight: height },
        // Mark as user override if not applying model defaults
        userOverrides: { ...state.userOverrides, userOverrideResolution: true }
      })),
      setCustomWidth: (customWidth) => set((state) => ({ 
        settings: { ...state.settings, customWidth },
        userOverrides: { ...state.userOverrides, userOverrideResolution: true }
      })),
      setCustomHeight: (customHeight) => set((state) => ({ 
        settings: { ...state.settings, customHeight },
        userOverrides: { ...state.userOverrides, userOverrideResolution: true }
      })),
      // setSteps with optional user override flag
      setSteps: (steps, isUserOverride = true) => set((state) => ({ 
        settings: { ...state.settings, steps },
        userOverrides: isUserOverride 
          ? { ...state.userOverrides, userOverrideSteps: true }
          : state.userOverrides
      })),
      setCfg: (cfg, isUserOverride = true) => set((state) => ({ 
        settings: { ...state.settings, cfg },
        userOverrides: isUserOverride 
          ? { ...state.userOverrides, userOverrideCfg: true }
          : state.userOverrides
      })),
      setSeed: (seed) => set((state) => ({ settings: { ...state.settings, seed: seed || null } })),
      toggleSeedLock: () => set((state) => ({ 
        settings: { ...state.settings, seedLocked: !state.settings.seedLocked } 
      })),
      setQualityPreset: (preset) => {
        const config = qualityPresets[preset]
        set((state) => ({ 
          settings: { 
            ...state.settings, 
            qualityPreset: preset,
            steps: config.steps,
            cfg: config.cfg,
          } 
        }))
      },
      setGenerating: (isGenerating) => set((state) => ({ 
        generation: { ...state.generation, isGenerating } 
      })),
      setProgress: (progress, currentStep, totalSteps, status) => set((state) => ({ 
        generation: { ...state.generation, progress, currentStep, totalSteps, status } 
      })),
      setCurrentImage: (currentImage) => set((state) => ({ 
        generation: { ...state.generation, currentImage } 
      })),
      addSessionImage: (image) => set((state) => ({ 
        generation: { ...state.generation, sessionImages: [image, ...state.generation.sessionImages] } 
      })),
      randomizeSeed: () => set((state) => {
        if (state.settings.seedLocked) return state
        return { settings: { ...state.settings, seed: Math.floor(Math.random() * 999999) + 1 } }
      }),
      loadModels: async () => {
        set({ modelsLoading: true })
        try {
          const response = await getModelsList()
          const apiModels = response.models
            .filter(m => m.enabled) // Only show enabled models
            .map(m => {
              // Get extended config from modelsConfig
              const extendedConfig = getModelConfig(m.key)
              return {
                id: m.key,
                name: m.description,
                image: modelThumbnails[m.key] || '/assets/thumbnails/thumbnail-sd-3.5-medium.webp',
                // Extended properties from modelsConfig
                architecture: extendedConfig?.architecture,
                vram_gb: extendedConfig?.vram_gb ?? m.vram_gb,
                supports_negative_prompt: extendedConfig?.supports_negative_prompt ?? true,
                default_resolution: extendedConfig?.default_resolution,
                recommended_steps: extendedConfig?.recommended_steps,
                recommended_cfg: extendedConfig?.recommended_cfg,
                prompt_style: extendedConfig?.prompt_style,
                token_limit: extendedConfig?.token_limit,
                lora_supported: extendedConfig?.lora_supported,
                hf_url: extendedConfig?.hf_url,
              }
            })
          
          if (apiModels.length > 0) {
            set({ models: apiModels, modelsLoading: false })
            // Also load model config for current model
            const currentModelId = get().settings.model
            const modelConfig = getModelConfig(currentModelId)
            if (modelConfig) {
              set({ currentModelConfig: modelConfig })
            }
          } else {
            // Keep fallback models if no models found
            set({ modelsLoading: false })
          }
        } catch (error) {
          console.error('Failed to load models from API:', error)
          // Keep fallback models on error
          set({ modelsLoading: false })
        }
      },
      setModels: (models) => set({ models }),
      // Reset user overrides (called when user selects a different model)
      resetUserOverrides: () => set({
        userOverrides: {
          userOverrideSteps: false,
          userOverrideCfg: false,
          userOverrideResolution: false,
        }
      }),
      // Apply model defaults - used by the reset button
      applyModelDefaults: (modelId: string) => {
        const modelConfig = getModelConfig(modelId)
        if (modelConfig) {
          set((state) => ({
            settings: {
              ...state.settings,
              steps: modelConfig.recommended_steps,
              cfg: modelConfig.recommended_cfg,
              resolution: `${modelConfig.default_resolution.width}x${modelConfig.default_resolution.height}`,
              customWidth: modelConfig.default_resolution.width,
              customHeight: modelConfig.default_resolution.height,
            },
            userOverrides: {
              userOverrideSteps: false,
              userOverrideCfg: false,
              userOverrideResolution: false,
            },
            currentModelConfig: modelConfig,
          }))
        }
      },
    }),
    {
      name: 'iris-settings',
      partialize: (state) => ({ settings: state.settings }),
    }
  )
)
