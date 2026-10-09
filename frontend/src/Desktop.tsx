import { useEffect, useState } from 'react'
import { api, UnauthorizedError, type ModuleInfo } from './api'
import Window from './components/Window'
import { windowComponents } from './windows'

export default function Desktop({ onLoggedOut }: { onLoggedOut: () => void }) {
  const [modules, setModules] = useState<ModuleInfo[]>([])
  const [error, setError] = useState<string | null>(null)
  // Window ids from back to front: the last one is drawn on top.
  const [stack, setStack] = useState<string[]>([])

  useEffect(() => {
    api
      .modules()
      .then((list) => {
        setModules(list)
        setStack(list.map((m) => m.id))
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError) onLoggedOut()
        else setError('Impossible de charger les modules.')
      })
  }, [onLoggedOut])

  async function logout() {
    try {
      await api.logout()
    } finally {
      onLoggedOut()
    }
  }

  const bringToFront = (id: string) =>
    setStack((current) => [...current.filter((x) => x !== id), id])

  return (
    <div className="desktop">
      <header className="taskbar">
        <span>Jarvis</span>
        <button type="button" onClick={logout}>
          Déconnexion
        </button>
      </header>
      <main className="workspace">
        {error && <p className="error">{error}</p>}
        {modules.map((module, index) => {
          const Content = windowComponents[module.id]
          return (
            <Window
              key={module.id}
              id={module.id}
              title={module.title}
              defaultLayout={{
                x: 24 + (index % 2) * 440,
                y: 24 + Math.floor(index / 2) * 300,
                width: 420,
                height: 280,
              }}
              zIndex={stack.indexOf(module.id) + 1}
              onFocus={() => bringToFront(module.id)}
            >
              {Content ? <Content /> : <p className="placeholder">Fenêtre non définie.</p>}
            </Window>
          )
        })}
      </main>
    </div>
  )
}
