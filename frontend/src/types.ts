export type LedState = 'on' | 'off'

export interface Evento {
  led: LedState
  distancia: number | null
  luminosidade: number | null
  timestamp: string
  origem?: 'sensor' | 'manual'
}

export interface Metrica {
  data: string
  total_eventos: number
  tempo_apagado_s: number
  percentual_economia: number
}
