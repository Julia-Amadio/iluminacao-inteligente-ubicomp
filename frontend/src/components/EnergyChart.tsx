import type { Metrica } from '../types'

export function EnergyChart({ data }: { data: Metrica[] }) {
  const points = [...data].reverse().slice(-7)
  if (!points.length) return <div className="empty-state chart-empty">Ainda não há dias agregados para exibir.</div>

  const values = points.map((item) => Math.max(0, Math.min(100, item.percentual_economia)))
  const labels = points.map((item) => new Intl.DateTimeFormat('pt-BR', { weekday: 'short', timeZone: 'UTC' }).format(new Date(item.data)).replace('.', ''))
  const width = 620, height = 190, left = 18, top = 16, usableW = width - left * 2, usableH = 130
  const coords = values.map((value, i) => ({ x: left + (usableW * i) / Math.max(values.length - 1, 1), y: top + usableH * (1 - value / 100) }))
  const line = coords.map((point, i) => `${i ? 'L' : 'M'}${point.x},${point.y}`).join(' ')
  const area = `${line} L${coords.at(-1)?.x},${top + usableH} L${coords[0].x},${top + usableH} Z`

  return <div className="chart-wrap">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Economia de energia nos últimos sete dias">
      <defs><linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#edb83d" stopOpacity=".3"/><stop offset="1" stopColor="#edb83d" stopOpacity="0"/></linearGradient></defs>
      {[0, 1, 2].map((n) => <line key={n} x1={left} x2={width-left} y1={top+n*65} y2={top+n*65} className="grid-line" />)}
      <path d={area} fill="url(#chartFill)"/><path d={line} className="chart-line"/>
      {coords.map((point, i) => <g key={i}><circle cx={point.x} cy={point.y} r="4" className="chart-point"/><text x={point.x} y="178" textAnchor="middle" className="chart-label">{labels[i]}</text></g>)}
    </svg>
  </div>
}
