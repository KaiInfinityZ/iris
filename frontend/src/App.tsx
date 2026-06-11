import { Routes, Route, Navigate } from 'react-router-dom'
import HomePage from './pages/HomePage'
import GeneratePage from './pages/GeneratePage'
import GalleryPage from './pages/GalleryPage'
import SettingsPage from './pages/SettingsPage'
import AdminPage from './pages/AdminPage'
import UpscalerPage from './pages/UpscalerPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/generate" element={<GeneratePage />} />
      <Route path="/gallery" element={<GalleryPage />} />
      <Route path="/upscaler" element={<UpscalerPage />} />
      <Route path="/dashboard" element={<SettingsPage />} />
      <Route path="/settings" element={<Navigate to="/dashboard" replace />} />
      <Route path="/admin" element={<AdminPage />} />
    </Routes>
  )
}

export default App
