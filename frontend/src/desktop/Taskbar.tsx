import { useEffect, useState, type ReactNode } from 'react'
import type { ModuleInfo } from '../api'
import { GridIcon, PowerIcon, ReactorLogo } from '../components/icons'
import { iconOf } from '../components/moduleIcons'
import type { ManagedWindow } from './useWindowManager'

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 15_000)
    return () => window.clearInterval(timer)
  }, [])
  return (
    <time className="taskbar-clock" dateTime={now.toISOString()}>
      <span>{now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</span>
      <span>{now.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })}</span>
    </time>
  )
}

interface TaskbarProps {
  modules: ModuleInfo[]
  windows: ManagedWindow[]
  onWindowClick: (id: string) => void
  onArrange: () => void
  onLogout: () => void
  extra?: ReactNode // e.g. the theme toggle
}

export default function Taskbar({ modules, windows, onWindowClick, onArrange, onLogout, extra }: TaskbarProps) {
  return (
    <nav className="taskbar" aria-label="Barre des tâches">
      <div className="taskbar-brand">
        <ReactorLogo size={26} />
        <span>JARVIS</span>
      </div>

      <ul className="taskbar-windows">
        {windows.map((win) => {
          const title = modules.find((m) => m.id === win.id)?.title ?? win.id
          const ModuleIcon = iconOf(win.id)
          const state = win.state.minimized ? 'réduite' : win.active ? 'au premier plan' : 'ouverte'
          return (
            <li key={win.id}>
              <button
                type="button"
                className={`taskbar-window${win.active ? ' is-active' : ''}${win.state.minimized ? ' is-minimized' : ''}`}
                aria-pressed={win.active}
                title={`${title} (${state})`}
                onClick={() => onWindowClick(win.id)}
              >
                <ModuleIcon />
                <span className="taskbar-label">{title}</span>
              </button>
            </li>
          )
        })}
      </ul>

      <div className="taskbar-tray">
        <button type="button" className="taskbar-icon" onClick={onArrange} title="Organiser les fenêtres" aria-label="Organiser les fenêtres">
          <GridIcon />
        </button>
        {extra}
        <Clock />
        <button type="button" className="taskbar-icon" onClick={onLogout} title="Déconnexion" aria-label="Déconnexion">
          <PowerIcon />
        </button>
      </div>
    </nav>
  )
}
