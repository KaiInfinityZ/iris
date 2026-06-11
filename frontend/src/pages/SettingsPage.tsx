import { useEffect, useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { clsx } from 'clsx'
import { getGpuInfo, getVersionInfo, getOutputGallery, getSettings, saveSettings, Settings } from '../lib/api'

// Reusable Toggle Component
function Toggle({ checked, onChange, color = 'purple' }) {
  const colors = {
    purple: 'bg-purple-500',
    blue: 'bg-blue-500',
    red: 'bg-red-500',
    indigo: 'bg-indigo-500',
    green: 'bg-green-500',
  }
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={clsx(
        "relative w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none",
        checked ? colors[color] : "bg-zinc-700"
      )}
    >
      <span
        className={clsx(
          "absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200",
          checked && "translate-x-5"
        )}
      />
    </button>
  )
}

export default function SettingsPage() {
  const [gpuInfo, setGpuInfo] = useState(null)
  const [versionInfo, setVersionInfo] = useState(null)
  const [stats, setStats] = useState({ images: 0, storage: '0 MB' })
  const [dramEnabled, setDramEnabled] = useState(false)
  const [vramThreshold, setVramThreshold] = useState(6)
  const [maxDram, setMaxDram] = useState(16)
  const [discordEnabled, setDiscordEnabled] = useState(false)
  const [discordStatus, setDiscordStatus] = useState('Not configured')
  const [activeSection, setActiveSection] = useState('overview')
  const [autoSaveStatus, setAutoSaveStatus] = useState('')
  const lastSettingsRef = useRef(null)
  const saveTimeoutRef = useRef(null)

  useEffect(() => {
    loadData()
    loadSettingsFromServer()
    loadDiscordStatus()
    const gpuInterval = setInterval(loadGpuInfo, 3000)
    const settingsInterval = setInterval(loadSettingsFromServer, 2000)
    const discordInterval = setInterval(loadDiscordStatus, 5000)
    return () => {
      clearInterval(gpuInterval)
      clearInterval(settingsInterval)
      clearInterval(discordInterval)
    }
  }, [])

  async function loadSettingsFromServer() {
    try {
      const data = await getSettings()
      const settings = (data.settings || data) as Settings
      const settingsStr = JSON.stringify(settings)
      if (lastSettingsRef.current === settingsStr) return
      lastSettingsRef.current = settingsStr
      
      if (settings.dramEnabled !== undefined) setDramEnabled(settings.dramEnabled)
      if (settings.vramThreshold !== undefined) setVramThreshold(settings.vramThreshold)
      if (settings.maxDram !== undefined) setMaxDram(settings.maxDram)
      if (settings.discordEnabled !== undefined) setDiscordEnabled(settings.discordEnabled)
    } catch (e) { console.error('Failed to load settings:', e) }
  }

  // Autosave function with debounce
  const autoSave = useCallback(async (settings) => {
    try {
      setAutoSaveStatus('Saving...')
      await saveSettings(settings)
      lastSettingsRef.current = JSON.stringify(settings)
      setAutoSaveStatus('Saved')
      setTimeout(() => setAutoSaveStatus(''), 2000)
    } catch (e) {
      console.error('Failed to save settings:', e)
      setAutoSaveStatus('Error')
      setTimeout(() => setAutoSaveStatus(''), 3000)
    }
  }, [])

  // Trigger autosave when settings change (excluding discordEnabled which is handled separately)
  useEffect(() => {
    // Skip initial load
    if (lastSettingsRef.current === null) return
    
    const currentSettings = {
      dramEnabled: dramEnabled,
      vramThreshold: vramThreshold,
      maxDram: maxDram,
    }
    
    // Don't save if nothing changed
    if (JSON.stringify(currentSettings) === lastSettingsRef.current) return
    
    // Debounce save
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    saveTimeoutRef.current = setTimeout(() => {
      autoSave(currentSettings)
    }, 500)
    
    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    }
  }, [dramEnabled, vramThreshold, maxDram, autoSave])

  async function handleDiscordToggle(enabled) {
    setDiscordEnabled(enabled)
    if (enabled) {
      setDiscordStatus('Starting...')
      try {
        const response = await fetch('/api/discord-bot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: true })
        })
        const data = await response.json()
        if (data.success) {
          setDiscordStatus('Running')
        } else {
          const errorMsg = data.message || 'Failed'
          setDiscordStatus(errorMsg === 'Bot token not configured' ? 'Token missing' : errorMsg)
          setDiscordEnabled(false)
        }
      } catch (e) {
        setDiscordStatus('Server offline')
        setDiscordEnabled(false)
      }
    } else {
      setDiscordStatus('Stopping...')
      try {
        await fetch('/api/discord-bot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: false })
        })
        setDiscordStatus('Not configured')
      } catch (e) {
        setDiscordStatus('Server offline')
      }
    }
  }

  async function loadDiscordStatus() {
    try {
      const response = await fetch('/api/discord-bot/status')
      const data = await response.json()
      if (data.running) {
        setDiscordStatus('Running')
        setDiscordEnabled(true)
      } else if (!discordEnabled) {
        setDiscordStatus('Not configured')
      }
    } catch (e) { /* ignore */ }
  }

  async function loadData() {
    loadGpuInfo()
    loadVersionInfo()
    loadStats()
  }

  async function loadGpuInfo() {
    try {
      const data = await getGpuInfo()
      setGpuInfo(data)
    } catch (e) { console.error('GPU info error:', e) }
  }

  async function loadVersionInfo() {
    try {
      const data = await getVersionInfo()
      setVersionInfo(data)
    } catch (e) { console.error('Version info error:', e) }
  }

  async function loadStats() {
    try {
      const data = await getOutputGallery()
      const count = data.images?.length || 0
      setStats({ images: count, storage: `${(count * 1.5).toFixed(1)} MB` })
    } catch (e) { console.error('Stats error:', e) }
  }

  const gpuLoad = gpuInfo?.gpu?.gpu_utilization ?? 0
  const gpuTemp = gpuInfo?.gpu?.gpu_temp ?? 0
  const vramUsed = gpuInfo?.gpu?.vram_used ?? 0
  const vramTotal = gpuInfo?.gpu?.vram_total ?? 4
  const vramPerc = vramTotal > 0 ? (vramUsed / vramTotal * 100) : 0
  const powerDraw = gpuInfo?.gpu?.power_draw ?? 0
  const gpuName = gpuInfo?.gpu?.gpu_name ?? '--'
  const cpuPercent = gpuInfo?.gpu?.cpu_percent ?? 0
  const cpuFreq = gpuInfo?.gpu?.cpu_freq ?? 0
  const cpuCores = gpuInfo?.gpu?.cpu_cores ?? 0
  const ramUsed = gpuInfo?.gpu?.ram_used ?? 0
  const ramTotal = gpuInfo?.gpu?.ram_total ?? 0
  const ramPercent = gpuInfo?.gpu?.ram_percent ?? 0

  const navItems = [
    { id: 'overview', label: 'Overview', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
    { id: 'generation', label: 'Generation', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
    { id: 'integrations', label: 'Integrations', icon: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1' },
    { id: 'system', label: 'System', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' },
  ]

  return (
    <div className="flex h-screen w-full overflow-hidden text-sm bg-iris-bg">
      {/* Sidebar */}
      <aside className="w-[320px] lg:w-[360px] flex flex-col bg-iris-panel border-r border-iris-border flex-shrink-0">
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
              <span className="text-[9px] font-mono text-purple-400/80 tracking-widest">DASHBOARD</span>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="px-3 py-2 border-b border-iris-border">
          <div className="flex gap-1 p-1 bg-iris-bg/50 rounded-lg">
            <Link to="/" className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md text-zinc-400 hover:text-white hover:bg-white/5 transition-all">Home</Link>
            <Link to="/generate" className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md text-zinc-400 hover:text-white hover:bg-white/5 transition-all">Create</Link>
            <Link to="/gallery" className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md text-zinc-400 hover:text-white hover:bg-white/5 transition-all">Gallery</Link>
            <span className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md bg-iris-accent/20 text-iris-accentLight border border-iris-accent/30">Dashboard</span>
          </div>
        </nav>

        {/* Dashboard Nav */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-3">
          <div className="text-[10px] text-zinc-500 uppercase font-semibold tracking-wider mb-3 px-2">Navigation</div>
          <div className="space-y-1">
            {navItems.map(item => (
              <button
                key={item.id}
                onClick={() => setActiveSection(item.id)}
                className={clsx(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all",
                  activeSection === item.id
                    ? "bg-iris-accent/20 text-iris-accentLight border border-iris-accent/30"
                    : "text-zinc-400 hover:text-white hover:bg-white/5"
                )}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} />
                </svg>
                {item.label}
              </button>
            ))}
          </div>

          {/* Quick Stats in Sidebar */}
          <div className="mt-6">
            <div className="text-[10px] text-zinc-500 uppercase font-semibold tracking-wider mb-3 px-2">Quick Stats</div>
            <div className="space-y-2">
              <div className="p-3 bg-iris-card rounded-xl border border-iris-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-zinc-500 uppercase">GPU</span>
                  <span className="text-xs font-mono text-iris-accent">{Math.round(gpuLoad)}%</span>
                </div>
                <div className="w-full bg-black/30 h-1.5 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${gpuLoad}%`, background: 'linear-gradient(90deg, #8b5cf6, #a78bfa)' }} />
                </div>
              </div>
              <div className="p-3 bg-iris-card rounded-xl border border-iris-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] text-zinc-500 uppercase">VRAM</span>
                  <span className="text-xs font-mono text-iris-accent">{vramUsed.toFixed(1)}/{vramTotal.toFixed(0)}GB</span>
                </div>
                <div className="w-full bg-black/30 h-1.5 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${vramPerc}%`, background: 'linear-gradient(90deg, #6366f1, #818cf8)' }} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Autosave Status */}
        <div className="p-4 border-t border-iris-border">
          <div className="flex items-center justify-center gap-2 text-sm">
            {autoSaveStatus === 'Saving...' && (
              <>
                <svg className="w-4 h-4 animate-spin text-iris-accent" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span className="text-zinc-400">Saving...</span>
              </>
            )}
            {autoSaveStatus === 'Saved' && (
              <>
                <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span className="text-emerald-400">Saved</span>
              </>
            )}
            {autoSaveStatus === 'Error' && (
              <>
                <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span className="text-red-400">Save failed</span>
              </>
            )}
            {!autoSaveStatus && (
              <span className="text-zinc-500 text-xs">Autosave enabled</span>
            )}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="p-8">

          {/* Overview Section */}
          {activeSection === 'overview' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-white mb-1">Dashboard Overview</h1>
                <p className="text-zinc-500">Monitor your system performance and resources.</p>
              </div>

              {/* Stats Cards */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-5 bg-gradient-to-br from-purple-500/10 to-purple-600/5 rounded-2xl border border-purple-500/20">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
                      <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                    </div>
                    <div className="text-[10px] text-zinc-500 uppercase font-semibold">Images</div>
                  </div>
                  <div className="text-3xl font-bold text-white">{stats.images}</div>
                  <div className="text-xs text-zinc-500 mt-1">{stats.storage} storage</div>
                </div>

                <div className="p-5 bg-gradient-to-br from-blue-500/10 to-blue-600/5 rounded-2xl border border-blue-500/20">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/20 flex items-center justify-center">
                      <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>
                    </div>
                    <div className="text-[10px] text-zinc-500 uppercase font-semibold">GPU Temp</div>
                  </div>
                  <div className="text-3xl font-bold text-white">{gpuTemp > 0 ? `${Math.round(gpuTemp)}°C` : '--'}</div>
                  <div className="text-xs text-zinc-500 mt-1">{powerDraw > 0 ? `${powerDraw.toFixed(0)}W power` : 'Idle'}</div>
                </div>

                <div className="p-5 bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 rounded-2xl border border-emerald-500/20">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                      <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" /></svg>
                    </div>
                    <div className="text-[10px] text-zinc-500 uppercase font-semibold">CPU</div>
                  </div>
                  <div className="text-3xl font-bold text-white">{Math.round(cpuPercent)}%</div>
                  <div className="text-xs text-zinc-500 mt-1">{cpuCores} cores @ {cpuFreq.toFixed(1)}GHz</div>
                </div>

                <div className="p-5 bg-gradient-to-br from-amber-500/10 to-amber-600/5 rounded-2xl border border-amber-500/20">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center">
                      <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                    </div>
                    <div className="text-[10px] text-zinc-500 uppercase font-semibold">RAM</div>
                  </div>
                  <div className="text-3xl font-bold text-white">{ramUsed.toFixed(1)}GB</div>
                  <div className="text-xs text-zinc-500 mt-1">of {ramTotal.toFixed(0)}GB ({Math.round(ramPercent)}%)</div>
                </div>
              </div>

              {/* Hardware Monitoring */}
              <div className="grid grid-cols-2 gap-6">
                {/* GPU Card */}
                <div className="p-6 bg-iris-panel rounded-2xl border border-iris-border">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-semibold text-white">GPU Performance</h3>
                    <span className="text-xs text-zinc-500 font-mono">{gpuName.replace('NVIDIA ', '').replace('GeForce ', '')}</span>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-xs text-zinc-400">Utilization</span>
                        <span className="text-xs font-mono text-white">{Math.round(gpuLoad)}%</span>
                      </div>
                      <div className="w-full bg-black/30 h-3 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${gpuLoad}%`, background: gpuLoad > 80 ? 'linear-gradient(90deg, #ef4444, #f87171)' : 'linear-gradient(90deg, #8b5cf6, #a78bfa)' }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-xs text-zinc-400">VRAM</span>
                        <span className="text-xs font-mono text-white">{vramUsed.toFixed(1)} / {vramTotal.toFixed(1)} GB</span>
                      </div>
                      <div className="w-full bg-black/30 h-3 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${vramPerc}%`, background: vramPerc > 85 ? 'linear-gradient(90deg, #ef4444, #f87171)' : 'linear-gradient(90deg, #6366f1, #818cf8)' }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* System Card */}
                <div className="p-6 bg-iris-panel rounded-2xl border border-iris-border">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-semibold text-white">System Resources</h3>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-xs text-zinc-400">CPU Usage</span>
                        <span className="text-xs font-mono text-white">{Math.round(cpuPercent)}%</span>
                      </div>
                      <div className="w-full bg-black/30 h-3 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${cpuPercent}%`, background: cpuPercent > 80 ? 'linear-gradient(90deg, #ef4444, #f87171)' : 'linear-gradient(90deg, #10b981, #34d399)' }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-xs text-zinc-400">Memory</span>
                        <span className="text-xs font-mono text-white">{ramUsed.toFixed(1)} / {ramTotal.toFixed(1)} GB</span>
                      </div>
                      <div className="w-full bg-black/30 h-3 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${ramPercent}%`, background: ramPercent > 85 ? 'linear-gradient(90deg, #ef4444, #f87171)' : 'linear-gradient(90deg, #f59e0b, #fbbf24)' }} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Generation Section */}
          {activeSection === 'generation' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-white mb-1">Generation Settings</h1>
                <p className="text-zinc-500">Configure image generation behavior and memory management.</p>
              </div>

              <div className="grid gap-4">
                {/* DRAM Extension */}
                <div className="p-6 bg-iris-panel rounded-2xl border border-iris-border">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center">
                        <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>
                      </div>
                      <div>
                        <h3 className="text-base font-semibold text-white">DRAM Extension</h3>
                        <p className="text-xs text-zinc-500">Use system RAM as VRAM fallback for larger generations</p>
                      </div>
                    </div>
                    <Toggle checked={dramEnabled} onChange={setDramEnabled} color="blue" />
                  </div>
                  
                  {dramEnabled && (
                    <div className="mt-4 pt-4 border-t border-iris-border space-y-4">
                      <div>
                        <div className="flex justify-between mb-2">
                          <label className="text-sm text-zinc-400">VRAM Threshold</label>
                          <span className="text-sm font-mono text-blue-400">{vramThreshold} GB</span>
                        </div>
                        <input type="range" min={2} max={12} value={vramThreshold} step={1} onChange={(e) => setVramThreshold(Number(e.target.value))} className="w-full accent-blue-500" />
                        <p className="text-[10px] text-zinc-600 mt-1">Enable DRAM extension when VRAM is below this threshold</p>
                      </div>
                      <div>
                        <div className="flex justify-between mb-2">
                          <label className="text-sm text-zinc-400">Max DRAM Usage</label>
                          <span className="text-sm font-mono text-blue-400">{maxDram} GB</span>
                        </div>
                        <input type="range" min={4} max={64} value={maxDram} step={4} onChange={(e) => setMaxDram(Number(e.target.value))} className="w-full accent-blue-500" />
                        <p className="text-[10px] text-zinc-600 mt-1">Maximum system RAM to use for model offloading</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Integrations Section */}
          {activeSection === 'integrations' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-white mb-1">Integrations</h1>
                <p className="text-zinc-500">Connect I.R.I.S. with external services.</p>
              </div>

              {/* Discord */}
              <div className="p-6 bg-iris-panel rounded-2xl border border-iris-border">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                      <svg className="w-6 h-6 text-indigo-400" viewBox="0 0 24 24" fill="currentColor"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" /></svg>
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-white">Discord Bot</h3>
                      <p className="text-xs text-zinc-500">Auto-share generated images to Discord channels</p>
                    </div>
                  </div>
                  <Toggle checked={discordEnabled} onChange={handleDiscordToggle} color="indigo" />
                </div>
                
                <div className="flex items-center gap-3 p-4 bg-iris-bg rounded-xl">
                  <span className={clsx(
                    "w-2.5 h-2.5 rounded-full",
                    discordStatus === 'Running' ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]' :
                    discordStatus === 'Starting...' || discordStatus === 'Stopping...' ? 'bg-yellow-500 animate-pulse' :
                    discordStatus === 'Token missing' || discordStatus === 'Failed' || discordStatus === 'Server offline' ? 'bg-red-500' :
                    'bg-zinc-500'
                  )} />
                  <span className={clsx(
                    "text-sm font-medium",
                    discordStatus === 'Running' ? 'text-green-400' :
                    discordStatus === 'Starting...' || discordStatus === 'Stopping...' ? 'text-yellow-400' :
                    discordStatus === 'Token missing' || discordStatus === 'Failed' || discordStatus === 'Server offline' ? 'text-red-400' :
                    'text-zinc-400'
                  )}>{discordStatus}</span>
                </div>

                {discordStatus === 'Token missing' && (
                  <div className="mt-4 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
                    <p className="text-sm text-amber-300">Configure your Discord bot token in the .env file to enable this feature.</p>
                  </div>
                )}
              </div>

              {/* Future Integrations Placeholder */}
              <div className="p-6 bg-iris-panel/50 rounded-2xl border border-dashed border-iris-border">
                <div className="text-center py-8">
                  <div className="w-16 h-16 rounded-2xl bg-iris-card mx-auto mb-4 flex items-center justify-center">
                    <svg className="w-8 h-8 text-zinc-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
                  </div>
                  <h3 className="text-base font-semibold text-zinc-400 mb-1">More Integrations Coming</h3>
                  <p className="text-sm text-zinc-600">Additional integrations will be added in future updates.</p>
                </div>
              </div>
            </div>
          )}

          {/* System Section */}
          {activeSection === 'system' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-bold text-white mb-1">System Information</h1>
                <p className="text-zinc-500">View your software stack and system details.</p>
              </div>

              <div className="grid grid-cols-2 gap-6">
                {/* Software Stack */}
                <div className="p-6 bg-iris-panel rounded-2xl border border-iris-border">
                  <h3 className="text-base font-semibold text-white mb-4">Software Stack</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center py-3 border-b border-iris-border">
                      <span className="text-zinc-500">Operating System</span>
                      <span className="text-white font-medium">{versionInfo?.os || 'Loading...'}</span>
                    </div>
                    <div className="flex justify-between items-center py-3 border-b border-iris-border">
                      <span className="text-zinc-500">Python</span>
                      <span className="text-white font-mono">{versionInfo?.python_version || '--'}</span>
                    </div>
                    <div className="flex justify-between items-center py-3 border-b border-iris-border">
                      <span className="text-zinc-500">PyTorch</span>
                      <span className="text-white font-mono">{versionInfo?.pytorch_version || '--'}</span>
                    </div>
                    <div className="flex justify-between items-center py-3 border-b border-iris-border">
                      <span className="text-zinc-500">CUDA</span>
                      <span className="text-white font-mono">{versionInfo?.cuda_version || '--'}</span>
                    </div>
                    <div className="flex justify-between items-center py-3">
                      <span className="text-zinc-500">I.R.I.S. Core</span>
                      <span className="text-iris-accentLight font-bold font-mono">v1.2.0</span>
                    </div>
                  </div>
                </div>

                {/* Hardware Info */}
                <div className="p-6 bg-iris-panel rounded-2xl border border-iris-border">
                  <h3 className="text-base font-semibold text-white mb-4">Hardware</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center py-3 border-b border-iris-border">
                      <span className="text-zinc-500">GPU</span>
                      <span className="text-white font-medium">{gpuName}</span>
                    </div>
                    <div className="flex justify-between items-center py-3 border-b border-iris-border">
                      <span className="text-zinc-500">VRAM</span>
                      <span className="text-white font-mono">{vramTotal.toFixed(1)} GB</span>
                    </div>
                    <div className="flex justify-between items-center py-3 border-b border-iris-border">
                      <span className="text-zinc-500">CPU Cores</span>
                      <span className="text-white font-mono">{cpuCores}</span>
                    </div>
                    <div className="flex justify-between items-center py-3">
                      <span className="text-zinc-500">System RAM</span>
                      <span className="text-white font-mono">{ramTotal.toFixed(0)} GB</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* About */}
              <div className="p-6 bg-gradient-to-br from-iris-accent/10 to-indigo-600/5 rounded-2xl border border-iris-accent/20">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 via-purple-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/20">
                    <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-white">I.R.I.S.</h3>
                    <p className="text-sm text-zinc-400">Intelligent Rendering & Image Synthesis</p>
                    <p className="text-xs text-zinc-500 mt-1">Local AI Image Generation powered by Stable Diffusion</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
