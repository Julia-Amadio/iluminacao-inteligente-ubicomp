import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Estado, Evento, Metrica } from '../types'

export function useDashboard() {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [eventosHoje, setEventosHoje] = useState<Evento[]>([])
  const [metricas, setMetricas] = useState<Metrica[]>([])
  const [estado, setEstado] = useState<Estado | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [eventsResult, todayResult, metricsResult, stateResult] = await Promise.allSettled([
        api.eventos(), api.eventosHoje(), api.metricas(), api.estado(),
      ])
      if (eventsResult.status === 'fulfilled') setEventos(eventsResult.value)
      if (todayResult.status === 'fulfilled') setEventosHoje(todayResult.value)
      if (metricsResult.status === 'fulfilled') setMetricas(metricsResult.value)
      if (stateResult.status === 'fulfilled') setEstado(stateResult.value)
      const results = [eventsResult, todayResult, metricsResult, stateResult]
      if (results.every((result) => result.status === 'rejected')) {
        throw new Error('Não foi possível conectar à API')
      }
      setError(results.some((result) => result.status === 'rejected')
        ? 'Parte dos dados não pôde ser atualizada. Exibindo os últimos valores disponíveis.'
        : null)
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

  return { eventos, eventosHoje, metricas, estado, loading, error, updatedAt, refresh }
}
