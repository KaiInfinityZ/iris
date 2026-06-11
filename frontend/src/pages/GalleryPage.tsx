import { useEffect, useState } from 'react'
import { clsx } from 'clsx'
import Sidebar from '../components/Sidebar'
import { getOutputGallery, getImageUrl } from '../lib/api'

export default function GalleryPage() {
  const [images, setImages] = useState([])
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [selectedImage, setSelectedImage] = useState(null)

  useEffect(() => {
    loadGallery()
  }, [])

  async function loadGallery() {
    try {
      const data = await getOutputGallery()
      setImages(data.images || [])
    } catch (e) {
      console.error('Failed to load gallery:', e)
    }
  }

  function getImageType(filename) {
    if (filename.startsWith('gen_') || filename.startsWith('generated_')) return 'generated'
    if (filename.startsWith('var_') || filename.startsWith('variation_')) return 'variation'
    if (filename.startsWith('up') || filename.startsWith('upscaled')) return 'upscaled'
    return 'generated'
  }

  const filteredImages = images.filter(img => {
    const matchesFilter = filter === 'all' || getImageType(img) === filter
    const matchesSearch = img.toLowerCase().includes(search.toLowerCase())
    return matchesFilter && matchesSearch
  })

  const stats = {
    total: images.length,
    generated: images.filter(f => getImageType(f) === 'generated').length,
    upscaled: images.filter(f => getImageType(f) === 'upscaled').length,
    variations: images.filter(f => getImageType(f) === 'variation').length,
  }

  function handleDownload() {
    if (!selectedImage) return
    const link = document.createElement('a')
    link.href = getImageUrl(selectedImage)
    link.download = selectedImage
    link.click()
  }

  return (
    <div className="flex h-screen w-full overflow-hidden text-sm">
      <Sidebar>
        {/* Sidebar Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          <div className="p-4 space-y-5">
            {/* Search */}
            <div className="space-y-2">
              <label className="sidebar-label">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                Search
              </label>
              <div className="relative">
                <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} className="w-full bg-iris-card border border-iris-border rounded-xl pl-10 pr-4 py-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-iris-accent" placeholder="Search filenames..." />
                <svg className="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
              </div>
            </div>

            <div className="h-px bg-gradient-to-r from-transparent via-iris-border to-transparent" />

            {/* Filters */}
            <div className="space-y-2">
              <label className="sidebar-label">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" /></svg>
                Filter
              </label>
              <div className="grid grid-cols-2 gap-2">
                {['all', 'generated', 'upscaled', 'variation'].map(f => (
                  <button key={f} onClick={() => setFilter(f)} className={clsx("px-3 py-2 rounded-lg text-xs font-medium transition-all", filter === f ? "bg-iris-accent/20 text-iris-accentLight border border-iris-accent/30" : "bg-iris-card border border-iris-border text-zinc-400 hover:text-white hover:border-white/20")}>
                    {f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div className="h-px bg-gradient-to-r from-transparent via-iris-border to-transparent" />

            {/* Stats */}
            <div className="space-y-2">
              <label className="sidebar-label">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                Statistics
              </label>
              <div className="space-y-2">
                <StatItem label="Total" value={stats.total} color="white" />
                <StatItem label="Generated" value={stats.generated} color="purple" />
                <StatItem label="Upscaled" value={stats.upscaled} color="indigo" />
                <StatItem label="Variations" value={stats.variations} color="pink" />
              </div>
            </div>
          </div>
        </div>

        {/* Refresh Button */}
        <div className="p-4 border-t border-iris-border bg-iris-panel">
          <button onClick={loadGallery} className="btn-secondary w-full py-3 rounded-xl font-medium text-sm flex items-center justify-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            Refresh Gallery
          </button>
        </div>
      </Sidebar>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-iris-bg">
        {/* Top Bar */}
        <header className="h-12 border-b border-iris-border bg-iris-panel/80 backdrop-blur-sm flex items-center justify-between px-5 shrink-0 z-10">
          <div className="flex items-center gap-3">
            <span className="text-xs text-zinc-500 font-mono">{filteredImages.length} images</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-400">Filter: <span className="text-iris-accentLight">{filter}</span></span>
          </div>
        </header>

        {/* Gallery Grid */}
        <div className="flex-1 overflow-y-auto p-6">
          {filteredImages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-20 h-20 rounded-2xl liquid-glass-subtle flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-zinc-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
              </div>
              <h3 className="text-lg font-medium text-zinc-400 mb-2">No Images Found</h3>
              <p className="text-sm text-zinc-600">Try adjusting your filters or generate some images</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4">
              {filteredImages.map((filename) => {
                const type = getImageType(filename)
                const badgeClass = type === 'generated' ? 'bg-purple-500' : type === 'upscaled' ? 'bg-indigo-500' : 'bg-pink-500'
                const typeLabel = type === 'generated' ? 'GEN' : type === 'upscaled' ? 'UP' : 'VAR'
                
                return (
                  <div key={filename} onClick={() => setSelectedImage(filename)} className="group relative aspect-square rounded-xl overflow-hidden cursor-pointer border border-iris-border hover:border-iris-accent/50 transition-all hover:scale-[1.02]">
                    <img src={getImageUrl(filename)} className="w-full h-full object-cover" alt={filename} loading="lazy" />
                    <div className="absolute top-2 right-2">
                      <span className={clsx("text-[10px] font-bold text-white px-2 py-1 rounded shadow-md", badgeClass)}>{typeLabel}</span>
                    </div>
                    <div className="absolute inset-0 flex flex-col justify-end p-3 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                      <p className="text-white text-[10px] font-mono truncate">{filename}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </main>

      {/* Modal */}
      {selectedImage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/95 backdrop-blur-xl" onClick={() => setSelectedImage(null)}>
          <div className="relative max-w-5xl w-full h-[85vh] flex flex-col md:flex-row gap-4" onClick={(e) => e.stopPropagation()}>
            <button onClick={() => setSelectedImage(null)} className="absolute -top-10 right-0 text-white/50 hover:text-white transition z-10">
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            </button>

            <div className="flex-1 bg-black/50 rounded-2xl flex items-center justify-center p-4 border border-white/10">
              <img src={getImageUrl(selectedImage)} className="max-w-full max-h-full object-contain shadow-2xl rounded-lg" alt="" />
            </div>

            <div className="w-full md:w-72 glass-panel p-5 flex flex-col shrink-0 rounded-2xl">
              <h3 className="text-base font-bold text-white mb-4 pb-3 border-b border-white/10">Image Details</h3>
              
              <div className="space-y-3 flex-1">
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 text-xs">Type</span>
                  <span className="text-purple-400 font-bold text-xs uppercase px-2 py-0.5 rounded bg-purple-900/30 border border-purple-500/30">
                    {getImageType(selectedImage)}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500 text-xs block mb-1">Filename</span>
                  <span className="text-zinc-400 font-mono text-[10px] break-all bg-black/30 p-2 rounded block border border-white/5">{selectedImage}</span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-white/10 flex flex-col gap-2">
                <button onClick={handleDownload} className="btn-primary w-full py-2.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 text-white">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                  Download
                </button>
                <button onClick={() => setSelectedImage(null)} className="btn-secondary w-full py-2.5 rounded-xl font-medium text-sm">Close</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function StatItem({ label, value, color }) {
  const colorClass = color === 'purple' ? 'text-purple-400' : color === 'indigo' ? 'text-indigo-400' : color === 'pink' ? 'text-pink-400' : 'text-white'
  return (
    <div className="flex justify-between items-center p-2.5 bg-iris-card rounded-lg border border-iris-border">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className={clsx("text-sm font-bold font-mono", colorClass)}>{value}</span>
    </div>
  )
}
