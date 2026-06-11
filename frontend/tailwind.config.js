/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        iris: {
          bg: '#0a0a0f',
          panel: '#12121a',
          card: '#1a1a24',
          elevated: '#22222e',
          border: 'rgba(255, 255, 255, 0.08)',
          accent: '#8b5cf6',
          accentLight: '#a78bfa',
          text: '#f4f4f5',
          muted: '#71717a',
        }
      },
      animation: {
        'pulse-glow': 'pulse-glow 10s ease-in-out infinite',
        'gradient': 'gradient 4s ease infinite',
        'shimmer': 'shimmer 1.5s infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { opacity: '0.4', transform: 'translate(-50%, -50%) scale(1)' },
          '50%': { opacity: '0.7', transform: 'translate(-50%, -50%) scale(1.15)' },
        },
        'gradient': {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        'shimmer': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
      },
    },
  },
  plugins: [],
}
