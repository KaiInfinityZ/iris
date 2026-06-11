# I.R.I.S. React Frontend

Ein modernes React-Frontend für I.R.I.S. (Intelligent Rendering & Image Synthesis), das 1:1 dem HTML-Frontend entspricht.

## Tech Stack

- **React 18** mit TypeScript
- **Vite** als Build-Tool
- **Tailwind CSS** für Styling
- **Zustand** für State Management
- **React Router** für Navigation

## Installation

```bash
cd frontend
npm install
```

## Development

```bash
npm run dev
```

Das Frontend läuft auf `http://localhost:3000` und proxied API-Requests automatisch zum Backend auf Port 8000.

## Build

```bash
npm run build
```

Die Build-Dateien werden in `dist/` erstellt.

## Struktur

```
frontend/
├── src/
│   ├── components/     # Wiederverwendbare Komponenten
│   │   ├── Navbar.tsx
│   │   └── Footer.tsx
│   ├── pages/          # Seiten-Komponenten
│   │   ├── HomePage.tsx
│   │   ├── GeneratePage.tsx
│   │   ├── GalleryPage.tsx
│   │   └── SettingsPage.tsx
│   ├── store/          # Zustand State Management
│   │   └── useStore.ts
│   ├── lib/            # API und Utilities
│   │   └── api.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css       # Tailwind + Custom Styles
├── package.json
├── tailwind.config.js
├── vite.config.ts
└── tsconfig.json
```

## Features

- **Home Page**: Landing Page mit Stats und Feature-Übersicht
- **Generate Page**: Vollständiger Image Generator mit allen Einstellungen
- **Gallery Page**: Bildergalerie mit Filter und Suche
- **Settings Page**: System-Einstellungen und Hardware-Monitoring

## API Proxy

Der Vite Dev Server proxied automatisch:
- `/api/*` → `http://localhost:8000/api/*`
- `/ws/*` → `ws://localhost:8000/ws/*`
- `/assets/*` → `http://localhost:8000/assets/*`
