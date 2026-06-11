import { Link, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'

interface NavbarProps {
  variant?: 'default' | 'transparent'
}

export default function Navbar({ variant = 'default' }: NavbarProps) {
  const location = useLocation()
  
  const links = [
    { to: '/gallery', label: 'Gallery' },
    { to: '/dashboard', label: 'Dashboard' },
    { to: 'https://github.com/KaiTooast/iris', label: 'GitHub', external: true },
  ]

  return (
    <nav className={clsx(
      'container mx-auto px-6 py-5 flex justify-between items-center relative z-20',
      variant === 'transparent' && 'border-b border-iris-border bg-iris-bg/80 backdrop-blur-sm sticky top-0'
    )}>
      <Link to="/" className="flex items-center gap-3 group">
        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-violet-500 via-purple-500 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-purple-500/25 group-hover:shadow-purple-500/40 transition-shadow">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
          </svg>
        </div>
        <span className="text-xl font-bold tracking-tight text-white">I.R.I.S.</span>
      </Link>
      
      <div className="flex gap-6">
        {links.map((link) => (
          link.external ? (
            <a
              key={link.to}
              href={link.to}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-zinc-400 hover:text-white transition-colors py-2"
            >
              {link.label}
            </a>
          ) : (
            <Link
              key={link.to}
              to={link.to}
              className={clsx(
                'text-sm font-medium transition-colors py-2',
                location.pathname === link.to
                  ? 'text-white border-b-2 border-iris-accent'
                  : 'text-zinc-400 hover:text-white'
              )}
            >
              {link.label}
            </Link>
          )
        ))}
      </div>
    </nav>
  )
}
