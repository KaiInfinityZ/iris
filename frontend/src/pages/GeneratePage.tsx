import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { clsx } from 'clsx'
import { useStore, resolutions, qualityPresets } from '../store/useStore'
import { getOutputGallery, getImageUrl, getWebSocketUrl, getSettings, upscaleImage, createVariation, Settings } from '../lib/api'
import { useIsMobile } from '../hooks/useMediaQuery'
import GeneratePageMobile from './GeneratePageMobile'
import ModelSelector from '../components/ModelSelector'
import PromptInput from '../components/PromptInput'
import ResolutionSelector from '../components/ResolutionSelector'
import QualityPresetSelector from '../components/QualityPresetSelector'

// Types
interface PromptCategory {
  [key: string]: string[]
}

interface PromptHistoryEntry {
  id: number
  prompt: string
  negativePrompt?: string
  seed?: number
  resolution?: string
  steps?: number
  cfg?: number
  timestamp: string
}

interface UpscaleResult {
  success: boolean
  filename?: string
  image?: string
  error?: string
}

interface GenerationTimeData {
  times: number[]
  avg: number
}

interface BenchmarkData {
  [key: string]: GenerationTimeData
}

// Benchmark System - stores generation times per configuration
function getBenchmarkData() {
  try {
    return JSON.parse(localStorage.getItem('iris_benchmark_data') || '{}')
  } catch { return {} }
}

function saveBenchmarkData(data) {
  localStorage.setItem('iris_benchmark_data', JSON.stringify(data))
}

function getBenchmarkKey(model, width, height, steps) {
  const mp = Math.round((width * height) / 100000) / 10
  return `${model}_${mp}mp_${steps}s`
}

function saveBenchmark(model, width, height, steps, timeSeconds) {
  const data = getBenchmarkData()
  const key = getBenchmarkKey(model, width, height, steps)
  if (!data[key]) data[key] = { times: [], avg: 0 }
  data[key].times.push(timeSeconds)
  if (data[key].times.length > 5) data[key].times.shift()
  data[key].avg = data[key].times.reduce((a, b) => a + b, 0) / data[key].times.length
  saveBenchmarkData(data)
}

// Prompt History Functions - now loads from server API
async function loadPromptHistoryFromServer() {
  try {
    const response = await fetch('/api/prompts-history?limit=50')
    const data = await response.json()
    return data.history || []
  } catch (e) {
    console.error('Failed to load prompt history:', e)
    return []
  }
}

function getRandomPrompt() {
  const baseTags = "masterpiece, best quality, ultra-detailed, high resolution, cinematic lighting"
  const prompts = {
    anime: [
      "1girl, anime girl, cyan hair, cat ears, fox tail, white tactical jacket, black pleated skirt, futuristic city, soft bokeh, glowing eyes",
      "1girl, anime girl, long pink hair, school uniform, sunset sky, rooftop, wind blowing hair, emotional atmosphere",
      "1girl, anime girl, short silver hair, headphones, oversized hoodie, night city, neon signs, lo-fi vibe",
    ],
    cyberpunk: [
      "1girl, cyberpunk, neon blue hair, tech armor, glowing circuit tattoos, night city, rain, neon reflections",
      "1girl, cyberpunk hacker, short purple hair, visor glasses, holographic UI, dark alley, neon lights",
    ],
    fantasy: [
      "1girl, elf archer, silver hair, long braid, pointed ears, green leather armor, mystical forest, sunlight rays",
      "1girl, witch, purple robe, wide wizard hat, floating spell circle, full moon, magic particles",
    ],
  }
  const categories = Object.keys(prompts)
  const category = categories[Math.floor(Math.random() * categories.length)]
  const prompt = prompts[category][Math.floor(Math.random() * prompts[category].length)]
  return `${baseTags}, ${prompt}`
}

