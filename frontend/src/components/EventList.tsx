import { Icon } from './Icons'
import type { Evento } from '../types'

const date = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

export function EventList({ eventos }: { eventos: Evento[] }) {
  const list = eventos.slice(0, 5)
  if (!list.length) return <div className="empty-state">Nenhum evento recebido ainda.</div>
  return <div className="event-list">
    {list.map((event, index) => <div className="event-row" key={`${event.timestamp}-${index}`}>
      <div className={`event-icon ${event.led}`}><Icon name="bulb" /></div>
      <div className="event-copy"><strong>Luz {event.led === 'on' ? 'acesa' : 'apagada'}</strong><span>{event.origem === 'manual' ? 'Controle manual' : 'Automação por sensores'}</span></div>
      <div className="sensor-data">
        <span><Icon name="distance" /> {event.distancia == null ? '—' : `${event.distancia.toFixed(1)} cm`}</span>
        <span><Icon name="sun" /> {event.luminosidade == null ? '—' : event.luminosidade}</span>
      </div>
      <time>{date.format(new Date(event.timestamp))}</time>
    </div>)}
  </div>
}
