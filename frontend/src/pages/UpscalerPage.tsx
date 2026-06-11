import { useState, useEffect, useRef } from 'react'
import { clsx } from 'clsx'
import Sidebar from '../components/Sidebar'
import { getImageUrl } from '../lib/api'

export default function UpscalerPage() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedMethod, setSelectedMethod] = useState('realesrgan') // Default to RealESRGAN
  const [scale, setScale] = useState(2.0)
  const [availableMethods, setAvailableMethods] = useState([])
  const [isUploading, setIsUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [originalImage, setOriginalImage] = useState(null)
  const [upscaledImage, setUpscaledImage] = useState(null)
  const [memoryEstimate, setMemoryEstimate] = useState(null)
  const [error, setError] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [processingTime, setProcessingTime] = useState(0)
  const [upscaleHistory, setUpscaleHistory] = useState([])
  const [activeTab, setActiveTab] = useState('current')
  const [postProcess, setPostProcess] = useState(true)
  const [galleryImages, setGalleryImages] = useState([])
  
  const fileInputRef = useRef(null)
  const timerRef = useRef(null)

  // Load available methods on component mount
  useEffect(() => {
    loadAvailableMethods()
    loadUpscaleHistory()
  }, [])

  // Update memory estimate when file, scale, or method changes
  useEffect(() => {
    if (selectedFile && originalImage) {
      updateMemoryEstimate()
    }
  }, [selectedFile, scale, selectedMethod, originalImage])

  const loadAvailableMethods = async () => {
    try {
      const response = await fetch('/api/upscaler/methods')
      const data = await response.json()
      setAvailableMethods(data.methods || [])
      
      // Auto-select first RealESRGAN method if available
      if (data.methods && data.methods.length > 0) {
        const realesrganMethod = data.methods.find(m => m.id.includes('realesrgan'))
        if (realesrganMethod) {
          setSelectedMethod(realesrganMethod.id)
        }
      }
    } catch (error) {
      setError('Failed to load upscaling methods: ' + error.message)
      // Set fallback methods with RealESRGAN as default
      setAvailableMethods([
        { id: 'realesrgan', name: 'RealESRGAN x4plus', desc: 'AI upscaling (CUDA/Tensor)', gpu: true, max_scale: 16 },
        { id: 'lanczos', name: 'Lanczos', desc: 'High-quality CPU interpolation', gpu: false, max_scale: 16 }
      ])
    }
  }

  const loadUpscaleHistory = () => {
    try {
      const history = JSON.parse(localStorage.getItem('iris_upscale_history') || '[]')
      setUpscaleHistory(history)
    } catch (e) {
      console.error('Failed to load upscale history:', e)
      setUpscaleHistory([])
    }
  }

  // NEW: Load gallery images from API
  const loadGalleryImages = async () => {
    try {
      const response = await fetch('/api/gallery/images')
      if (response.ok) {
        const data = await response.json()
        setGalleryImages(data.images || [])
      }
    } catch (e) {
      console.error('Failed to load gallery:', e)
      setGalleryImages([])
    }
  }

  // Load gallery on mount
  useEffect(() => {
    loadGalleryImages()
  }, [])

  const saveToHistory = (original, upscaled, method, scale, time) => {
    const historyItem = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      originalUrl: original.src,
      upscaledUrl: upscaled.url,
      originalWidth: original.naturalWidth,
      originalHeight: original.naturalHeight,
      upscaledWidth: upscaled.width,
      upscaledHeight: upscaled.height,
      method,
      scale,
      processingTime: time
    }

    const newHistory = [historyItem, ...upscaleHistory].slice(0, 50) // Keep last 50
    setUpscaleHistory(newHistory)
    localStorage.setItem('iris_upscale_history', JSON.stringify(newHistory))
  }

  const clearHistory = () => {
    if (confirm('Clear all upscale history?')) {
      setUpscaleHistory([])
      localStorage.removeItem('iris_upscale_history')
    }
  }

  const loadFromHistory = (item) => {
    // Load the upscaled image from history
    const img = new Image()
    img.onload = () => {
      setUpscaledImage({
        url: item.upscaledUrl,
        width: item.upscaledWidth,
        height: item.upscaledHeight,
        scale: item.scale,
        method: item.method
      })
    }
    img.src = item.upscaledUrl

    // Load original if available
    const origImg = new Image()
    origImg.onload = () => {
      setOriginalImage(origImg)
    }
    origImg.src = item.originalUrl
  }

  const updateMemoryEstimate = async () => {
    if (!originalImage) return

    try {
      const formData = new FormData()
      formData.append('width', originalImage.naturalWidth.toString())
      formData.append('height', originalImage.naturalHeight.toString())
      formData.append('scale', scale.toString())
      formData.append('method', selectedMethod)

      const response = await fetch('/api/upscaler/estimate-memory', {
        method: 'POST',
        body: formData
      })

      if (response.ok) {
        const estimate = await response.json()
        setMemoryEstimate(estimate)
      }
    } catch (error) {
      console.error('Memory estimation failed:', error)
    }
  }

  const handleFileSelect = (file) => {
    if (!file || !file.type.startsWith('image/')) {
      setError('Please select a valid image file.')
      return
    }

    // Check file size (max 50MB)
    if (file.size > 50 * 1024 * 1024) {
      setError('File size too large. Maximum 50MB allowed.')
      return
    }

    setSelectedFile(file)
    setError(null)
    setUpscaledImage(null)
    
    // Create preview
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        setOriginalImage(img)
      }
      img.src = e.target.result as string
    }
    reader.readAsDataURL(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragActive(false)
    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleFileSelect(files[0])
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragActive(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setDragActive(false)
  }

  const startUpscaling = async () => {
    if (!selectedFile) return

    setIsUploading(true)
    setProgress(0)
    setError(null)
    setProcessingTime(0)

    // Start timer
    const startTime = Date.now()
    timerRef.current = setInterval(() => {
      setProcessingTime((Date.now() - startTime) / 1000)
    }, 100)

    // Simulate progress for better UX
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        const newProgress = prev + Math.random() * 5
        return newProgress > 85 ? 85 : newProgress
      })
    }, 300)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      formData.append('scale', scale.toString())
      formData.append('method', selectedMethod)
      formData.append('format', 'PNG')
      formData.append('post_process', postProcess ? 'natural' : 'sharp')

      const response = await fetch('/api/upscaler/upscale', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
      }

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      
      const img = new Image()
      img.onload = () => {
        setUpscaledImage({ 
          url, 
          blob, 
          width: img.naturalWidth, 
          height: img.naturalHeight,
          scale: response.headers.get('X-Scale-Factor') || scale,
          method: response.headers.get('X-Method') || selectedMethod
        })
        
        // Save to history
        saveToHistory(originalImage, {
          url,
          width: img.naturalWidth,
          height: img.naturalHeight
        }, selectedMethod, scale, processingTime)
      }
      img.src = url

      // Complete progress
      clearInterval(progressInterval)
      setProgress(100)

    } catch (error) {
      clearInterval(progressInterval)
      setError('Upscaling failed: ' + error.message)
    } finally {
      setIsUploading(false)
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
      setTimeout(() => setProgress(0), 2000)
    }
  }

  const downloadResult = () => {
    if (!upscaledImage) return

    const a = document.createElement('a')
    a.href = upscaledImage.url
    a.download = `iris_upscaled_${scale}x_${selectedMethod}.png`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const clearImages = () => {
    setSelectedFile(null)
    setOriginalImage(null)
    setUpscaledImage(null)
    setMemoryEstimate(null)
    setError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const formatFileSize = (bytes) => {
    return (bytes / 1024 / 1024).toFixed(2) + ' MB'
  }

  const formatTime = (seconds) => {
    return seconds < 60 ? `${seconds.toFixed(1)}s` : `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(1)}s`
  }

  const selectedMethodData = availableMethods.find(m => m.id === selectedMethod)
  const isGpuMethod = selectedMethodData?.gpu || false

  return (
    <div className="flex h-screen w-full overflow-hidden text-sm">
      <Sidebar>
        {/* Sidebar Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="p-4 space-y-5">
            {/* Method Selection */}
            <div className="space-y-2">
              <label className="sidebar-label">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Upscaling Method
              </label>
              <div className="space-y-2">
                {availableMethods.map((method) => (
                  <div
                    key={method.id}
                    onClick={() => setSelectedMethod(method.id)}
                    className={clsx(
                      "p-3 rounded-xl cursor-pointer transition-all border",
                      selectedMethod === method.id
                        ? "bg-iris-accent/20 border-iris-accent/50 text-iris-accentLight"
                        : "bg-iris-card border-iris-border text-zinc-400 hover:text-white hover:border-white/20"
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="font-semibold text-sm">{method.name}</div>
                      <div className="flex items-center gap-2">
                        <span className={clsx(
                          "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                          method.gpu 
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" 
                            : "bg-zinc-600/20 text-zinc-400 border border-zinc-600/30"
                        )}>
                          {method.gpu ? 'CUDA' : 'CPU'}
                        </span>
                      </div>
                    </div>
                    <div className="text-xs text-zinc-500">{method.desc}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="h-px bg-gradient-to-r from-transparent via-iris-border to-transparent" />

            {/* Scale Control */}
            <div className="space-y-2">
              <label className="sidebar-label">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                </svg>
                Scale Factor
              </label>
              <div className="liquid-glass-input border border-iris-border rounded-xl p-4">
                <div className="text-center mb-3">
                  <span className="text-2xl font-bold text-iris-accentLight">{scale}x</span>
                  <div className="text-[10px] text-zinc-500 mt-1">
                    {originalImage && `${originalImage.naturalWidth}×${originalImage.naturalHeight} → ${Math.round(originalImage.naturalWidth * scale)}×${Math.round(originalImage.naturalHeight * scale)}`}
                  </div>
                </div>
                <input
                  type="range"
                  min="2"
                  max="16"
                  step="0.5"
                  value={scale}
                  onChange={(e) => setScale(parseFloat(e.target.value))}
                  className="w-full h-2 bg-iris-bg rounded-lg appearance-none cursor-pointer slider"
                />
                <div className="flex justify-between text-[10px] text-zinc-500 mt-2">
                  <span>2x</span>
                  <span>4x</span>
                  <span>8x</span>
                  <span>16x</span>
                </div>
              </div>
            </div>

            <div className="h-px bg-gradient-to-r from-transparent via-iris-border to-transparent" />

            {/* Style: Natural vs Sharp - NEW FEATURE */}
            <div className="space-y-2">
              <label className="sidebar-label">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
                </svg>
                Style
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setPostProcess(true)}
                  className={clsx(
                    "px-3 py-2 rounded-lg text-xs font-medium transition-all",
                    postProcess
                      ? "bg-white/10 border border-white/30 text-white"
                      : "bg-iris-card border border-iris-border text-zinc-400 hover:border-white/20 hover:text-white"
                  )}
                >
                  Natural
                </button>
                <button
                  onClick={() => setPostProcess(false)}
                  className={clsx(
                    "px-3 py-2 rounded-lg text-xs font-medium transition-all",
                    !postProcess
                      ? "bg-white/10 border border-white/30 text-white"
                      : "bg-iris-card border border-iris-border text-zinc-400 hover:border-white/20 hover:text-white"
                  )}
                >
                  Sharp
                </button>
              </div>
              <p className="text-[10px] text-zinc-600 mt-1">
                {postProcess ? "Minimal processing - only fixes over-saturation" : "Raw AI output - maximum sharpness"}
              </p>
            </div>

            <div className="h-px bg-gradient-to-r from-transparent via-iris-border to-transparent" />

            {/* Memory Estimate */}
            {memoryEstimate && (
              <div className="space-y-2">
                <label className="sidebar-label">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                  </svg>
                  Memory Usage
                </label>
                <div className={clsx(
                  "p-3 rounded-xl border text-xs",
                  memoryEstimate.total_memory_mb > 4000
                    ? "bg-amber-500/10 border-amber-500/30 text-amber-200"
                    : "bg-iris-card border-iris-border text-zinc-400"
                )}>
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span>Input:</span>
                      <span className="font-mono">{memoryEstimate.input_size_mb} MB</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Output:</span>
                      <span className="font-mono">{memoryEstimate.output_size_mb} MB</span>
                    </div>
                    <div className="flex justify-between font-semibold border-t border-current/20 pt-1">
                      <span>Total:</span>
                      <span className="font-mono">{memoryEstimate.total_memory_mb} MB</span>
                    </div>
                    {memoryEstimate.gpu_required && (
                      <div className="text-[10px] text-emerald-400 mt-2 flex items-center gap-1">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        CUDA acceleration enabled
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Processing Stats */}
            {(isUploading || upscaledImage) && (
              <div className="space-y-2">
                <label className="sidebar-label">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Processing Stats
                </label>
                <div className="bg-iris-card border border-iris-border rounded-xl p-3 text-xs space-y-2">
                  <div className="flex justify-between">
                    <span>Time:</span>
                    <span className="font-mono text-iris-accentLight">{formatTime(processingTime)}</span>
                  </div>
                  {upscaledImage && (
                    <>
                      <div className="flex justify-between">
                        <span>Method:</span>
                        <span className="font-mono">{upscaledImage.method}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Scale:</span>
                        <span className="font-mono">{upscaledImage.scale}x</span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="p-4 border-t border-iris-border bg-iris-panel space-y-2">
          <button
            onClick={startUpscaling}
            disabled={!selectedFile || isUploading}
            className={clsx(
              "w-full py-3 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2",
              !selectedFile || isUploading
                ? "bg-zinc-700 text-zinc-500 cursor-not-allowed"
                : isGpuMethod
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-lg shadow-emerald-500/25"
                  : "bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-500 hover:to-violet-500 text-white shadow-lg shadow-purple-500/25"
            )}
          >
            {isUploading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Processing...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                {isGpuMethod ? 'Upscale with CUDA' : 'Upscale with CPU'}
              </>
            )}
          </button>
          
          {selectedFile && (
            <button
              onClick={clearImages}
              className="w-full py-2 rounded-xl font-medium text-sm bg-iris-card border border-iris-border text-zinc-400 hover:text-white hover:border-white/20 transition-all"
            >
              Clear Images
            </button>
          )}
        </div>
      </Sidebar>

      {/* Main Content - Horizontal Layout */}
      <main className="flex-1 flex min-w-0 bg-iris-bg">
        {/* Left Side - Content Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Top Bar */}
          <header className="h-12 border-b border-iris-border bg-iris-panel/80 backdrop-blur-sm flex items-center justify-between px-5 shrink-0 z-10">
          <div className="flex items-center gap-3">
            <svg className="w-4 h-4 text-iris-accentLight" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
            <span className="font-semibold text-white">Image Upscaler</span>
            {isGpuMethod && (
              <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-[10px] font-bold rounded border border-emerald-500/30">
                CUDA ACCELERATED
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <span>Scale: {scale}x</span>
            <span>•</span>
            <span>Method: {selectedMethodData?.name || selectedMethod}</span>
          </div>
        </header>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Upload Area */}
          {!selectedFile && (
            <div className="max-w-2xl mx-auto">
              <div className="text-center mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">AI Image Upscaler</h1>
                <p className="text-zinc-400">Enhance your images with AI-powered upscaling from 2x to 16x resolution</p>
              </div>

              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                className={clsx(
                  "border-2 border-dashed rounded-2xl p-12 text-center transition-all cursor-pointer",
                  dragActive
                    ? "border-iris-accent bg-iris-accent/5"
                    : "border-iris-border hover:border-iris-accent/50 hover:bg-iris-accent/5"
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={(e) => e.target.files[0] && handleFileSelect(e.target.files[0])}
                  className="hidden"
                />
                <div className="text-white">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-iris-accent/20 flex items-center justify-center">
                    <svg className="w-8 h-8 text-iris-accentLight" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <h3 className="text-xl font-semibold mb-2">Upload Image</h3>
                  <p className="text-zinc-400 mb-6">
                    Drag and drop an image here or click to select
                  </p>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="btn-primary px-6 py-3 rounded-xl font-semibold"
                  >
                    Select Image
                  </button>
                  <p className="text-xs text-zinc-600 mt-4">
                    Supports JPG, PNG, WebP • Max 50MB
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Progress Bar */}
          {isUploading && (
            <div className="max-w-2xl mx-auto mb-6">
              <div className="bg-iris-card rounded-full h-3 overflow-hidden border border-iris-border">
                <div
                  className={clsx(
                    "h-full transition-all duration-300",
                    isGpuMethod
                      ? "bg-gradient-to-r from-emerald-500 to-teal-500"
                      : "bg-gradient-to-r from-purple-500 to-violet-500"
                  )}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-zinc-400 mt-2">
                <span>Processing with {isGpuMethod ? 'CUDA' : 'CPU'}...</span>
                <span>{Math.round(progress)}%</span>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="max-w-2xl mx-auto mb-6">
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                <div className="flex items-center gap-2 text-red-200">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  {error}
                </div>
              </div>
            </div>
          )}

          {/* Image Comparison */}
          {(originalImage || upscaledImage) && (
            <div className="max-w-6xl mx-auto">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Original Image */}
                {originalImage && (
                  <div className="liquid-glass-subtle rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-lg font-semibold text-white">Original</h4>
                      <span className="px-2 py-1 bg-zinc-600/20 text-zinc-400 text-xs font-mono rounded border border-zinc-600/30">
                        {originalImage.naturalWidth} × {originalImage.naturalHeight}
                      </span>
                    </div>
                    <div className="text-center">
                      <img
                        src={originalImage.src}
                        alt="Original"
                        className="max-w-full max-h-80 rounded-xl mx-auto shadow-lg border border-white/10"
                      />
                      <div className="mt-4 text-zinc-400 text-sm space-y-1">
                        <div>{originalImage.naturalWidth} × {originalImage.naturalHeight} pixels</div>
                        {selectedFile && <div>{formatFileSize(selectedFile.size)}</div>}
                      </div>
                    </div>
                  </div>
                )}

                {/* Upscaled Image */}
                {upscaledImage && (
                  <div className="liquid-glass-subtle rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-lg font-semibold text-white">Upscaled</h4>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 bg-iris-accent/20 text-iris-accentLight text-xs font-mono rounded border border-iris-accent/30">
                          {upscaledImage.width} × {upscaledImage.height}
                        </span>
                        <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-bold rounded border border-emerald-500/30">
                          {upscaledImage.scale}x
                        </span>
                      </div>
                    </div>
                    <div className="text-center">
                      <img
                        src={upscaledImage.url}
                        alt="Upscaled"
                        className="max-w-full max-h-80 rounded-xl mx-auto shadow-lg border border-white/10"
                      />
                      <div className="mt-4 text-zinc-400 text-sm space-y-1">
                        <div>{upscaledImage.width} × {upscaledImage.height} pixels</div>
                        <div>{formatFileSize(upscaledImage.blob.size)}</div>
                      </div>
                      <button
                        onClick={downloadResult}
                        className="mt-4 btn-primary px-4 py-2 rounded-xl font-semibold text-sm flex items-center gap-2 mx-auto"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        Download Result
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
        </div>

        {/* Right Sidebar - Gallery */}
        <aside className="w-80 bg-iris-panel border-l border-iris-border flex flex-col shrink-0">
          {/* Gallery Header */}
          <div className="h-12 border-b border-iris-border flex items-center justify-between px-4 bg-iris-panel/80 backdrop-blur-sm">
            <h2 className="text-sm font-semibold text-white">History</h2>
            <button onClick={clearHistory} className="text-zinc-600 hover:text-red-400 p-1.5 transition rounded-lg hover:bg-red-500/10" title="Clear History">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
            </button>
          </div>

          {/* Gallery Tabs */}
          <div className="flex border-b border-iris-border">
            <button onClick={() => setActiveTab('current')} className={clsx("flex-1 px-3 py-3 text-[11px] font-semibold uppercase tracking-wider transition-colors", activeTab === 'current' ? "text-white bg-iris-accent/10 border-b-2 border-iris-accent" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5")}>
              <div className="flex flex-col items-center gap-1">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                <span>Current</span>
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
            {/* Current Tab */}
            {activeTab === 'current' && (
              <div className="p-3">
                {!originalImage && !upscaledImage ? (
                  <div className="text-center py-16 text-zinc-600 text-xs">
                    <svg className="w-16 h-16 mx-auto mb-4 text-zinc-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                    <p className="font-medium text-zinc-500 mb-1">No images yet</p>
                    <p className="text-[10px] text-zinc-700">Upload an image to start</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {/* Original Image */}
                    {originalImage && (
                      <div className="bg-iris-card border border-iris-border rounded-xl p-3">
                        <div className="text-[10px] text-zinc-500 uppercase font-semibold mb-2">Original</div>
                        <div className="aspect-square rounded-lg overflow-hidden mb-2">
                          <img src={originalImage.src} className="w-full h-full object-cover" alt="Original" />
                        </div>
                        <div className="text-[10px] text-zinc-600 font-mono">
                          {originalImage.naturalWidth} × {originalImage.naturalHeight}
                        </div>
                      </div>
                    )}

                    {/* Upscaled Image */}
                    {upscaledImage && (
                      <div className="bg-iris-card border border-iris-accent/30 rounded-xl p-3">
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-[10px] text-zinc-500 uppercase font-semibold">Upscaled</div>
                          <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-[9px] font-bold rounded border border-emerald-500/30">
                            {upscaledImage.scale}x
                          </span>
                        </div>
                        <div className="aspect-square rounded-lg overflow-hidden mb-2 ring-2 ring-iris-accent/50">
                          <img src={upscaledImage.url} className="w-full h-full object-cover" alt="Upscaled" />
                        </div>
                        <div className="text-[10px] text-zinc-600 font-mono">
                          {upscaledImage.width} × {upscaledImage.height}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* History Tab */}
            {activeTab === 'history' && (
              <div className="p-3">
                {upscaleHistory.length === 0 ? (
                  <div className="text-center py-16 text-zinc-600 text-xs">
                    <svg className="w-16 h-16 mx-auto mb-4 text-zinc-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    <p className="font-medium text-zinc-500 mb-1">No history yet</p>
                    <p className="text-[10px] text-zinc-700">Upscaled images will appear here</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {upscaleHistory.map((item) => (
                      <div key={item.id} onClick={() => loadFromHistory(item)} className="bg-iris-card border border-iris-border rounded-xl p-3 cursor-pointer hover:border-iris-accent/30 transition-all group">
                        <div className="grid grid-cols-2 gap-2 mb-2">
                          <div className="aspect-square rounded-lg overflow-hidden">
                            <img src={item.originalUrl} className="w-full h-full object-cover" alt="Original" />
                          </div>
                          <div className="aspect-square rounded-lg overflow-hidden ring-1 ring-iris-accent/30">
                            <img src={item.upscaledUrl} className="w-full h-full object-cover" alt="Upscaled" />
                          </div>
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] text-zinc-500 font-mono">{item.originalWidth}×{item.originalHeight}</span>
                            <svg className="w-3 h-3 text-zinc-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
                            <span className="text-[10px] text-iris-accentLight font-mono">{item.upscaledWidth}×{item.upscaledHeight}</span>
                          </div>
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 font-bold rounded">{item.scale}x</span>
                            <span className="text-zinc-600">{new Date(item.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>
      </main>

      
    </div>
  )
}