import { Link } from 'react-router-dom'

export default function HomePage() {
  return (
    <div className="min-h-screen bg-iris-bg flex flex-col">
      {/* Navigation */}
      <nav className="h-16 border-b border-iris-border bg-iris-panel/80 backdrop-blur-xl shrink-0 relative z-10">
        <div className="max-w-6xl mx-auto px-6 h-full flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-500 via-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/30">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
            </div>
            <span className="text-white font-bold text-lg">I.R.I.S.</span>
          </Link>
          
          <div className="flex items-center gap-1">
            <Link to="/generate" className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">Generate</Link>
            <Link to="/gallery" className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">Gallery</Link>
            <Link to="/dashboard" className="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">Dashboard</Link>
            <Link to="/generate" className="ml-3 px-5 py-2 bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-500 hover:to-violet-500 text-white text-sm font-semibold rounded-lg transition-all shadow-lg shadow-purple-500/25">
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <main className="flex-1 flex flex-col">
        {/* Hero Section */}
        <section className="flex-1 flex items-center justify-center px-6 py-16 relative overflow-hidden">
          {/* Background Effects */}
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-violet-600/10 rounded-full blur-3xl" />
          </div>

          <div className="max-w-4xl text-center relative z-10">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-purple-500/10 to-violet-500/10 border border-purple-500/20 text-sm mb-8">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-lg shadow-emerald-500/50" />
              <span className="text-purple-300 font-medium">v1.2.0</span>
              <span className="text-zinc-500">—</span>
              <span className="text-zinc-400">100% Local & Open Source</span>
            </div>

            <h1 className="text-5xl md:text-7xl font-bold text-white mb-6 tracking-tight leading-[1.1]">
              AI Image Generation,<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 via-pink-400 to-violet-400 animate-gradient">
                On Your Terms
              </span>
            </h1>

            <p className="text-xl text-zinc-400 mb-12 max-w-2xl mx-auto leading-relaxed">
              Powerful, open-source image synthesis that runs entirely on your hardware. 
              No cloud, no subscriptions, no limits.
            </p>

            <div className="flex gap-4 justify-center">
              <Link to="/generate" className="group px-8 py-4 bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-500 hover:to-violet-500 text-white text-lg font-semibold rounded-xl transition-all shadow-xl shadow-purple-500/30 flex items-center gap-2">
                Start Creating
                <svg className="w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Link>
              <a href="https://github.com/KaiTooast/iris" target="_blank" rel="noopener noreferrer" className="px-8 py-4 bg-iris-card hover:bg-iris-card/80 border border-iris-border text-white text-lg font-medium rounded-xl transition-all flex items-center gap-2">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                </svg>
                GitHub
              </a>
            </div>
          </div>
        </section>

        {/* Stats Bar */}
        <section className="py-6 border-t border-b border-iris-border bg-iris-panel/50">
          <div className="max-w-4xl mx-auto px-6">
            <div className="grid grid-cols-3 gap-8">
              <div className="text-center">
                <div className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-violet-400 mb-1">12+</div>
                <div className="text-xs text-zinc-500 uppercase tracking-wide font-medium">AI Models</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-pink-400 to-rose-400 mb-1">4x</div>
                <div className="text-xs text-zinc-500 uppercase tracking-wide font-medium">Upscaling</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-blue-400 mb-1">∞</div>
                <div className="text-xs text-zinc-500 uppercase tracking-wide font-medium">Variations</div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="py-6 border-t border-iris-border bg-iris-panel/50">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-6 h-6 rounded-md bg-gradient-to-br from-purple-500 to-violet-600 flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
              </div>
              <span className="text-zinc-500 text-sm">I.R.I.S. v1.2.0</span>
              <span className="text-zinc-700">•</span>
              <span className="text-zinc-500 text-sm">© 2026 KaiTooast</span>
            </div>
            <div className="flex items-center gap-6 text-sm">
              <a href="https://github.com/KaiTooast/iris" target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-white transition-colors">GitHub</a>
              <a href="https://github.com/KaiTooast/iris/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-white transition-colors">License</a>
              <a href="https://github.com/KaiTooast/iris#readme" target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-white transition-colors">Documentation</a>
              <Link to="/dashboard" className="text-zinc-500 hover:text-white transition-colors">Dashboard</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
