import type { Evento, Metrica } from './types'

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal: AbortSignal.timeout(8000) })
  if (!response.ok) throw new Error(`A API respondeu com status ${response.status}`)
  return response.json() as Promise<T>
}

export const api = {
  eventos: () => get<Evento[]>('/eventos?limite=50'),
  metricas: () => get<Metrica[]>('/metricas?limite=30'),
}
