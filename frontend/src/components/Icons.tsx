import type { ReactNode } from 'react'

type IconProps = { name: 'home' | 'history' | 'chart' | 'settings' | 'bulb' | 'leaf' | 'clock' | 'activity' | 'refresh' | 'sun' | 'distance' | 'chevron' }

export function Icon({ name }: IconProps) {
  const paths: Record<IconProps['name'], ReactNode> = {
    home: <><path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M9 20v-6h6v6"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/></>,
    chart: <><path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.56V21h-4v-.08A1.7 1.7 0 0 0 9 19.37a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.63 15 1.7 1.7 0 0 0 3.08 14H3v-4h.08A1.7 1.7 0 0 0 4.63 9a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.63h.01A1.7 1.7 0 0 0 10 3.08V3h4v.08A1.7 1.7 0 0 0 15 4.63a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.37 9v.01A1.7 1.7 0 0 0 20.92 10H21v4h-.08A1.7 1.7 0 0 0 19.4 15Z"/></>,
    bulb: <><path d="M9 18h6"/><path d="M10 22h4"/><path d="M8.2 14.6A7 7 0 1 1 15.8 14.6C15.1 15.2 15 16 15 17H9c0-1-.1-1.8-.8-2.4Z"/></>,
    leaf: <><path d="M20 4S8 3 5 11c-2 5 2 8 6 6 5-2 6-8 9-13Z"/><path d="M4 20c3-6 7-8 12-11"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    activity: <><path d="M3 12h4l2-7 4 14 2-7h6"/></>,
    refresh: <><path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M18.5 9A7 7 0 0 0 6 6.5L4 11"/><path d="M5.5 15A7 7 0 0 0 18 17.5l2-4.5"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41"/></>,
    distance: <><path d="M4 12h16"/><path d="m7 9-3 3 3 3M17 9l3 3-3 3"/></>,
    chevron: <path d="m9 18 6-6-6-6"/>,
  }
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}
