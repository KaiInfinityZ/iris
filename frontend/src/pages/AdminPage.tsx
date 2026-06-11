import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { clsx } from 'clsx'
import Sidebar from '../components/Sidebar'
import { getHealthInfo, getSettings, getModelsList, scanModels, setModelEnabled, deleteModel, type ModelInfo } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_URL || ''

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [logs, setLogs] = useState([])
  const [systemInfo, setSystemInfo] = useState(null)
  const [serverSettings, setServerSettings] = useState(null)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [models, setModels] = useState<ModelInfo[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [scanningModels, setScanningModels] = useState(false)

  useEffect(() => {
    const auth = localStorage.getItem('iris_admin_auth')
    if (auth === 'true') setIsAuthenticated(true)
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      loadSystemInfo()
      loadLogs()
      loadSettings()
      loadModels()
    }
  }, [isAuthenticated])

  async function loadSystemInfo() {
    try {
      const data = await getHealthInfo()
      setSystemInfo(data)
    } catch (e) {
      console.error('Failed to load system info:', e)
    }
  }

  async function loadSettings() {
    try {
      const data = await getSettings()
      setServerSettings(data.settings || data)
    } catch (e) {
      console.error('Failed to load settings:', e)
    }
  }

  async function loadLogs() {
    try {
      const res = await fetch(`${API_BASE}/api/admin/logs`)
      if (res.ok) {
        const data = await res.json()
        setLogs(data.logs || [])
      }
    } catch (e) {
      setLogs([{ time: new Date().toLocaleTimeString(), level: 'INFO', message: 'Server running' }])
    }
  }

  async function loadModels() {
    setModelsLoading(true)
    try {
      const data = await getModelsList()
      setModels(data.models || [])
    } catch (e) {
      console.error('Failed to load models:', e)
      setModels([])
    } finally {
      setModelsLoading(false)
    }
  }

  async function handleScanModels() {
    setScanningModels(true)
    try {
      const result = await scanModels()
      alert(`✅ Scan complete! Found ${result.models_found} models`)
      await loadModels()
    } catch (e) {
      alert('❌ Failed to scan models')
    } finally {
      setScanningModels(false)
    }
  }

  async function handleToggleModel(modelKey: string, currentlyEnabled: boolean) {
    try {
      await setModelEnabled(modelKey, !currentlyEnabled)
      await loadModels()
      alert(`✅ Model ${!currentlyEnabled ? 'enabled' : 'disabled'}`)
    } catch (e) {
      alert('❌ Failed to update model')
    }
  }

  async function handleDeleteModel(modelKey: string) {
    if (!confirm(`⚠️ Delete model "${modelKey}" from disk? This cannot be undone!`)) return
    try {
      await deleteModel(modelKey)
      await loadModels()
      alert('✅ Model deleted')
    } catch (e) {
      alert('❌ Failed to delete model')
    }
  }

  async function handleClearCache() {
    try {
      const res = await fetch(`${API_BASE}/api/admin/clear-cache`, { method: 'POST' })
      if (res.ok) alert('Cache cleared!')
    } catch (e) {
      alert('Failed to clear cache')
    }
  }

  async function handleRestartServer() {
    if (!confirm('Restart the server?')) return
    try {
      await fetch(`${API_BASE}/api/admin/restart`, { method: 'POST' })
      alert('Server restart initiated...')
    } catch (e) {
      alert('Restart signal sent')
    }
  }

  function handleLogin(e) {
    e.preventDefault()
    if (password === 'iris2026' || password === 'admin') {
      localStorage.setItem('iris_admin_auth', 'true')
      setIsAuthenticated(true)
      setError('')
    } else {
      setError('Invalid password')
    }
  }

  function handleLogout() {
    localStorage.removeItem('iris_admin_auth')
    setIsAuthenticated(false)
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-iris-bg flex items-center justify-center p-4">
        <div className="w-full max-w-md glass-panel p-8 rounded-2xl">
          <div className="text-center mb-8">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-red-500 via-orange-500 to-yellow-500 flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-white mb-2">Admin Access</h1>
            <p className="text-zinc-400 text-sm">Enter password to continue</p>
          </div>
          <form onSubmit={handleLogin} className="space-y-4">
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" className="w-full bg-iris-card border border-iris-border rounded-xl px-4 py-3 text-white placeholder-zinc-500 focus:outline-none focus:border-iris-accent" />
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button type="submit" className="btn-primary w-full py-3 rounded-xl font-bold text-white">Login</button>
          </form>
          <div className="mt-6 text-center">
            <Link to="/" className="text-zinc-500 hover:text-white text-sm">← Back to Home</Link>
          </div>
        </div>
      </div>
    )
  }

  const tabIcons = {
    overview: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>,
    models: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>,
    logs: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>,
    actions: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
    danger: <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>,
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'models', label: 'Models' },
    { id: 'logs', label: 'Logs' },
    { id: 'actions', label: 'Actions' },
    { id: 'danger', label: 'Danger' },
  ]

  return (
    <div className="flex h-screen w-full overflow-hidden text-sm">
      <Sidebar>
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="p-4 space-y-5">
            {/* Admin Badge */}
            <div className="p-3 bg-gradient-to-r from-red-500/20 to-orange-500/20 border border-red-500/30 rounded-xl">
              <div className="flex items-center gap-2 mb-1">
                <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
                <span className="text-white font-bold text-sm">Admin Panel</span>
              </div>
              <p className="text-zinc-400 text-xs">Server management & monitoring</p>
            </div>

            <div className="h-px bg-gradient-to-r from-transparent via-iris-border to-transparent" />

            {/* Tabs */}
            <div className="space-y-2">
              <label className="sidebar-label">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
                </svg>
                Sections
              </label>
              <div className="space-y-1">
                {tabs.map(tab => (
                  <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={clsx("w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all", activeTab === tab.id ? "bg-iris-accent/20 text-iris-accentLight border border-iris-accent/30" : "text-zinc-400 hover:text-white hover:bg-white/5")}>
                    {tabIcons[tab.id]}
                    <span className="text-sm font-medium">{tab.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="h-px bg-gradient-to-r from-transparent via-iris-border to-transparent" />

            {/* Quick Stats */}
            <div className="space-y-2">
              <label className="sidebar-label">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                System Status
              </label>
              <div className="space-y-2">
                <div className="flex justify-between items-center p-2.5 bg-iris-card rounded-lg border border-iris-border">
                  <span className="text-xs text-zinc-500">Server</span>
                  <span className="text-xs font-bold text-emerald-400">● Online</span>
                </div>
                <div className="flex justify-between items-center p-2.5 bg-iris-card rounded-lg border border-iris-border">
                  <span className="text-xs text-zinc-500">GPU</span>
                  <span className="text-xs font-bold text-purple-400 truncate max-w-[120px]" title={systemInfo?.gpu_name}>{systemInfo?.gpu_name?.split(' ').slice(-2).join(' ') || 'Loading...'}</span>
                </div>
                <div className="flex justify-between items-center p-2.5 bg-iris-card rounded-lg border border-iris-border">
                  <span className="text-xs text-zinc-500">VRAM</span>
                  <span className="text-xs font-bold text-blue-400">{systemInfo?.vram_total || 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Logout */}
        <div className="p-4 border-t border-iris-border bg-iris-panel">
          <button onClick={handleLogout} className="btn-secondary w-full py-3 rounded-xl font-medium text-sm flex items-center justify-center gap-2 text-red-400 hover:text-red-300">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Logout
          </button>
        </div>
      </Sidebar>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-iris-bg">
        <header className="h-12 border-b border-iris-border bg-iris-panel/80 backdrop-blur-sm flex items-center justify-between px-5 shrink-0">
          <div className="flex items-center gap-3">
            {tabIcons[activeTab]}
            <span className="text-white font-medium">{tabs.find(t => t.id === activeTab)?.label}</span>
          </div>
          <button onClick={() => { loadSystemInfo(); loadLogs(); loadSettings(); }} className="text-xs text-zinc-400 hover:text-white flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            Refresh
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Generation Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="glass-panel rounded-xl p-4 text-center">
                  <div className="text-3xl font-bold text-purple-400 font-mono">{systemInfo?.total_generations || 0}</div>
                  <div className="text-xs text-zinc-500 mt-1">Total Generations</div>
                </div>
                <div className="glass-panel rounded-xl p-4 text-center">
                  <div className="text-3xl font-bold text-blue-400 font-mono">{systemInfo?.total_generation_time ? `${Math.round(systemInfo.total_generation_time)}s` : '0s'}</div>
                  <div className="text-xs text-zinc-500 mt-1">Total Gen Time</div>
                </div>
                <div className="glass-panel rounded-xl p-4 text-center">
                  <div className="text-3xl font-bold text-emerald-400 font-mono">{systemInfo?.uptime || 'N/A'}</div>
                  <div className="text-xs text-zinc-500 mt-1">Uptime</div>
                </div>
                <div className="glass-panel rounded-xl p-4 text-center">
                  <div className="text-3xl font-bold text-pink-400 font-mono">{systemInfo?.model_loaded ? <svg className="w-8 h-8 mx-auto text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg> : <svg className="w-8 h-8 mx-auto text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" /></svg>}</div>
                  <div className="text-xs text-zinc-500 mt-1">Model Loaded</div>
                </div>
              </div>

              {/* System Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <StatCard title="Server Status" value="Online" color="green" icon="server" />
                <StatCard title="GPU" value={systemInfo?.gpu_name || 'Loading...'} color="purple" icon="gpu" />
                <StatCard title="VRAM Total" value={systemInfo?.vram_total || 'N/A'} color="blue" icon="memory" />
                <StatCard title="VRAM Used" value={systemInfo?.vram_used || 'N/A'} color="indigo" icon="memory" />
                <StatCard title="VRAM Free" value={systemInfo?.vram_free || 'N/A'} color="cyan" icon="memory" />
                <StatCard title="GPU Temp" value={systemInfo?.gpu_temp ? `${systemInfo.gpu_temp}°C` : 'N/A'} color="orange" icon="temp" />
                <StatCard title="GPU Load" value={systemInfo?.gpu_utilization ? `${systemInfo.gpu_utilization}%` : 'N/A'} color="yellow" icon="chip" />
                <StatCard title="Power Draw" value={systemInfo?.power_draw ? `${systemInfo.power_draw}W` : 'N/A'} color="red" icon="power" />
                <StatCard title="Device" value={systemInfo?.device || 'cuda'} color="violet" icon="chip" />
                <StatCard title="Model" value={systemInfo?.model_name || serverSettings?.model || 'No Model'} color="pink" icon="model" />
                <StatCard title="Discord Bot" value={serverSettings?.discordBotEnabled ? 'Running' : 'Stopped'} color="violet" icon="bot" />
              </div>

              {/* CPU & RAM Section */}
              <div className="glass-panel rounded-2xl p-6">
                <h3 className="text-white font-bold mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>
                  CPU & RAM
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div><span className="text-zinc-500 block text-xs">CPU Usage</span><span className="text-white font-bold">{systemInfo?.cpu_percent || 0}%</span></div>
                  <div><span className="text-zinc-500 block text-xs">CPU Cores</span><span className="text-white font-bold">{systemInfo?.cpu_cores || '-'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">CPU Freq</span><span className="text-white font-bold">{systemInfo?.cpu_freq ? `${systemInfo.cpu_freq} GHz` : '-'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">RAM Usage</span><span className="text-white font-bold">{systemInfo?.ram_percent || 0}%</span></div>
                  <div><span className="text-zinc-500 block text-xs">RAM Total</span><span className="text-white font-bold">{systemInfo?.ram_total || '-'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">RAM Used</span><span className="text-white font-bold">{systemInfo?.ram_used || '-'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">RAM Free</span><span className="text-white font-bold">{systemInfo?.ram_free || '-'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">VRAM %</span><span className="text-white font-bold">{systemInfo?.vram_percent || 0}%</span></div>
                </div>
              </div>

              {/* Software Versions */}
              <div className="glass-panel rounded-2xl p-6">
                <h3 className="text-white font-bold mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" /></svg>
                  Software Versions
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div><span className="text-zinc-500 block text-xs">I.R.I.S.</span><span className="text-white font-bold">v{systemInfo?.iris_version || '1.0.0'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">Python</span><span className="text-white font-bold">{systemInfo?.python_version || '-'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">PyTorch</span><span className="text-white font-bold">{systemInfo?.pytorch_version || '-'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">CUDA</span><span className="text-white font-bold">{systemInfo?.cuda_version || '-'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">OS</span><span className="text-white font-bold">{systemInfo?.os || '-'}</span></div>
                  <div><span className="text-zinc-500 block text-xs">GPU Name</span><span className="text-white font-bold truncate">{systemInfo?.gpu_name || '-'}</span></div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'models' && (
            <div className="space-y-6">
              {/* Scan Button */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-white">Model Management</h2>
                  <p className="text-sm text-zinc-400 mt-1">Manage AI models stored locally</p>
                </div>
                <button 
                  onClick={handleScanModels} 
                  disabled={scanningModels}
                  className="btn-primary px-4 py-2 rounded-lg text-sm flex items-center gap-2 disabled:opacity-50"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  {scanningModels ? 'Scanning...' : 'Scan Models'}
                </button>
              </div>

              {/* Models List */}
              {modelsLoading ? (
                <div className="glass-panel rounded-2xl p-8 text-center">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-iris-accent"></div>
                  <p className="text-zinc-400 mt-4">Loading models...</p>
                </div>
              ) : models.length === 0 ? (
                <div className="glass-panel rounded-2xl p-8 text-center">
                  <svg className="w-16 h-16 mx-auto text-zinc-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                  <p className="text-zinc-400 mb-2">No models found</p>
                  <p className="text-sm text-zinc-500">Click "Scan Models" to discover models in your local directory</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {['S', 'A', 'B', 'C'].map(tier => {
                    const tierModels = models.filter(m => m.tier === tier)
                    if (tierModels.length === 0) return null
                    
                    const tierColors = {
                      'S': 'from-yellow-500 to-orange-500',
                      'A': 'from-purple-500 to-pink-500',
                      'B': 'from-blue-500 to-cyan-500',
                      'C': 'from-gray-500 to-zinc-500',
                    }
                    
                    return (
                      <div key={tier}>
                        <div className={clsx("inline-flex items-center gap-2 px-3 py-1 rounded-full mb-3 bg-gradient-to-r", tierColors[tier])}>
                          <span className="text-white font-bold text-sm">Tier {tier}</span>
                        </div>
                        <div className="space-y-2">
                          {tierModels.map(model => (
                            <div key={model.key} className="glass-panel rounded-xl p-4">
                              <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-3 mb-2">
                                    <h3 className="font-bold text-white truncate">{model.description}</h3>
                                    {model.enabled ? (
                                      <span className="px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-xs font-bold">ENABLED</span>
                                    ) : (
                                      <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs font-bold">DISABLED</span>
                                    )}
                                  </div>
                                  <p className="text-xs text-zinc-500 mb-2 font-mono truncate">{model.id}</p>
                                  <div className="flex items-center gap-4 text-xs text-zinc-400">
                                    <span className="flex items-center gap-1">
                                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                                      </svg>
                                      {model.vram_gb}GB VRAM
                                    </span>
                                    <span className="flex items-center gap-1">
                                      {'⭐'.repeat(model.quality_stars)}
                                    </span>
                                    <span className="flex items-center gap-1">
                                      {'⚡'.repeat(model.speed_stars)}
                                    </span>
                                    <span className="uppercase font-bold text-purple-400">{model.model_type}</span>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                  <button 
                                    onClick={() => handleToggleModel(model.key, model.enabled)}
                                    className={clsx(
                                      "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border",
                                      model.enabled 
                                        ? "bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/30"
                                        : "bg-emerald-500/20 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/30"
                                    )}
                                  >
                                    {model.enabled ? 'Disable' : 'Enable'}
                                  </button>
                                  <button 
                                    onClick={() => handleDeleteModel(model.key)}
                                    className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20"
                                    title="Delete model from disk"
                                  >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                  </button>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Info Box */}
              <div className="glass-panel rounded-2xl p-5 border border-blue-500/30">
                <div className="flex items-start gap-3">
                  <svg className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div>
                    <h3 className="text-white font-bold text-sm mb-1">Model Management Guide</h3>
                    <ul className="text-xs text-zinc-400 space-y-1">
                      <li>• Models are stored in <code className="text-iris-accent">models/huggingface/</code></li>
                      <li>• Click "Scan Models" to auto-discover new models</li>
                      <li>• Enable/disable models to control which appear in the frontend</li>
                      <li>• Delete models to free up disk space (cannot be undone!)</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="glass-panel rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-white">Server Logs</h2>
                <button onClick={loadLogs} className="btn-secondary px-4 py-2 rounded-lg text-sm">Refresh</button>
              </div>
              <div className="bg-black/50 rounded-xl p-4 font-mono text-xs max-h-[500px] overflow-y-auto custom-scrollbar">
                {logs.length === 0 ? (
                  <p className="text-zinc-500">No logs available</p>
                ) : (
                  logs.map((log, i) => (
                    <div key={i} className="py-1 border-b border-white/5 last:border-0">
                      <span className="text-zinc-500">{log.time}</span>
                      <span className={clsx("mx-2 px-1.5 py-0.5 rounded text-[10px] font-bold", log.level === 'ERROR' ? 'bg-red-500/20 text-red-400' : log.level === 'WARN' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400')}>{log.level}</span>
                      <span className="text-zinc-300">{log.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {activeTab === 'actions' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <ActionCard title="Clear CUDA Cache" description="Free up GPU memory" buttonText="Clear Cache" onClick={handleClearCache} color="blue" />
              <ActionCard title="Reload System Info" description="Refresh all system data" buttonText="Reload" onClick={() => { loadSystemInfo(); loadSettings(); }} color="purple" />
              <ActionCard title="Clear Settings Cache" description="Force reload settings" buttonText="Clear" onClick={() => { localStorage.removeItem('iris_settings'); loadSettings(); }} color="orange" />
              <ActionCard title="Refresh Logs" description="Get latest server logs" buttonText="Refresh" onClick={loadLogs} color="emerald" />
            </div>
          )}

          {activeTab === 'danger' && (
            <div className="space-y-4">
              <div className="glass-panel rounded-2xl p-6 border border-red-500/30">
                <h2 className="text-lg font-bold text-red-400 mb-4 flex items-center gap-2">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                  Danger Zone
                </h2>
                <p className="text-zinc-400 text-sm mb-6">These actions can affect server stability.</p>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-red-500/10 rounded-xl border border-red-500/20">
                    <div>
                      <h3 className="font-medium text-white">Restart Server</h3>
                      <p className="text-sm text-zinc-500">Restart the I.R.I.S. server</p>
                    </div>
                    <button onClick={handleRestartServer} className="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg text-sm font-medium hover:bg-red-500/30 border border-red-500/30">Restart</button>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-red-500/10 rounded-xl border border-red-500/20">
                    <div>
                      <h3 className="font-medium text-white">Force Clear All</h3>
                      <p className="text-sm text-zinc-500">Clear all caches and reload</p>
                    </div>
                    <button onClick={() => { handleClearCache(); loadSystemInfo(); loadSettings(); loadLogs(); }} className="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg text-sm font-medium hover:bg-red-500/30 border border-red-500/30">Clear All</button>
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

function StatCard({ title, value, color, icon }) {
  const colors = {
    green: 'from-emerald-500 to-green-600', purple: 'from-purple-500 to-violet-600',
    blue: 'from-blue-500 to-indigo-600', pink: 'from-pink-500 to-rose-600',
    emerald: 'from-emerald-500 to-teal-600', orange: 'from-orange-500 to-amber-600',
    indigo: 'from-indigo-500 to-blue-600', red: 'from-red-500 to-rose-600',
    violet: 'from-violet-500 to-purple-600', cyan: 'from-cyan-500 to-blue-600',
    yellow: 'from-yellow-500 to-amber-600',
  }
  
  const icons = {
    server: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" /></svg>,
    gpu: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>,
    memory: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>,
    chip: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>,
    model: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>,
    shield: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>,
    bot: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>,
    temp: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5" /></svg>,
    power: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
    cpu: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" /></svg>,
    ram: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" /></svg>,
    version: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" /></svg>,
    os: <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>,
  }
  
  return (
    <div className="glass-panel rounded-xl p-4">
      <div className={clsx("w-10 h-10 rounded-lg bg-gradient-to-br flex items-center justify-center mb-3", colors[color])}>
        {icons[icon] || icons.chip}
      </div>
      <h3 className="text-xs text-zinc-500 mb-1">{title}</h3>
      <p className="text-sm font-bold text-white truncate">{value}</p>
    </div>
  )
}

function ActionCard({ title, description, buttonText, onClick, color }) {
  const colors = {
    blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30 hover:bg-blue-500/30',
    purple: 'bg-purple-500/20 text-purple-400 border-purple-500/30 hover:bg-purple-500/30',
    orange: 'bg-orange-500/20 text-orange-400 border-orange-500/30 hover:bg-orange-500/30',
    emerald: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/30',
  }
  return (
    <div className="glass-panel rounded-xl p-5">
      <h3 className="font-bold text-white mb-2">{title}</h3>
      <p className="text-sm text-zinc-400 mb-4">{description}</p>
      <button onClick={onClick} className={clsx("px-4 py-2 rounded-lg text-sm font-medium transition-colors border", colors[color])}>{buttonText}</button>
    </div>
  )
}
