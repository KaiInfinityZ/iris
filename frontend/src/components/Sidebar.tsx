import { Link, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'
import { ReactNode } from 'react'

interface SidebarProps {
  children?: ReactNode
  showControls?: boolean
}

export default function Sidebar({ children, showControls = false }: SidebarProps) {
  const location = useLocation()
  const currentPath = location.pathname

  return (
    <aside className="w-[320px] lg:w-[360px] flex flex-col bg-iris-panel border-r border-iris-border flex-shrink-0 z-20">
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
            <span className="text-[9px] font-mono text-purple-400/80 tracking-widest">AI STUDIO</span>
          </div>
        </Link>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
          <span className="text-[10px] font-medium text-zinc-500">Ready</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="px-3 py-2 border-b border-iris-border">
        <div className="flex flex-wrap gap-1 p-1 bg-iris-bg/50 rounded-lg">
          <NavLink to="/" current={currentPath}>Home</NavLink>
          <NavLink to="/generate" current={currentPath}>Create</NavLink>
          <NavLink to="/gallery" current={currentPath}>Gallery</NavLink>
          <NavLink to="/upscaler" current={currentPath}>Upscale</NavLink>
        </div>
      </nav>

      {/* Dashboard - Full width button below */}
      <div className="px-3 py-2">
        <Link 
          to="/dashboard" 
          className={clsx(
            "flex items-center justify-center gap-2 w-full py-2 px-3 rounded-lg text-sm font-medium transition-all",
            currentPath === '/dashboard'
              ? "bg-iris-accent/20 text-iris-accentLight border border-iris-accent/30"
              : "bg-iris-card border border-iris-border text-zinc-400 hover:text-white hover:border-white/20"
          )}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
          </svg>
          Dashboard
        </Link>
      </div>

      {/* Content */}
      {children}

      {/* Footer */}
      <div className="px-4 py-3 border-t border-iris-border mt-auto">
        <div className="flex items-center justify-between text-[10px] mb-2">
          <span className="text-zinc-600">I.R.I.S. v1.2.0</span>
          <span className="text-zinc-600">© 2026 KaiTooast</span>
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <a href="https://github.com/KaiTooast/iris" target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-white transition-colors">GitHub</a>
          <span className="text-zinc-700">•</span>
          <a href="https://github.com/KaiTooast/iris/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-white transition-colors">License (CC BY 4.0)</a>
          <span className="text-zinc-700">•</span>
          <a href="https://github.com/KaiTooast/iris#readme" target="_blank" rel="noopener noreferrer" className="text-zinc-500 hover:text-white transition-colors">Docs</a>
        </div>
      </div>
    </aside>
  )
}

interface NavLinkProps {
  to: string
  current: string
  children: ReactNode
}

function NavLink({ to, current, children }: NavLinkProps) {
  const isActive = current === to || (to === '/generate' && current === '/generate')
  
  return isActive ? (
    <span className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md bg-iris-accent/20 text-iris-accentLight border border-iris-accent/30">
      {children}
    </span>
  ) : (
    <Link to={to} className="flex-1 px-3 py-1.5 text-center text-[11px] font-medium rounded-md text-zinc-400 hover:text-white hover:bg-white/5 transition-all">
      {children}
    </Link>
  )
}