export default function GeneratePage() {
  // Check if mobile
  const isMobile = useIsMobile()
  
  // Render mobile version on small screens
  if (isMobile) {
    return <GeneratePageMobile />
  }

  // Desktop version continues below
  const { settings, generation, setModel, setPrompt, setNegativePrompt, setResolution,
    setSteps, setCfg, setSeed, toggleSeedLock, setQualityPreset, setGenerating,
    setProgress, setCurrentImage, addSessionImage, randomizeSeed,
    setCustomWidth, setCustomHeight, loadModels, models: storeModels } = useStore()
  
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [activeTab, setActiveTab] = useState('recent')
  const [outputImages, setOutputImages] = useState<string[]>([])
  const [generationTime, setGenerationTime] = useState(0)
  const [promptHistory, setPromptHistoryState] = useState<PromptHistoryEntry[]>([])
  const [aspectLocked, setAspectLocked] = useState(false)
  const [lastAspectRatio, setLastAspectRatio] = useState(1)
  const [showUpscalePopup, setShowUpscalePopup] = useState(false)
  const [upscaleScale, setUpscaleScale] = useState(2)
  const [upscaleMethod, setUpscaleMethod] = useState('realesrgan')
  const [isUpscaling, setIsUpscaling] = useState(false)
  const [showVariationPopup, setShowVariationPopup] = useState(false)
  const [variationStrength, setVariationStrength] = useState(0.5)
  const [isCreatingVariation, setIsCreatingVariation] = useState(false)
  const [eta, setEta] = useState<number | null>(null)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false) // Mobile menu state
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<number | null>(null)
  const genStartRef = useRef<number | null>(null)
  const upscalePopupRef = useRef<HTMLDivElement | null>(null)
  const variationPopupRef = useRef<HTMLDivElement | null>(null)

  // Calculate custom resolution info
  const customWidth = settings.customWidth || 512
  const customHeight = settings.customHeight || 512

  // Get current dimensions
  const getCurrentDimensions = () => {
    if (settings.resolution === 'custom') {
      return [customWidth, customHeight]
    }
    return settings.resolution.split('x').map(Number)
  }

  useEffect(() => {
    loadOutputGallery()
    loadPromptHistory()
    loadModels() // Load models from API on mount

    return () => {}
  }, [])

  // Click outside handler for upscale popup
  useEffect(() => {
    function handleClickOutside(event) {
      if (upscalePopupRef.current && !upscalePopupRef.current.contains(event.target)) {
        setShowUpscalePopup(false)
      }
    }
    if (showUpscalePopup) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showUpscalePopup])

  // Click outside handler for variation popup
  useEffect(() => {
    function handleClickOutside(event) {
      if (variationPopupRef.current && !variationPopupRef.current.contains(event.target)) {
        setShowVariationPopup(false)
      }
    }
    if (showVariationPopup) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showVariationPopup])

  async function loadPromptHistory() {
    const history = await loadPromptHistoryFromServer()
    setPromptHistoryState(history)
  }


  // Timer effect - only depends on isGenerating, not progress
  useEffect(() => {
    if (generation.isGenerating) {
      // Only set start time when generation actually starts
      if (!genStartRef.current) {
        genStartRef.current = Date.now()
      }
      timerRef.current = window.setInterval(() => {
        const elapsed = (Date.now() - genStartRef.current) / 1000
        setGenerationTime(elapsed)
      }, 100)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
      genStartRef.current = null // Reset for next generation
      setEta(null)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [generation.isGenerating])

  // ETA calculation - separate effect for progress updates
  useEffect(() => {
    if (generation.isGenerating && generation.progress > 5 && genStartRef.current) {
      const elapsed = (Date.now() - genStartRef.current) / 1000
      const remainingProgress = 100 - generation.progress
      const timePerPercent = elapsed / generation.progress
      setEta(Math.max(1, Math.round(timePerPercent * remainingProgress)))
    }
  }, [generation.progress, generation.isGenerating])

  async function loadOutputGallery() {
    try {
      const data = await getOutputGallery()
      setOutputImages(data.images || [])
    } catch (e) { console.error('Failed to load gallery:', e) }
  }

  function handleCustomWidthChange(value) {
    // Allow any value between 256 and 2048, no rounding
    const newWidth = Math.max(256, Math.min(2048, Math.floor(value)))
    setCustomWidth(newWidth)
    if (aspectLocked && lastAspectRatio) {
      const newHeight = Math.max(256, Math.min(2048, Math.floor(newWidth / lastAspectRatio)))
      setCustomHeight(newHeight)
    }
  }

  function handleCustomHeightChange(value) {
    // Allow any value between 256 and 2048, no rounding
    const newHeight = Math.max(256, Math.min(2048, Math.floor(value)))
    setCustomHeight(newHeight)
    if (aspectLocked && lastAspectRatio) {
      const newWidth = Math.max(256, Math.min(2048, Math.floor(newHeight * lastAspectRatio)))
      setCustomWidth(newWidth)
    }
  }

  function toggleAspectLockFn() {
    if (!aspectLocked) {
      setLastAspectRatio(customWidth / customHeight)
    }
    setAspectLocked(!aspectLocked)
  }

  function swapDimensions() {
    const w = customWidth, h = customHeight
    setCustomWidth(h)
    setCustomHeight(w)
  }

  function handleGenerate() {
    if (generation.isGenerating) return
    
    setGenerating(true)
    setProgress(0, 0, settings.steps, 'Initializing...')
    setGenerationTime(0)
    setEta(null)

    // Close any existing WebSocket connection first
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const wsUrl = getWebSocketUrl()
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      const [width, height] = getCurrentDimensions()
      
      const request = {
        prompt: settings.prompt,
        negative_prompt: settings.negativePrompt,
        style: settings.model,
        width, height,
        steps: settings.steps,
        cfg_scale: settings.cfg,
        seed: settings.seed,
      }
      ws.send(JSON.stringify(request))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'progress') {
        const progress = data.progress || (data.step / data.total_steps * 100) || 0
        let status = 'Generating...'
        if (progress < 10) status = 'Loading model...'
        else if (progress < 30) status = 'Warming up...'
        else if (progress < 60) status = 'Generating details...'
        else if (progress < 85) status = 'Refining image...'
        else status = 'Finishing up...'
        setProgress(progress, data.step || 0, data.total_steps || settings.steps, status)
      } else if (data.type === 'completed') {
        const [width, height] = getCurrentDimensions()
        const finalTime = data.generation_time || generationTime
        saveBenchmark(settings.model, width, height, settings.steps, finalTime)
        
        // Reload prompt history from server (server saves it automatically)
        loadPromptHistory()
        
        // Use filename instead of base64 for better upscale/variation support
        const imageRef = data.filename || data.image
        setCurrentImage(imageRef)
        addSessionImage(imageRef)
        setGenerating(false)
        setProgress(100, settings.steps, settings.steps, 'Complete!')
        loadOutputGallery()
      } else if (data.type === 'error') {
        setGenerating(false)
        setProgress(0, 0, 0, 'Error: ' + (data.message || 'Unknown error'))
      } else if (data.type === 'started') {
        setProgress(0, 0, settings.steps, 'Starting generation...')
      }
    }

    ws.onerror = () => { setGenerating(false); setProgress(0, 0, 0, 'Connection error') }
    ws.onclose = () => { wsRef.current = null }
  }

  function handleDownload() {
    if (!generation.currentImage) return
    
    // Get original filename to detect image type
    const originalFilename = generation.currentImage.split('/').pop() || ''
    
    // Detect image type from filename prefix
    let imageType = 'gen'  // default: generated
    let typePrefix = ''
    
    if (originalFilename.startsWith('up') || originalFilename.startsWith('upscaled')) {
      imageType = 'upscaled'
      // Extract scale from filename (e.g., up2x_, up4x_)
      const scaleMatch = originalFilename.match(/^up(\d+)x_/)
      typePrefix = scaleMatch ? `up${scaleMatch[1]}x_` : 'up_'
    } else if (originalFilename.startsWith('var_') || originalFilename.startsWith('variation_')) {
      imageType = 'variation'
      typePrefix = 'var_'
    }
    
    // Generate descriptive filename
    // Format: iris_[type_][prompt]-[seed]-[steps]-[cfg]-[resolution]-[model].png
    
    // Extract important/descriptive parts from prompt
    const boringWords = [
      'masterpiece', 'best quality', 'ultra-detailed', 'high resolution', 'high quality',
      'detailed', 'intricate', 'beautiful', 'stunning', 'amazing', 'gorgeous',
      'cinematic lighting', 'cinematic', 'lighting', 'soft lighting', 'dramatic lighting',
      'bokeh', 'soft bokeh', 'depth of field', 'dof', 'sharp focus', 'sharp',
      '8k', '4k', 'hd', 'uhd', 'hdr', 'raw photo', 'photorealistic',
      'highly detailed', 'extremely detailed', 'very detailed', 'super detailed',
      'professional', 'award winning', 'trending on artstation', 'artstation',
      'concept art', 'digital art', 'illustration', 'painting', 'artwork',
      'perfect', 'flawless', 'realistic', 'hyperrealistic', 'ultra realistic',
      'absurdres', 'highres', 'incredibly absurdres', 'huge filesize',
      'wallpaper', 'official art', 'key visual',
    ]
    
    // Split by comma first to keep phrases together
    const phrases = settings.prompt
      .toLowerCase()
      .split(',')
      .map(p => p.trim())
      .filter(p => p.length > 0)
      .filter(p => !boringWords.some(bw => p === bw || p.startsWith(bw + ' ')))
    
    // Take first 8 phrases and join them
    const promptShort = phrases
      .slice(0, 8)
      .join('_')
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9_-]/g, '')
      .substring(0, 80) || 'image'
    
    // Get resolution
    let resolution = settings.resolution
    if (resolution === 'custom') {
      resolution = `${settings.customWidth}x${settings.customHeight}`
    }
    
    // Model abbreviation
    const modelAbbrev = {
      'animagine_xl': 'anmgn',
      'anime_kawai': 'kawai',
      'anything_v5': 'any5',
      'aom3': 'aom3',
      'counterfeit_v3': 'cf3',
      'dreamshaper_8': 'ds8',
      'openjourney': 'oj',
      'pixel_art': 'pixel',
      'stable_diffusion_2_1': 'sd21',
      'stable_diffusion_3_5': 'sd35',
      'waifu_diffusion': 'waifu',
    }[settings.model] || settings.model.substring(0, 5)
    
    // Get seed from filename if available, otherwise use settings
    let seed = settings.seed || 'rnd'
    const seedMatch = originalFilename.match(/_(\d+)_s\d+\.png$/)
    if (seedMatch) seed = seedMatch[1]
    
    // Build filename with type prefix
    const downloadName = `iris_${typePrefix}${promptShort}-${seed}-s${settings.steps}-cfg${settings.cfg}-${resolution}-${modelAbbrev}.png`
    
    const link = document.createElement('a')
    link.href = getImageUrl(generation.currentImage)
    link.download = downloadName
    link.click()
  }

  async function handleUpscale() {
    if (!generation.currentImage || isUpscaling) return
    
    // Extract filename from currentImage (could be base64 or filename)
    let filename = generation.currentImage
    if (filename.startsWith('data:')) {
      alert('Cannot upscale base64 image directly. Please select an image from the library.')
      return
    }
    // If it's a URL path, extract just the filename
    if (filename.includes('/')) {
      filename = filename.split('/').pop()
    }
    
    // Close popup immediately before starting upscale
    setShowUpscalePopup(false)
    setIsUpscaling(true)
    
    try {
      const result = await upscaleImage(filename, upscaleScale, upscaleMethod)
      if (result.success) {
        // Use filename instead of base64 for consistency
        const imageRef = result.filename || result.image
        setCurrentImage(imageRef)
        addSessionImage(imageRef)
        loadOutputGallery()
      } else {
        alert('Upscale failed: ' + (result.error || 'Unknown error'))
      }
    } catch (e) {
      console.error('Upscale error:', e)
      alert('Upscale failed: ' + e.message)
    } finally {
      setIsUpscaling(false)
    }
  }

  async function handleVariation() {
    if (!generation.currentImage || isCreatingVariation) return
    
    // Extract filename from currentImage
    let filename = generation.currentImage
    if (filename.startsWith('data:')) {
      alert('Cannot create variation from base64 image. Please select an image from the library.')
      return
    }
    if (filename.includes('/')) {
      filename = filename.split('/').pop()
    }
    
    // Close popup immediately before starting variation
    setShowVariationPopup(false)
    setIsCreatingVariation(true)
    
    try {
      const result = await createVariation(filename, variationStrength, settings.steps, settings.cfg)
      if (result.success) {
        // Use filename instead of base64 for consistency
        const imageRef = result.filename || result.image
        setCurrentImage(imageRef)
        addSessionImage(imageRef)
        loadOutputGallery()
      } else {
        alert('Variation failed: ' + (result.error || 'Unknown error'))
      }
    } catch (e) {
      console.error('Variation error:', e)
      alert('Variation failed: ' + e.message)
    } finally {
      setIsCreatingVariation(false)
    }
  }

  function loadFromHistory(entry: PromptHistoryEntry) {
    setPrompt(entry.prompt)
    setNegativePrompt(entry.negativePrompt || '')
    if (entry.seed) setSeed(entry.seed)
    if (entry.resolution) setResolution(entry.resolution)
    if (entry.steps) setSteps(entry.steps)
    if (entry.cfg) setCfg(entry.cfg)
  }

  function clearHistory() {
    if (confirm('Clear all history?')) {
      localStorage.removeItem('iris_prompt_history')
      setPromptHistoryState([])
    }
  }

  return (
    <div className="flex h-screen w-full overflow-hidden text-sm relative">
      {/* Mobile Overlay */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-30 md:hidden" 
          onClick={() => setMobileMenuOpen(false)}
        />
      )}
      
      {/* Sidebar - Responsive */}
      <aside className={clsx(
        "w-[320px] lg:w-[360px] flex flex-col bg-iris-panel border-r border-iris-border flex-shrink-0 z-40 transition-transform duration-300",
        "md:relative md:translate-x-0",
        "fixed inset-y-0 left-0",
        mobileMenuOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
      )}>
        {/* Logo Header */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-iris-border">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 via-purple-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/20">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
            </div>
            <div>
              <h1 className="font-bold text-base tracking-tight text-white leading-none">I.R.I.S.</h1>
              <span className="text-[9px] font-mono text-purple-400/80 tracking-widest">AI STUDIO</span>
            </div>
          </Link>
          
          {/* Close button (mobile only) */}
          <button 
            onClick={() => setMobileMenuOpen(false)}
            className="md:hidden p-2 text-zinc-400 hover:text-white transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          
          {/* Dynamic Status Indicator (desktop only) */}
          <div className="hidden md:flex items-center gap-1.5">
            {generation.isGenerating ? (
              <>
                <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse shadow-[0_0_8px_rgba(168,85,247,0.6)]" />
                <span className="text-[10px] font-medium text-purple-400">Generating</span>
              </>
            ) : isUpscaling ? (
              <>
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
                <span className="text-[10px] font-medium text-blue-400">Upscaling</span>
              </>
            ) : isCreatingVariation ? (
              <>
                <span className="w-2 h-2 rounded-full bg-pink-500 animate-pulse shadow-[0_0_8px_rgba(236,72,153,0.6)]" />
                <span className="text-[10px] font-medium text-pink-400">Variation</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
                <span className="text-[10px] font-medium text-zinc-500 hidden lg:inline">Ready</span>
              </>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="px-3 py-2 border-b border-iris-border">
          <div className="flex gap-1 p-1 bg-iris-bg/50 rounded-lg">
            <Link to="/" className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md text-zinc-400 hover:text-white hover:bg-white/5 transition-all">Home</Link>
            <span className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md bg-iris-accent/20 text-iris-accentLight border border-iris-accent/30">Create</span>
            <Link to="/gallery" className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md text-zinc-400 hover:text-white hover:bg-white/5 transition-all">Gallery</Link>
            <Link to="/upscaler" className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md text-zinc-400 hover:text-white hover:bg-white/5 transition-all">Upscale</Link>
          </div>
        </nav>

        {/* Dashboard - Full width button below */}
        <div className="px-3 py-2">
          <Link to="/dashboard" className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-lg text-sm font-medium transition-all bg-iris-card border border-iris-border text-zinc-400 hover:text-white hover:border-white/20">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
            Dashboard
          </Link>
        </div>

        {/* Scrollable Controls */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="p-4 space-y-5">
            {/* Model Selector */}
            <ModelSelector 
              selectedModelId={settings.model}
              onModelChange={setModel}
            />

            {/* Prompt */}
            <PromptInput
              prompt={settings.prompt}
              negativePrompt={settings.negativePrompt}
              onPromptChange={setPrompt}
              onNegativePromptChange={setNegativePrompt}
              onRandomPrompt={() => setPrompt(getRandomPrompt())}
              negativePromptSupported={storeModels.find(m => m.id === settings.model)?.supports_negative_prompt ?? true}
            />

            <div className="h-px bg-gradient-to-r from-transparent via-iris-border to-transparent" />

            {/* Dimensions */}
            <ResolutionSelector
              selectedResolution={settings.resolution}
              customWidth={customWidth}
              customHeight={customHeight}
              onResolutionChange={setResolution}
              onCustomWidthChange={handleCustomWidthChange}
              onCustomHeightChange={handleCustomHeightChange}
              aspectLocked={aspectLocked}
              onAspectLockToggle={toggleAspectLockFn}
              onSwapDimensions={swapDimensions}
              modelArchitecture={storeModels.find(m => m.id === settings.model)?.architecture}
            />

            {/* Quality Preset */}
            <QualityPresetSelector
              selectedPreset={settings.qualityPreset}
              onPresetChange={setQualityPreset}
            />

            <div className="h-px bg-gradient-to-r from-transparent via-iris-border to-transparent" />

            {/* Advanced Settings */}
            <details open={showAdvanced} onToggle={(e) => setShowAdvanced((e.target as HTMLDetailsElement).open)}>
              <summary className="flex justify-between items-center cursor-pointer py-2 text-xs font-semibold text-zinc-500 hover:text-white transition-colors select-none">
                <div className="flex items-center gap-2">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                  <span>Advanced</span>
                </div>
                <svg className={clsx("w-4 h-4 transition-transform text-zinc-600", showAdvanced && "rotate-180")} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
              </summary>
              
              <div className="pt-4 space-y-5">
                {/* Steps */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] uppercase text-zinc-500 font-semibold">Steps</label>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-iris-accent bg-iris-accent/10 px-2 py-0.5 rounded-md">{settings.steps}</span>
                      {storeModels.find(m => m.id === settings.model)?.recommended_steps && (
                        <button 
                          onClick={() => setSteps(storeModels.find(m => m.id === settings.model)?.recommended_steps || 28, false)}
                          className="text-[10px] text-zinc-500 hover:text-iris-accent transition-colors"
                          title="Reset to model default"
                        >
                          ↺
                        </button>
                      )}
                    </div>
                  </div>
                  <input type="range" min={1} max={150} value={settings.steps} onChange={(e) => setSteps(Number(e.target.value))} className="w-full" />
                </div>

                {/* CFG */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] uppercase text-zinc-500 font-semibold">CFG Scale</label>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-iris-accent bg-iris-accent/10 px-2 py-0.5 rounded-md">{settings.cfg.toFixed(1)}</span>
                      {storeModels.find(m => m.id === settings.model)?.recommended_cfg && (
                        <button 
                          onClick={() => setCfg(storeModels.find(m => m.id === settings.model)?.recommended_cfg || 7.5, false)}
                          className="text-[10px] text-zinc-500 hover:text-iris-accent transition-colors"
                          title="Reset to model default"
                        >
                          ↺
                        </button>
                      )}
                    </div>
                  </div>
                  <input type="range" min={1} max={30} step={0.5} value={settings.cfg} onChange={(e) => setCfg(Number(e.target.value))} className="w-full" />
                </div>

                {/* Seed */}
                <div className="space-y-2">
                  <label className="text-[10px] uppercase text-zinc-500 font-semibold">Seed</label>
                  <div className="liquid-glass-input border border-iris-border rounded-xl p-3">
                    <div className="flex items-center gap-3">
                      <input type="number" value={settings.seed ?? ''} onChange={(e) => setSeed(e.target.value ? Number(e.target.value) : null)} readOnly={settings.seedLocked} className="flex-1 bg-transparent text-white text-lg font-mono focus:outline-none min-w-0" placeholder="Random" />
                      <div className="flex gap-1.5">
                        <button onClick={toggleSeedLock} className={clsx("w-9 h-9 rounded-lg border border-iris-border bg-iris-card text-zinc-500 hover:text-iris-accent hover:border-iris-accent/50 transition-all flex items-center justify-center", settings.seedLocked && "text-iris-accent bg-iris-accent/10 border-iris-accent/50")} title="Lock Seed">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={settings.seedLocked ? "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" : "M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z"} /></svg>
                        </button>
                        <button onClick={randomizeSeed} className="w-9 h-9 rounded-lg border border-iris-border bg-iris-card text-zinc-500 hover:text-white hover:border-white/20 transition-all flex items-center justify-center" title="Randomize">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-iris-border/50">
                      <span className="text-[10px] text-zinc-600">Empty = Random each time</span>
                      {settings.seedLocked && <span className="text-[10px] text-zinc-600 ml-auto flex items-center gap-1"><svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>Locked</span>}
                    </div>
                  </div>
                </div>

                {/* Safety Filter Display */}
              </div>
            </details>
          </div>
        </div>

        {/* Generate Button */}
        <div className="p-4 border-t border-iris-border bg-iris-panel">
          <button onClick={handleGenerate} disabled={generation.isGenerating} className="w-full py-3.5 rounded-xl font-bold text-sm tracking-wide text-white flex items-center justify-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed transition-all bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 hover:from-violet-500 hover:via-purple-500 hover:to-indigo-500 shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40">
            <svg className="w-5 h-5 group-hover:scale-110 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <span>{generation.isGenerating ? 'Generating...' : 'Generate'}</span>
          </button>
        </div>
      </aside>

      {/* Main Content - Horizontal Layout */}
      <main className="flex-1 flex min-w-0 bg-iris-bg relative">
        {/* Left Side - Canvas Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Top Bar */}
          <header className="h-12 border-b border-iris-border bg-iris-panel/80 backdrop-blur-sm flex items-center justify-between px-3 md:px-5 shrink-0 z-10">
            <div className="flex items-center gap-3">
              {/* Hamburger Menu Button (Mobile Only) */}
              <button 
                onClick={() => setMobileMenuOpen(true)}
                className="md:hidden p-2 -ml-2 text-zinc-400 hover:text-white transition-colors"
                aria-label="Open menu"
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
              <span className="text-xs text-zinc-500 font-mono">{settings.resolution === 'custom' ? `${customWidth}x${customHeight}` : settings.resolution}</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs font-mono text-zinc-400">{generation.sessionImages.length} generated</span>
            </div>
          </header>

          {/* Canvas Area */}
          <div className="flex-1 relative flex flex-col min-h-0">
          <div className="flex-1 checkerboard-bg relative flex items-center justify-center p-3 md:p-6 overflow-hidden min-h-0">
            {/* Placeholder */}
            {!generation.currentImage && !generation.isGenerating && (
              <div className="text-center select-none w-full h-full flex flex-col items-center justify-center px-4">
                <div className="relative mb-4 md:mb-6">
                  <div className="w-16 h-16 md:w-24 md:h-24 rounded-2xl liquid-glass-subtle flex items-center justify-center">
                    <svg className="w-8 h-8 md:w-10 md:h-10 text-iris-accent/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                </div>
                <h3 className="text-base md:text-lg font-light text-zinc-300 mb-2">Create something amazing</h3>
                <p className="text-xs text-zinc-600 mb-4">Enter a prompt and click Generate</p>
                <div className="flex gap-2 flex-wrap justify-center">
                  <span className="px-2.5 py-1 rounded-full text-[9px] liquid-glass-subtle text-iris-accentLight font-medium">AI Powered</span>
                  <span className="px-2.5 py-1 rounded-full text-[9px] liquid-glass-subtle text-indigo-400 font-medium">Local Processing</span>
                </div>
              </div>
            )}

            {/* Generated Image */}
            {generation.currentImage && !generation.isGenerating && (
              <img src={getImageUrl(generation.currentImage)} className="max-h-[calc(100%-32px)] md:max-h-[calc(100%-48px)] max-w-[calc(100%-32px)] md:max-w-[calc(100%-48px)] object-contain shadow-2xl rounded-xl" style={{ boxShadow: '0 25px 80px -20px rgba(0,0,0,0.8)' }} alt="Generated" />
            )}

            {/* Progress Overlay */}
            {generation.isGenerating && (
              <div className="absolute inset-0 bg-iris-bg/95 backdrop-blur-xl flex flex-col items-center justify-center z-50">
                <div className="flex flex-col items-center gap-6 w-full max-w-md px-8">
                  {/* Circular Timer */}
                  <div className="relative w-32 h-32">
                    <svg className="w-full h-full transform -rotate-90" style={{ filter: 'drop-shadow(0 0 20px rgba(139, 92, 246, 0.3))' }}>
                      <circle cx="64" cy="64" r="58" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="2" />
                      <circle cx="64" cy="64" r="58" fill="none" stroke="url(#timerGradient)" strokeWidth="4" strokeLinecap="round" strokeDasharray="364" strokeDashoffset={364 * (1 - generation.progress / 100)} style={{ transition: 'stroke-dashoffset 0.3s ease' }} />
                      <defs>
                        <linearGradient id="timerGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                          <stop offset="0%" style={{ stopColor: '#a855f7' }} />
                          <stop offset="100%" style={{ stopColor: '#6366f1' }} />
                        </linearGradient>
                      </defs>
                    </svg>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <div className="text-3xl font-bold text-white tabular-nums font-mono">{generationTime.toFixed(1)}s</div>
                      <div className="text-[9px] text-zinc-500 font-medium mt-0.5 uppercase tracking-wider">
                        {generation.progress < 30 ? 'WARMING UP' : generation.progress < 70 ? 'REFINING' : 'FINISHING'}
                      </div>
                    </div>
                  </div>
                  
                  {/* Progress Bar */}
                  <div className="w-full">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm text-zinc-400">{generation.status}</span>
                      <span className="text-sm font-mono text-iris-accent">{Math.round(generation.progress)}%</span>
                    </div>
                    <div className="w-full h-2 bg-iris-card rounded-full overflow-hidden border border-iris-border">
                      <div className="h-full rounded-full transition-all duration-300 ease-out" style={{ width: `${generation.progress}%`, background: generation.progress > 85 ? 'linear-gradient(90deg, #10b981, #34d399)' : 'linear-gradient(90deg, #8b5cf6, #6366f1)' }} />
                    </div>
                    <div className="flex justify-between items-center mt-2">
                      <div className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 bg-iris-accent rounded-full animate-pulse" />
                        <span className="text-xs text-zinc-600 font-mono">Step {generation.currentStep}/{generation.totalSteps}</span>
                      </div>
                      <span className="text-xs text-zinc-600 font-mono">ETA: {eta ? `~${eta}s` : '--'}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Image Actions - Adjusted position */}
        {generation.currentImage && !generation.isGenerating && (
          <div className="absolute left-1/2 -translate-x-1/2 liquid-glass p-1.5 md:p-1.5 rounded-2xl flex items-center gap-1 z-50" style={{ bottom: '24px' }}>
            <button onClick={handleDownload} className="px-3 md:px-4 py-2.5 md:py-2 rounded-xl text-xs font-medium text-zinc-400 hover:bg-white/5 hover:text-white transition flex items-center gap-2 touch-manipulation">
              <svg className="w-4 h-4 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
              <span className="hidden sm:inline">Download</span>
            </button>
            <div className="w-px h-6 bg-white/10 mx-1" />
            <div className="relative">
              <button onClick={() => setShowUpscalePopup(!showUpscalePopup)} className="px-3 md:px-4 py-2.5 md:py-2 rounded-xl text-xs font-medium text-iris-accentLight hover:bg-iris-accent/10 transition flex items-center gap-2 touch-manipulation">
                <svg className="w-4 h-4 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
                <span className="hidden sm:inline">Upscale</span>
              </button>
              {/* Upscale Popup */}
              {showUpscalePopup && (
                <div ref={upscalePopupRef} className="absolute bottom-full left-0 mb-2 bg-iris-panel border border-iris-border rounded-xl shadow-2xl min-w-[280px] z-[9999]">
                  {/* Method Selection */}
                  <div className="p-3 border-b border-iris-border/50">
                    <div className="text-[10px] text-zinc-500 uppercase font-semibold mb-2">Upscale Method</div>
                    <div className="space-y-1.5">
                      <div onClick={() => setUpscaleMethod('realesrgan')} className={clsx("flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors", upscaleMethod === 'realesrgan' ? "bg-iris-accent/10" : "hover:bg-white/5")}>
                        <div className="w-8 h-8 rounded-lg bg-iris-accent/20 flex items-center justify-center">
                          <svg className="w-4 h-4 text-iris-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /></svg>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-zinc-200">Real-ESRGAN</div>
                          <div className="text-[10px] text-zinc-500">AI Enhanced • Best quality</div>
                        </div>
                      </div>
                      <div onClick={() => setUpscaleMethod('anime_v3')} className={clsx("flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors", upscaleMethod === 'anime_v3' ? "bg-iris-accent/10" : "hover:bg-white/5")}>
                        <div className="w-8 h-8 rounded-lg bg-pink-500/20 flex items-center justify-center">
                          <svg className="w-4 h-4 text-pink-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" /></svg>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-zinc-200">Anime v3</div>
                          <div className="text-[10px] text-zinc-500">Fast • Optimized for anime</div>
                        </div>
                      </div>
                      <div onClick={() => setUpscaleMethod('bsrgan')} className={clsx("flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors", upscaleMethod === 'bsrgan' ? "bg-iris-accent/10" : "hover:bg-white/5")}>
                        <div className="w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center">
                          <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-zinc-200">Tile Mode</div>
                          <div className="text-[10px] text-zinc-500">For JPEG/compressed images</div>
                        </div>
                      </div>
                      <div onClick={() => setUpscaleMethod('lanczos')} className={clsx("flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors", upscaleMethod === 'lanczos' ? "bg-iris-accent/10" : "hover:bg-white/5")}>
                        <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                          <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-zinc-200">Lanczos</div>
                          <div className="text-[10px] text-zinc-500">CPU • Fast fallback</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Scale Selection */}
                  <div className="p-3 border-b border-iris-border/50">
                    <div className="text-[10px] text-zinc-500 uppercase font-semibold mb-2">Scale Factor</div>
                    <div className="flex gap-2">
                      {[2, 4].map(scale => (
                        <button key={scale} onClick={() => setUpscaleScale(scale)} className={clsx("flex-1 py-2.5 rounded-lg text-sm font-medium transition-all", upscaleScale === scale ? "bg-iris-accent/20 text-iris-accentLight border border-iris-accent/30" : "bg-iris-card border border-iris-border text-zinc-500 hover:bg-white/5 hover:text-zinc-300")}>
                          {scale}x
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  {/* Apply Button */}
                  <div className="p-3">
                    <button 
                      onClick={handleUpscale} 
                      disabled={isUpscaling}
                      className="w-full py-2.5 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-iris-accent to-indigo-500 hover:from-iris-accent/90 hover:to-indigo-500/90 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {isUpscaling ? (
                        <>
                          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                          Upscaling...
                        </>
                      ) : (
                        <>
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" /></svg>
                          Apply Upscale
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
            {/* Variation Button */}
            <div className="w-px h-6 bg-white/10 mx-1" />
            <div className="relative">
              <button onClick={() => setShowVariationPopup(!showVariationPopup)} className="px-3 md:px-4 py-2.5 md:py-2 rounded-xl text-xs font-medium text-pink-400 hover:bg-pink-500/10 transition flex items-center gap-2 touch-manipulation">
                <svg className="w-4 h-4 md:w-4 md:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                <span className="hidden sm:inline">Variation</span>
              </button>
              {/* Variation Popup */}
              {showVariationPopup && (
                <div ref={variationPopupRef} className="absolute bottom-full left-0 mb-2 bg-iris-panel border border-iris-border rounded-xl shadow-2xl min-w-[280px] z-[9999]">
                  {/* Strength Slider */}
                  <div className="p-3 border-b border-iris-border/50">
                    <div className="text-[10px] text-zinc-500 uppercase font-semibold mb-2">Variation Strength</div>
                    <div className="space-y-2">
                      <input 
                        type="range" 
                        min="0.1" 
                        max="0.9" 
                        step="0.1" 
                        value={variationStrength} 
                        onChange={(e) => setVariationStrength(parseFloat(e.target.value))}
                        className="w-full accent-pink-500"
                      />
                      <div className="flex justify-between text-[10px] text-zinc-500">
                        <span>Similar</span>
                        <span className="text-pink-400 font-medium">{Math.round(variationStrength * 100)}%</span>
                        <span>Different</span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Presets */}
                  <div className="p-3 border-b border-iris-border/50">
                    <div className="text-[10px] text-zinc-500 uppercase font-semibold mb-2">Quick Presets</div>
                    <div className="flex gap-2">
                      {[
                        { label: 'Subtle', value: 0.2 },
                        { label: 'Medium', value: 0.5 },
                        { label: 'Strong', value: 0.8 },
                      ].map(preset => (
                        <button 
                          key={preset.label} 
                          onClick={() => setVariationStrength(preset.value)} 
                          className={clsx("flex-1 py-2 rounded-lg text-xs font-medium transition-all", variationStrength === preset.value ? "bg-pink-500/20 text-pink-400 border border-pink-500/30" : "bg-iris-card border border-iris-border text-zinc-500 hover:bg-white/5 hover:text-zinc-300")}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  {/* Apply Button */}
                  <div className="p-3">
                    <button 
                      onClick={handleVariation} 
                      disabled={isCreatingVariation}
                      className="w-full py-2.5 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-500/90 hover:to-rose-500/90 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {isCreatingVariation ? (
                        <>
                          <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                          Creating Variation...
                        </>
                      ) : (
                        <>
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                          Create Variation
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        </div>

        {/* Right Sidebar - Gallery (hidden on mobile) */}
        <aside className="hidden lg:flex w-80 bg-iris-panel border-l border-iris-border flex-col shrink-0">
          {/* Gallery Header */}
          <div className="h-12 border-b border-iris-border flex items-center justify-between px-4 bg-iris-panel/80 backdrop-blur-sm">
            <h2 className="text-sm font-semibold text-white">Gallery</h2>
            <button onClick={loadOutputGallery} className="text-zinc-600 hover:text-white p-1.5 transition rounded-lg hover:bg-white/5" title="Refresh">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            </button>
          </div>

          {/* Gallery Tabs */}
          <div className="flex border-b border-iris-border">
            <button onClick={() => setActiveTab('recent')} className={clsx("flex-1 px-3 py-3 text-[11px] font-semibold uppercase tracking-wider transition-colors", activeTab === 'recent' ? "text-white bg-iris-accent/10 border-b-2 border-iris-accent" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5")}>
              <div className="flex flex-col items-center gap-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>Session</span>
              </div>
            </button>
            <button onClick={() => setActiveTab('output')} className={clsx("flex-1 px-3 py-3 text-[11px] font-semibold uppercase tracking-wider transition-colors", activeTab === 'output' ? "text-white bg-iris-accent/10 border-b-2 border-iris-accent" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5")}>
              <div className="flex flex-col items-center gap-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                <span>Library</span>
              </div>
            </button>
            <button onClick={() => setActiveTab('history')} className={clsx("flex-1 px-3 py-3 text-[11px] font-semibold uppercase tracking-wider transition-colors", activeTab === 'history' ? "text-white bg-iris-accent/10 border-b-2 border-iris-accent" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5")}>
              <div className="flex flex-col items-center gap-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>History</span>
              </div>
            </button>
          </div>

          {/* Gallery Content */}
          <div className="flex-1 overflow-y-auto custom-scrollbar bg-iris-bg/30">
            {/* Session Tab */}
            {activeTab === 'recent' && (
              <div className="p-3">
                {generation.sessionImages.length === 0 ? (
                  <div className="text-center py-16 text-zinc-600 text-xs">
                    <svg className="w-16 h-16 mx-auto mb-4 text-zinc-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                    <p className="font-medium text-zinc-500 mb-1">No images yet</p>
                    <p className="text-[10px] text-zinc-700">Generate your first image</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    {generation.sessionImages.map((img, i) => (
                      <div key={i} onClick={() => setCurrentImage(img)} className={clsx("aspect-square rounded-xl overflow-hidden cursor-pointer transition-all hover:scale-[1.02] hover:shadow-xl", generation.currentImage === img ? "ring-2 ring-iris-accent shadow-lg shadow-iris-accent/20" : "hover:ring-2 hover:ring-white/20")}>
                        <img src={getImageUrl(img)} className="w-full h-full object-cover" alt="" />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Library Tab */}
            {activeTab === 'output' && (
              <div className="p-3">
                {outputImages.length === 0 ? (
                  <div className="text-center py-16 text-zinc-600 text-xs">
                    <svg className="w-16 h-16 mx-auto mb-4 text-zinc-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                    <p className="font-medium text-zinc-500 mb-1">Library is empty</p>
                    <p className="text-[10px] text-zinc-700">Saved images appear here</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    {outputImages.map((img, i) => (
                      <div key={i} onClick={() => setCurrentImage(img)} className={clsx("aspect-square rounded-xl overflow-hidden cursor-pointer transition-all hover:scale-[1.02] hover:shadow-xl", generation.currentImage === img ? "ring-2 ring-iris-accent shadow-lg shadow-iris-accent/20" : "hover:ring-2 hover:ring-white/20")}>
                        <img src={getImageUrl(img)} className="w-full h-full object-cover" alt="" />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* History Tab */}
            {activeTab === 'history' && (
              <div className="p-3">
                <div className="flex justify-end mb-3">
                  <button onClick={clearHistory} className="text-[10px] text-red-400/70 hover:text-red-400 transition px-2 py-1 rounded hover:bg-red-500/10">Clear History</button>
                </div>
                <div className="space-y-2">
                  {promptHistory.length === 0 ? (
                    <div className="text-center py-16 text-zinc-600 text-xs">
                      <svg className="w-16 h-16 mx-auto mb-4 text-zinc-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      <p className="font-medium text-zinc-500 mb-1">No history yet</p>
                      <p className="text-[10px] text-zinc-700">Your prompts will be saved here</p>
                    </div>
                  ) : (
                    promptHistory.map((entry, i) => (
                      <div key={i} onClick={() => loadFromHistory(entry)} className="p-3 bg-iris-card border border-iris-border rounded-xl cursor-pointer hover:border-iris-accent/30 transition-all group">
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-zinc-300 line-clamp-2 group-hover:text-iris-accentLight transition mb-2">{entry.prompt}</div>
                          <div className="flex gap-2 text-[10px] text-zinc-600 font-mono">
                            <span>{new Date(entry.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</span>
                            <span>•</span>
                            <span>{entry.resolution}</span>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </aside>
      </main>
    </div>
  )
}
