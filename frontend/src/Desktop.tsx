import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { api, UnauthorizedError, type ModuleInfo } from './api'
import { iconOf } from './components/moduleIcons'
import Window from './components/Window'
import type { Size } from './desktop/layout'
import Taskbar from './desktop/Taskbar'
import { useWindowManager } from './desktop/useWindowManager'
import { windowComponents } from './windows'

function useElementSize(ref: RefObject<HTMLElement | null>): Size {
  const [size, setSize] = useState<Size>({ width: 0, height: 0 })
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize({ width: Math.floor(width), height: Math.floor(height) })
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return size
}

// The desktop once the module list is known: windows and their manager.
function Session({ modules, onLogout }: { modules: ModuleInfo[]; onLogout: () => void }) {
  const workspace = useRef<HTMLElement>(null)
  const area = useElementSize(workspace)
  const ids = useMemo(() => modules.map((m) => m.id), [modules])
  const manager = useWindowManager(ids, area)

  return (
    <div className="desktop">
      <main className="workspace" ref={workspace}>
        {manager.ready &&
          manager.windows.map((win) => {
            const module = modules.find((m) => m.id === win.id)
            const Content = windowComponents[win.id]
            const ModuleIcon = iconOf(win.id)
            return (
              <Window
                key={win.id}
                title={module?.title ?? win.id}
                icon={<ModuleIcon />}
                window={win}
                onFocus={() => manager.focus(win.id)}
                onMove={(rect) => manager.move(win.id, rect)}
                onMinimize={() => manager.minimize(win.id)}
                onToggleMaximize={() => manager.toggleMaximize(win.id)}
              >
                {Content ? <Content /> : <p className="placeholder">Fenêtre non définie.</p>}
              </Window>
            )
          })}
      </main>
      <Taskbar
        modules={modules}
        windows={manager.windows}
        onWindowClick={manager.taskbarClick}
        onArrange={manager.arrange}
        onLogout={onLogout}
      />
    </div>
  )
}

export default function Desktop({ onLoggedOut }: { onLoggedOut: () => void }) {
  const [modules, setModules] = useState<ModuleInfo[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .modules()
      .then(setModules)
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

  if (error) return <p className="centered error">{error}</p>
  if (modules === null) return <p className="centered">Chargement…</p>
  return <Session modules={modules} onLogout={logout} />
}
