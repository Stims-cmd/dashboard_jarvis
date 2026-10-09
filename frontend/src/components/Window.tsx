import type { ReactNode } from 'react'
import { Rnd } from 'react-rnd'

export interface WindowLayout {
  x: number
  y: number
  width: number
  height: number
}

interface WindowProps {
  id: string
  title: string
  defaultLayout: WindowLayout
  zIndex: number
  onFocus: () => void
  children: ReactNode
}

// Window positions are a per-browser convenience: storage may be unavailable, so never fail on it.
function loadLayout(id: string, fallback: WindowLayout): WindowLayout {
  try {
    const saved = localStorage.getItem(`jarvis.window.${id}`)
    return saved ? { ...fallback, ...(JSON.parse(saved) as WindowLayout) } : fallback
  } catch {
    return fallback
  }
}

function saveLayout(id: string, layout: WindowLayout) {
  try {
    localStorage.setItem(`jarvis.window.${id}`, JSON.stringify(layout))
  } catch {
    // ignore
  }
}

export default function Window({ id, title, defaultLayout, zIndex, onFocus, children }: WindowProps) {
  const initial = loadLayout(id, defaultLayout)

  return (
    <Rnd
      className="window"
      default={initial}
      minWidth={240}
      minHeight={140}
      bounds="parent"
      dragHandleClassName="window-title"
      style={{ zIndex }}
      onMouseDown={onFocus}
      onDragStop={(_e, d) => saveLayout(id, { ...loadLayout(id, initial), x: d.x, y: d.y })}
      onResizeStop={(_e, _dir, ref, _delta, position) =>
        saveLayout(id, { width: ref.offsetWidth, height: ref.offsetHeight, ...position })
      }
    >
      <div className="window-title">{title}</div>
      <div className="window-body">{children}</div>
    </Rnd>
  )
}
