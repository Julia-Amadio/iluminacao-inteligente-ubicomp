import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Evento, Metrica } from '../types'

export function useDashboard() {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [metricas, setMetricas] = useState<Metrica[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [eventsResult, metricsResult] = await Promise.allSettled([api.eventos(), api.metricas()])
      if (eventsResult.status === 'fulfilled') setEventos(eventsResult.value)
      if (metricsResult.status === 'fulfilled') setMetricas(metricsResult.value)
      if (eventsResult.status === 'rejected' && metricsResult.status === 'rejected') {
        throw new Error('Não foi possível conectar à API')
      }
      setError(null)
      setUpdatedAt(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro inesperado')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => void refresh(), 30_000)
    return () => window.clearInterval(id)
  }, [refresh])

  return { eventos, metricas, loading, error, updatedAt, refresh }
}
