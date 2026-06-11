import { useState } from 'react'
import { clsx } from 'clsx'
import { useStore } from '../store/useStore'
import { getModelConfig } from '../modelsConfig'

interface ModelSelectorProps {
  selectedModelId: string
  onModelChange: (modelId: string) => void
}

export default function ModelSelector({ selectedModelId, onModelChange }: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [showInfo, setShowInfo] = useState(false)
  const models = useStore((state) => state.models)
  const selectedModel = models.find(m => m.id === selectedModelId)
  
  // Get extended model config from modelsConfig
  const modelConfig = getModelConfig(selectedModelId)

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="sidebar-label">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
          </svg>
          Model
        </label>
        {modelConfig && (
          <button 
            onClick={() => setShowInfo(!showInfo)}
            className="text-[10px] text-zinc-500 hover:text-iris-accent transition-colors flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Info
          </button>
        )}
      </div>
      <div className="relative">
        <button 
          onClick={() => setIsOpen(!isOpen)} 
          className="w-full liquid-glass-input border border-iris-border rounded-xl text-sm text-white p-3 flex items-center justify-between hover:border-iris-accent/50 transition-all"
        >
          <div className="flex items-center gap-3 overflow-hidden">
            {selectedModel?.image && (
              <div 
                className="w-9 h-9 rounded-lg bg-zinc-800 flex-shrink-0 bg-cover bg-center border border-white/10" 
                style={{ backgroundImage: `url(${selectedModel.image})` }} 
              />
            )}
            <span className="truncate font-medium text-zinc-300">
              {selectedModel?.name || 'Select Model'}
            </span>
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
          <div className="absolute top-full left-0 right-0 mt-2 bg-zinc-900/95 backdrop-blur-xl border border-iris-border rounded-xl shadow-2xl z-50 max-h-[300px] overflow-y-auto">
            {models.map(model => (
              <div 
                key={model.id} 
                onClick={() => { 
                  onModelChange(model.id)
                  setIsOpen(false) 
                }} 
                className="p-2.5 hover:bg-iris-accent/10 cursor-pointer flex items-center gap-3 transition-colors border-b border-iris-border/50 last:border-0"
              >
                {model.image ? (
                  <img 
                    src={model.image} 
                    className="w-10 h-10 rounded-lg object-cover bg-zinc-800 border border-white/5" 
                    alt={model.name} 
                  />
                ) : (
                  <div className="w-10 h-10 rounded-lg bg-zinc-800 flex items-center justify-center text-xs text-zinc-500 font-mono border border-white/5">
                    {model.name.substring(0,2).toUpperCase()}
                  </div>
                )}
                <span className="text-sm text-zinc-300">{model.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Model Info Panel */}
      {showInfo && modelConfig && (
        <div className="mt-2 p-3 bg-iris-bg/50 border border-iris-border rounded-xl space-y-2 text-xs">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-zinc-500">Architecture</span>
              <p className="text-white font-medium">{modelConfig.architecture}</p>
            </div>
            <div>
              <span className="text-zinc-500">VRAM</span>
              <p className="text-white font-medium">~{modelConfig.vram_gb}GB</p>
            </div>
            <div>
              <span className="text-zinc-500">Token Limit</span>
              <p className="text-white font-medium">{modelConfig.token_limit || 'Unlimited'}</p>
            </div>
            <div>
              <span className="text-zinc-500">LoRA Support</span>
              <p className={clsx("font-medium", modelConfig.lora_supported ? "text-emerald-400" : "text-red-400")}>
                {modelConfig.lora_supported ? 'Yes' : 'No'}
              </p>
            </div>
          </div>
          <div>
            <span className="text-zinc-500">Prompt Style</span>
            <p className="text-white font-medium">{modelConfig.prompt_style}</p>
          </div>
          <div>
            <a 
              href={modelConfig.hf_url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-iris-accent hover:text-iris-accentLight transition-colors"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              View on HuggingFace
            </a>
          </div>
        </div>
      )}
    </div>
  )
}