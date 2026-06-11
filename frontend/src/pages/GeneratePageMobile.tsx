import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { clsx } from 'clsx'
import { useStore, models, resolutions } from '../store/useStore'
import { getOutputGallery, getImageUrl, getWebSocketUrl } from '../lib/api'

/**
 * Mobile-optimized Generate Page
 * Features:
 * - Fullscreen canvas
 * - Bottom sheet for controls
 * - Bottom navigation
 * - Swipe gestures
 * - Floating action button
 */

export default function GeneratePageMobile() {
  const { settings, generation, setModel, setPrompt, setResolution,
    setSteps, setCfg, setGenerating, setProgress, setCurrentImage, 
    addSessionImage } = useStore()
  
  // Mobile-specific state
  const [showControls, setShowControls] = useState(false)
  const [showGallery, setShowGallery] = useState(false)
  const [sessionImages, setSessionImages] = useState<string[]>([])
  const [generationTime, setGenerationTime] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<number | null>(null)
  const genStartRef = useRef<number | null>(null)

  const selectedModel = models.find(m => m.id === settings.model)

  useEffect(() => {
    loadSessionImages()
  }, [])

  // Timer for generation
  useEffect(() => {
    if (generation.isGenerating) {
      if (!genStartRef.current) genStartRef.current = Date.now()
      timerRef.current = window.setInterval(() => {
        const elapsed = (Date.now() - genStartRef.current) / 1000
        setGenerationTime(elapsed)
      }, 100)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
      genStartRef.current = null
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [generation.isGenerating])

  async function loadSessionImages() {
    try {
      const data = await getOutputGallery()
      setSessionImages(data.images || [])
    } catch (e) { 
      console.error('Failed to load gallery:', e)
    }
  }

  function handleGenerate() {
    if (generation.isGenerating) return
    setGenerating(true)
    setProgress(0, 0, settings.steps, 'Initializing...')
    setGenerationTime(0)
    setShowControls(false) // Close bottom sheet

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const wsUrl = getWebSocketUrl()
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      const [width, height] = settings.resolution.split('x').map(Number)
      ws.send(JSON.stringify({
        prompt: settings.prompt,
        style: settings.model,
        width, height,
        steps: settings.steps,
        cfg_scale: settings.cfg,
        seed: settings.seed || null
      }))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'progress') {
        const progress = data.progress || (data.step / data.total_steps * 100) || 0
        setProgress(progress, data.step || 0, data.total_steps || settings.steps, 'Generating...')
      } else if (data.type === 'completed') {
        const imageRef = data.filename || data.image
        setCurrentImage(imageRef)
        addSessionImage(imageRef)
        setGenerating(false)
        setProgress(100, settings.steps, settings.steps, 'Complete!')
        loadSessionImages()
      } else if (data.type === 'error') {
        setGenerating(false)
        setProgress(0, 0, 0, 'Error: ' + (data.message || 'Unknown error'))
      }
    }

    ws.onerror = () => { setGenerating(false); setProgress(0, 0, 0, 'Connection error') }
    ws.onclose = () => { wsRef.current = null }
  }

  return (
    <div className="fixed inset-0 bg-iris-bg flex flex-col">
      {/* Top Bar - Minimal */}
      <header className="h-14 bg-iris-panel/95 backdrop-blur-md border-b border-iris-border flex items-center justify-between px-4 z-20">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
          </div>
          <span className="font-bold text-white tracking-tight">I.R.I.S.</span>
        </Link>
        
        {/* Status */}
        <div className="flex items-center gap-2">
          {generation.isGenerating && (
            <span className="text-xs text-purple-400 font-medium">{Math.round(generation.progress)}%</span>
          )}
          <button onClick={() => setShowGallery(!showGallery)} className="p-2 rounded-lg text-zinc-400 hover:bg-white/5">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </button>
        </div>
      </header>

      {/* Main Canvas - Fullscreen */}
      <main className="flex-1 relative overflow-hidden">
        {!generation.currentImage && !generation.isGenerating && (
          <div className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center">
            <div className="w-20 h-20 rounded-2xl bg-iris-panel border border-iris-border flex items-center justify-center mb-4">
              <svg className="w-10 h-10 text-iris-accent/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Tap to create</h3>
            <p className="text-sm text-zinc-500">Enter a prompt and hit generate</p>
          </div>
        )}

        {/* Generated Image */}
        {generation.currentImage && !generation.isGenerating && (
          <div className="absolute inset-0 flex items-center justify-center p-4 bg-black/50">
            <img 
              src={getImageUrl(generation.currentImage)} 
              className="max-w-full max-h-full object-contain rounded-xl shadow-2xl"
              alt="Generated"
            />
          </div>
        )}

        {/* Progress Overlay */}
        {generation.isGenerating && (
          <div className="absolute inset-0 bg-iris-bg/98 backdrop-blur-xl flex flex-col items-center justify-center">
            <div className="relative w-32 h-32 mb-6">
              <svg className="w-full h-full transform -rotate-90">
                <circle cx="64" cy="64" r="56" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="3" />
                <circle 
                  cx="64" cy="64" r="56" fill="none" 
                  stroke="url(#gradient)" strokeWidth="4" strokeLinecap="round"
                  strokeDasharray="352" 
                  strokeDashoffset={352 * (1 - generation.progress / 100)}
                  style={{ transition: 'stroke-dashoffset 0.3s ease' }}
                />
                <defs>
                  <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#a855f7" />
                    <stop offset="100%" stopColor="#6366f1" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <div className="text-2xl font-bold text-white font-mono">{generationTime.toFixed(1)}s</div>
                <div className="text-xs text-zinc-500 uppercase tracking-wide mt-1">Generating</div>
              </div>
            </div>
            <div className="w-full max-w-xs px-6">
              <div className="flex justify-between text-sm mb-2">
                <span className="text-zinc-400">{generation.status}</span>
                <span className="text-iris-accent font-mono">{Math.round(generation.progress)}%</span>
              </div>
              <div className="h-2 bg-iris-card rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-300"
                  style={{ width: `${generation.progress}%` }}
                />
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Floating Action Button */}
      {!generation.isGenerating && (
        <button
          onClick={() => setShowControls(!showControls)}
          className={clsx(
            "fixed bottom-20 right-6 w-14 h-14 rounded-full shadow-2xl flex items-center justify-center z-30 transition-all",
            showControls 
              ? "bg-zinc-700 rotate-45" 
              : "bg-gradient-to-r from-violet-600 to-indigo-600 shadow-purple-500/30"
          )}
        >
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
      )}

      {/* Bottom Sheet - Controls */}
      {showControls && (
        <>
          <div 
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setShowControls(false)}
          />
          <div className="fixed bottom-0 left-0 right-0 bg-iris-panel rounded-t-3xl shadow-2xl z-50 max-h-[80vh] overflow-y-auto">
            {/* Handle */}
            <div className="flex justify-center py-3">
              <div className="w-12 h-1.5 bg-zinc-700 rounded-full" />
            </div>

            <div className="px-6 pb-6 space-y-5">
              {/* Model Selector */}
              <div>
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2 block">Model</label>
                <div className="flex items-center gap-3 bg-iris-card border border-iris-border rounded-xl p-3">
                  {selectedModel?.image && (
                    <img src={selectedModel.image} className="w-10 h-10 rounded-lg object-cover" alt="" />
                  )}
                  <span className="text-sm font-medium text-white">{selectedModel?.name}</span>
                </div>
              </div>

              {/* Prompt */}
              <div>
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2 block">Prompt</label>
                <textarea
                  value={settings.prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  className="w-full bg-iris-card border border-iris-border rounded-xl text-white p-4 text-sm min-h-[120px] resize-none outline-none focus:border-iris-accent"
                  placeholder="Describe your image..."
                />
              </div>

              {/* Resolution */}
              <div>
                <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2 block">Resolution</label>
                <div className="grid grid-cols-3 gap-2">
                  {resolutions.slice(0, 6).map(res => (
                    <button
                      key={String(res)}
                      onClick={() => setResolution(String(res))}
                      className={clsx(
                        "py-3 rounded-lg text-sm font-medium transition-all",
                        settings.resolution === String(res)
                          ? "bg-iris-accent text-white shadow-lg"
                          : "bg-iris-card border border-iris-border text-zinc-400"
                      )}
                    >
                      {String(res)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Steps */}
              <div>
                <div className="flex justify-between mb-2">
                  <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">Steps</label>
                  <span className="text-sm font-mono text-iris-accent">{settings.steps}</span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="50"
                  value={settings.steps}
                  onChange={(e) => setSteps(parseInt(e.target.value))}
                  className="w-full h-2 bg-iris-card rounded-full appearance-none cursor-pointer accent-iris-accent"
                />
              </div>

              {/* CFG Scale */}
              <div>
                <div className="flex justify-between mb-2">
                  <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">CFG Scale</label>
                  <span className="text-sm font-mono text-iris-accent">{settings.cfg}</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="0.5"
                  value={settings.cfg}
                  onChange={(e) => setCfg(parseFloat(e.target.value))}
                  className="w-full h-2 bg-iris-card rounded-full appearance-none cursor-pointer accent-iris-accent"
                />
              </div>

              {/* Generate Button */}
              <button
                onClick={handleGenerate}
                disabled={generation.isGenerating}
                className="w-full py-4 rounded-xl font-bold text-base text-white bg-gradient-to-r from-violet-600 to-indigo-600 shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {generation.isGenerating ? 'Generating...' : 'Generate Image'}
              </button>
            </div>
          </div>
        </>
      )}

      {/* Gallery Drawer */}
      {showGallery && (
        <>
          <div 
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setShowGallery(false)}
          />
          <div className="fixed top-0 right-0 bottom-0 w-80 bg-iris-panel shadow-2xl z-50 overflow-y-auto">
            <div className="p-4 border-b border-iris-border flex items-center justify-between">
              <h2 className="font-bold text-white">Gallery</h2>
              <button onClick={() => setShowGallery(false)} className="p-2 text-zinc-400 hover:text-white">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4 grid grid-cols-2 gap-3">
              {generation.sessionImages.map((img, i) => (
                <div
                  key={i}
                  onClick={() => {
                    setCurrentImage(img)
                    setShowGallery(false)
                  }}
                  className={clsx(
                    "aspect-square rounded-xl overflow-hidden cursor-pointer transition-all",
                    generation.currentImage === img 
                      ? "ring-2 ring-iris-accent" 
                      : "hover:ring-2 hover:ring-white/20"
                  )}
                >
                  <img src={getImageUrl(img)} className="w-full h-full object-cover" alt="" />
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Bottom Navigation */}
      <nav className="h-16 bg-iris-panel/95 backdrop-blur-md border-t border-iris-border flex items-center justify-around z-20">
        <Link to="/" className="flex flex-col items-center gap-1 text-zinc-500">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          <span className="text-xs font-medium">Home</span>
        </Link>
        <div className="flex flex-col items-center gap-1 text-iris-accent">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span className="text-xs font-medium">Create</span>
        </div>
        <Link to="/gallery" className="flex flex-col items-center gap-1 text-zinc-500">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <span className="text-xs font-medium">Gallery</span>
        </Link>
        <Link to="/settings" className="flex flex-col items-center gap-1 text-zinc-500">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span className="text-xs font-medium">Settings</span>
        </Link>
      </nav>
    </div>
  )
}
