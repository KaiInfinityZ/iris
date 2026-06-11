// Common types used across the application

export interface UpscaleMethod {
  id: string
  name: string
  desc: string
  gpu: boolean
  max_scale: number
}

export interface UpscaledImage {
  url: string
  width: number
  height: number
  scale: number
  method: string
  blob: Blob
}

export interface UpscaleHistoryItem {
  id: number
  timestamp: string
  originalUrl: string
  upscaledUrl: string
  originalWidth: number
  originalHeight: number
  upscaledWidth: number
  upscaledHeight: number
  method: string
  scale: number
  processingTime: number
}

export interface MemoryEstimate {
  input_size_mb: number
  output_size_mb: number
  total_memory_mb: number
  gpu_required: boolean
}

export interface GpuData {
  gpu_name?: string
  vram_total?: number
  vram_used?: number
  vram_free?: number
  vram_percent?: number
  gpu_temp?: number
  gpu_utilization?: number
  power_draw?: number
  cpu_percent?: number
  cpu_freq?: number
  cpu_cores?: number
  ram_used?: number
  ram_total?: number
  ram_percent?: number
}

export interface GpuInfo {
  gpu: GpuData
}

export interface VersionInfo {
  os: string
  python_version: string
  pytorch_version: string
  cuda_version: string
}

export interface SystemInfo {
  pytorch_version: string
  cuda_version: string
  os: string
  gpu_name: string
}

export interface LogEntry {
  time: string
  level: 'ERROR' | 'WARN' | 'INFO'
  message: string
}

export interface PromptHistoryEntry {
  prompt: string
  negativePrompt: string
  timestamp: number
}

export interface UpscaleResult {
  image_url: string
  original_width: number
  original_height: number
  upscaled_width: number
  upscaled_height: number
  scale: number
  method: string
  processing_time: number
}
