import { useState } from 'react'
import { clsx } from 'clsx'

interface PromptInputProps {
  prompt: string
  negativePrompt: string
  onPromptChange: (prompt: string) => void
  onNegativePromptChange: (negativePrompt: string) => void
  onRandomPrompt: () => void
  // New prop for negative prompt support
  negativePromptSupported?: boolean
}

export default function PromptInput({
  prompt,
  negativePrompt,
  onPromptChange,
  onNegativePromptChange,
  onRandomPrompt,
  negativePromptSupported = true
}: PromptInputProps) {
  const [showNegativePrompt, setShowNegativePrompt] = useState(false)

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <label className="sidebar-label mb-0">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          Prompt
        </label>
        <button 
          onClick={onRandomPrompt} 
          className="p-1.5 rounded-lg hover:bg-white/5 text-zinc-500 hover:text-iris-accent transition" 
          title="Random Prompt"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
      <div className="liquid-glass-input rounded-xl overflow-hidden">
        <textarea 
          value={prompt} 
          onChange={(e) => onPromptChange(e.target.value)} 
          className="w-full bg-transparent text-white p-3 text-sm focus:ring-0 resize-y min-h-[100px] placeholder-zinc-600 leading-relaxed outline-none" 
          placeholder="Describe your image..." 
        />
      </div>

      {/* Negative Prompt */}
      <details 
        open={showNegativePrompt} 
        onToggle={(e) => setShowNegativePrompt((e.target as HTMLDetailsElement).open)}
      >
        <summary className="flex items-center gap-2 cursor-pointer p-2 rounded-lg hover:bg-white/5 transition-colors select-none">
          <svg 
            className={clsx("w-3.5 h-3.5 text-zinc-500 transition-transform", showNegativePrompt && "rotate-90")} 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-[11px] font-medium text-zinc-500">Negative Prompt</span>
        </summary>
        <div className="mt-2 relative">
          <textarea 
            value={negativePrompt} 
            onChange={(e) => onNegativePromptChange(e.target.value)} 
            disabled={!negativePromptSupported}
            className={clsx(
              "w-full bg-iris-bg/30 text-white p-3 text-sm rounded-xl focus:ring-0 resize-y min-h-[80px] placeholder-zinc-600 leading-relaxed outline-none border border-iris-border/50",
              !negativePromptSupported && "opacity-50 cursor-not-allowed"
            )} 
            placeholder={negativePromptSupported ? "What to avoid in the image..." : "This model does not support negative prompts"}
          />
          {!negativePromptSupported && (
            <div className="absolute bottom-full left-0 mb-1 px-2 py-1 bg-amber-500/90 text-white text-[10px] rounded-md whitespace-nowrap" title="This model does not support negative prompts">
              This model does not support negative prompts
            </div>
          )}
        </div>
      </details>
    </div>
  )
}
