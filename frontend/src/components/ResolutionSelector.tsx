import { clsx } from 'clsx'
import { resolutions, type Resolution } from '../store/useStore'

interface AspectIconProps {
  icon: string
}

function AspectIcon({ icon }: AspectIconProps) {
  const iconMap: Record<string, React.ReactElement> = {
    'square': <div className="w-4 h-4 border-2 border-current rounded" />,
    'portrait': <div className="w-3 h-4 border-2 border-current rounded" />,
    'portrait-narrow': <div className="w-2.5 h-4 border-2 border-current rounded" />,
    'portrait-tall': <div className="w-2 h-5 border-2 border-current rounded" />,
    'landscape': <div className="w-4 h-3 border-2 border-current rounded" />,
    'landscape-narrow': <div className="w-4 h-2.5 border-2 border-current rounded" />,
    'custom': <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>,
  }
  return iconMap[icon] || iconMap['square']
}

import { useMemo } from 'react'

interface ResolutionSelectorProps {
  selectedResolution: string
  customWidth: number
  customHeight: number
  onResolutionChange: (resolution: string) => void
  onCustomWidthChange: (width: number) => void
  onCustomHeightChange: (height: number) => void
  aspectLocked: boolean
  onAspectLockToggle: () => void
  onSwapDimensions: () => void
  // New props for model-based validation
  modelArchitecture?: string
}

export default function ResolutionSelector({
  selectedResolution,
  customWidth,
  customHeight,
  onResolutionChange,
  onCustomWidthChange,
  onCustomHeightChange,
  aspectLocked,
  onAspectLockToggle,
  onSwapDimensions,
  modelArchitecture = 'SD 1.5'
}: ResolutionSelectorProps) {
  const megapixels = (customWidth * customHeight) / 1000000
  const showVramWarning = megapixels > 1.0
  
  // Validation for diffusion models (must be multiples of 8)
  const widthError = customWidth % 8 !== 0
  const heightError = customHeight % 8 !== 0
  
  // Model-specific resolution warnings
  const maxResolution = useMemo(() => {
    switch (modelArchitecture) {
      case 'SDXL':
        return { width: 1536, height: 1536 }
      case 'SD 1.5':
        return { width: 512, height: 768 }
      default:
        return { width: 1024, height: 1024 }
    }
  }, [modelArchitecture])
  
  const resolutionWarning = useMemo(() => {
    if (modelArchitecture === 'SD 1.5') {
      if (customWidth > 512 || customHeight > 768) {
        return 'SD 1.5 models may produce artifacts at high resolutions. Consider using 512x768 or lower.'
      }
    } else if (modelArchitecture === 'SDXL') {
      if (customWidth > 1536 || customHeight > 1536) {
        return 'Resolution exceeds SDXL native limit (1536x1536). Results may be degraded.'
      }
    }
    return null
  }, [modelArchitecture, customWidth, customHeight])

  return (
    <div className="space-y-3">
      <label className="sidebar-label">
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
        </svg>
        Dimensions
      </label>
      <div className="grid grid-cols-4 gap-1.5">
        {resolutions.map(res => (
          <button 
            key={res.value} 
            onClick={() => onResolutionChange(res.value)} 
            className={clsx(
              "aspect-btn rounded-lg aspect-square flex flex-col items-center justify-center", 
              selectedResolution === res.value && "active"
            )} 
            title={res.sublabel}
          >
            <AspectIcon icon={res.icon} />
            <span className="text-xs font-medium leading-none mt-1">{res.label}</span>
            <span className="text-[10px] text-zinc-600 leading-none">{res.sublabel}</span>
          </button>
        ))}
      </div>

      {/* Custom Resolution Panel */}
      {selectedResolution === 'custom' && (
        <div className="pt-2">
          <div className="liquid-glass-input border border-iris-border rounded-xl p-3">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-iris-border/50">
              <span className="text-[10px] text-zinc-500 uppercase font-semibold">Custom Size</span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-zinc-400">{megapixels.toFixed(2)} MP</span>
                {showVramWarning && (
                  <span className="text-[10px] text-amber-400 flex items-center gap-1">
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    High VRAM
                  </span>
                )}
              </div>
            </div>
            
            {/* Resolution Validation Errors */}
            {(widthError || heightError) && (
              <div className="mb-3 p-2 bg-red-500/10 border border-red-500/30 rounded-lg text-[10px] text-red-400">
                <div className="flex items-center gap-1.5">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Dimensions must be multiples of 8 for diffusion models
                </div>
                {widthError && <div className="ml-4">• Width: {customWidth} is not divisible by 8</div>}
                {heightError && <div className="ml-4">• Height: {customHeight} is not divisible by 8</div>}
              </div>
            )}
            
            {/* Model-specific Resolution Warning */}
            {resolutionWarning && (
              <div className="mb-3 p-2 bg-amber-500/10 border border-amber-500/30 rounded-lg text-[10px] text-amber-400">
                <div className="flex items-center gap-1.5">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  {resolutionWarning}
                </div>
              </div>
            )}
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <label className="text-[10px] text-zinc-500 uppercase font-semibold block mb-1.5">Width</label>
                <input 
                  type="number" 
                  value={customWidth} 
                  min={256} 
                  max={2048} 
                  step={1} 
                  onChange={(e) => onCustomWidthChange(Number(e.target.value))} 
                  className="bg-iris-bg border border-iris-border rounded-lg px-3 py-2 w-full text-white text-sm font-mono focus:border-iris-accent focus:outline-none transition-all" 
                />
              </div>
              <div className="flex flex-col items-center pt-5">
                <button 
                  onClick={onAspectLockToggle} 
                  className={clsx(
                    "p-1.5 rounded-lg border border-iris-border bg-iris-card text-zinc-500 hover:text-white hover:border-white/20 transition-all", 
                    aspectLocked && "text-iris-accent border-iris-accent/50 bg-iris-accent/10"
                  )} 
                  title="Lock Aspect Ratio"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path 
                      strokeLinecap="round" 
                      strokeLinejoin="round" 
                      strokeWidth={2} 
                      d={aspectLocked 
                        ? "M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" 
                        : "M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z"
                      } 
                    />
                  </svg>
                </button>
              </div>
              <div className="flex-1">
                <label className="text-[10px] text-zinc-500 uppercase font-semibold block mb-1.5">Height</label>
                <input 
                  type="number" 
                  value={customHeight} 
                  min={256} 
                  max={2048} 
                  step={1} 
                  onChange={(e) => onCustomHeightChange(Number(e.target.value))} 
                  className="bg-iris-bg border border-iris-border rounded-lg px-3 py-2 w-full text-white text-sm font-mono focus:border-iris-accent focus:outline-none transition-all" 
                />
              </div>
            </div>
            <div className="flex gap-2 mt-3">
              <button 
                onClick={onSwapDimensions} 
                className="flex-1 py-1.5 px-3 rounded-lg border border-iris-border bg-iris-card text-zinc-400 hover:text-white hover:border-white/20 transition-all text-xs flex items-center justify-center gap-1.5"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                </svg>
                Swap
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
