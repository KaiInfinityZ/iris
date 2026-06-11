import { useState } from 'react'
import { clsx } from 'clsx'
import { qualityPresets, type QualityPreset } from '../store/useStore'

interface QualityPresetSelectorProps {
  selectedPreset: string
  onPresetChange: (preset: string) => void
}

export default function QualityPresetSelector({ selectedPreset, onPresetChange }: QualityPresetSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const preset = qualityPresets[selectedPreset]

  return (
    <div className="space-y-2">
      <label className="sidebar-label">
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        Generation Mode
      </label>
      <div className="relative">
        <button 
          onClick={() => setIsOpen(!isOpen)} 
          className="w-full liquid-glass-input border border-iris-border rounded-xl text-sm text-white p-3 flex items-center justify-between hover:border-iris-accent/50 transition-all"
        >
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-9 h-9 rounded-lg bg-zinc-800 flex items-center justify-center flex-shrink-0 border border-white/10">
              <svg className="w-5 h-5 text-iris-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div className="text-left overflow-hidden">
              <span className="truncate font-medium text-zinc-300 block">{preset.name}</span>
              <span className="text-[10px] text-zinc-500 truncate block">{preset.desc}</span>
            </div>
          </div>
          <svg 
            className={clsx("w-4 h-4 text-zinc-500 transition-transform", isOpen && "rotate-180")} 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        {isOpen && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-zinc-900/95 backdrop-blur-xl border border-iris-border rounded-xl shadow-2xl z-50 overflow-hidden">
            {Object.entries(qualityPresets).map(([key, presetItem]) => (
              <div 
                key={key} 
                onClick={() => { 
                  onPresetChange(key)
                  setIsOpen(false) 
                }} 
                className={clsx(
                  "p-2.5 hover:bg-iris-accent/10 cursor-pointer flex items-center gap-3 transition-colors border-b border-iris-border/50 last:border-0", 
                  selectedPreset === key && "bg-iris-accent/5"
                )}
              >
                <div 
                  className={clsx(
                    "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0", 
                    key === 'fast' && "bg-emerald-500/20", 
                    key === 'balanced' && "bg-iris-accent/20", 
                    key === 'high' && "bg-amber-500/20", 
                    key === 'extreme' && "bg-red-500/20"
                  )}
                >
                  <svg 
                    className={clsx(
                      "w-5 h-5", 
                      key === 'fast' && "text-emerald-400", 
                      key === 'balanced' && "text-iris-accent", 
                      key === 'high' && "text-amber-400", 
                      key === 'extreme' && "text-red-400"
                    )} 
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div>
                  <span className="font-medium text-zinc-300 block text-sm">{presetItem.name}</span>
                  <span className="text-[10px] text-zinc-500">{presetItem.desc}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
