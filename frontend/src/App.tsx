import { useMemo, useState } from 'react'
import './styles.css'
import { EnergyChart } from './components/EnergyChart'
import { EventList } from './components/EventList'
import { Icon } from './components/Icons'
import { useDashboard } from './hooks/useDashboard'
import { useMqtt } from './hooks/useMqtt'
import type { LedState } from './types'

const duration = (seconds: number) => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${String(minutes).padStart(2, '0')}min`
}

export default function App() {
  const { eventos, metricas, loading, error, updatedAt, refresh } = useDashboard()
  const { connected, publish } = useMqtt()
  const [pending, setPending] = useState<LedState | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const currentState = eventos[0]?.led || 'off'
  const latestMetric = metricas[0]
  const todayEvents = useMemo(() => eventos.filter((event) => new Date(event.timestamp).toDateString() === new Date().toDateString()), [eventos])

  async function sendCommand(state: LedState) {
    setPending(state); setNotice(null)
    try { await publish(state); setNotice(`Comando para ${state === 'on' ? 'acender' : 'apagar'} enviado`) }
    catch (err) { setNotice(err instanceof Error ? err.message : 'Falha ao enviar comando') }
    finally { setPending(null) }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Icon name="bulb" /></span><div><strong>Lumen</strong><small>Smart lighting</small></div></div>
      <nav aria-label="Menu principal">
        <a className="active" href="#visao"><Icon name="home" /><span>Visão geral</span></a>
        <a href="#historico"><Icon name="history" /><span>Histórico</span></a>
        <a href="#eficiencia"><Icon name="chart" /><span>Eficiência</span></a>
        <a href="#controle"><Icon name="settings" /><span>Controle</span></a>
      </nav>
      <div className="sidebar-foot"><span className={`status-dot ${connected ? '' : 'offline'}`}/><div><strong>{connected ? 'Sistema online' : 'Broker offline'}</strong><small>ESP32 · Grupo 1</small></div></div>
    </aside>

    <main>
      <header id="visao">
        <div><p className="eyebrow">PAINEL DE CONTROLE</p><h1>Olá, bem-vindo.</h1><p>Acompanhe o ambiente e controle a iluminação em tempo real.</p></div>
        <button className="refresh" onClick={() => void refresh()} aria-label="Atualizar dados"><Icon name="refresh" /><span>{updatedAt ? `Atualizado ${updatedAt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}` : 'Atualizar'}</span></button>
      </header>

      {error && <div className="alert"><span>API indisponível. Exibindo os últimos dados carregados.</span><button onClick={() => void refresh()}>Tentar novamente</button></div>}

      <section className="hero-grid">
        <article className={`light-card ${currentState}`}>
          <div className="light-glow"><Icon name="bulb" /></div>
          <div className="light-info"><span>ESTADO DA LUZ</span><h2>{currentState === 'on' ? 'Acesa' : 'Apagada'}</h2><p>{currentState === 'on' ? 'Ambiente ocupado e com pouca luz.' : 'Economizando energia no momento.'}</p></div>
          <span className="mode-pill">● Modo automático</span>
        </article>

        <article className="control-card" id="controle">
          <div className="card-heading"><div><span>CONTROLE MANUAL</span><h2>Intervir na iluminação</h2></div><span className={`connection ${connected ? '' : 'offline'}`}>{connected ? 'MQTT conectado' : 'MQTT desconectado'}</span></div>
          <p>O comando manual sobrepõe temporariamente a decisão dos sensores.</p>
          <div className="control-buttons">
            <button disabled={!connected || pending !== null} className="turn-on" onClick={() => void sendCommand('on')}><Icon name="bulb" />{pending === 'on' ? 'Enviando…' : 'Acender luz'}</button>
            <button disabled={!connected || pending !== null} onClick={() => void sendCommand('off')}>{pending === 'off' ? 'Enviando…' : 'Apagar luz'}</button>
          </div>
          {notice && <div className="notice">{notice}</div>}
        </article>
      </section>

      <section className="metric-grid" aria-label="Resumo do sistema">
        <article><span className="metric-icon green"><Icon name="leaf" /></span><div><span>ECONOMIA MÉDIA</span><strong>{latestMetric ? `${latestMetric.percentual_economia.toFixed(1)}%` : '—'}</strong><small>tempo com a luz apagada</small></div></article>
        <article><span className="metric-icon amber"><Icon name="clock" /></span><div><span>TEMPO ECONOMIZADO</span><strong>{latestMetric ? duration(latestMetric.tempo_apagado_s) : '—'}</strong><small>no último dia agregado</small></div></article>
        <article><span className="metric-icon blue"><Icon name="activity" /></span><div><span>EVENTOS HOJE</span><strong>{todayEvents.length}</strong><small>transições registradas</small></div></article>
      </section>

      <section className="content-grid">
        <article className="panel" id="eficiencia">
          <div className="panel-head"><div><span>DESEMPENHO</span><h2>Eficiência energética</h2></div><span className="range">Últimos 7 dias</span></div>
          <EnergyChart data={metricas} />
          <div className="chart-foot"><span><i /> Economia diária</span><strong>{latestMetric ? `${latestMetric.percentual_economia.toFixed(1)}%` : '—'} <small>último registro</small></strong></div>
        </article>
        <article className="panel context-panel">
          <div className="panel-head"><div><span>CONTEXTO ATUAL</span><h2>Leituras dos sensores</h2></div></div>
          <div className="context-value"><span className="metric-icon blue"><Icon name="distance" /></span><div><span>DISTÂNCIA</span><strong>{eventos[0]?.distancia == null ? '—' : `${eventos[0].distancia.toFixed(1)} cm`}</strong></div></div>
          <div className="context-value"><span className="metric-icon amber"><Icon name="sun" /></span><div><span>LUMINOSIDADE</span><strong>{eventos[0]?.luminosidade ?? '—'} <small>/ 4095</small></strong></div></div>
          <p>As leituras são atualizadas quando ocorre uma transição da iluminação, conforme a arquitetura orientada a eventos.</p>
        </article>
      </section>

      <section className="panel history-panel" id="historico">
        <div className="panel-head"><div><span>ATIVIDADE RECENTE</span><h2>Histórico de eventos</h2></div><button className="text-button" onClick={() => void refresh()}>Atualizar <Icon name="chevron" /></button></div>
        {loading ? <div className="empty-state">Carregando eventos…</div> : <EventList eventos={eventos} />}
      </section>
      <footer>Projeto de Computação Pervasiva e Ubíqua · 2026</footer>
    </main>
  </div>
}
