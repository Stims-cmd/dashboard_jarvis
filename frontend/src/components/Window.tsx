import type { ReactNode } from 'react'
import { Rnd } from 'react-rnd'
import { MIN_HEIGHT, MIN_WIDTH, type Rect } from '../desktop/layout'
import type { ManagedWindow } from '../desktop/useWindowManager'
import { MaximizeIcon, MinimizeIcon, RestoreIcon } from './icons'

interface WindowProps {
  title: string
  icon?: ReactNode
  window: ManagedWindow
  onFocus: () => void
  onMove: (rect: Rect) => void
  onMinimize: () => void
  onToggleMaximize: () => void
  children: ReactNode
}

// Controlled window: its position, size and state come from the window manager (Desktop).
export default function Window({
  title,
  icon,
  window: win,
  onFocus,
  onMove,
  onMinimize,
  onToggleMaximize,
  children,
}: WindowProps) {
  const { minimized, maximized } = win.state
  const classes = ['window', win.active && 'window-active', minimized && 'window-minimized', maximized && 'window-maximized']

  return (
    <Rnd
      className={classes.filter(Boolean).join(' ')}
      position={{ x: win.rect.x, y: win.rect.y }}
      size={{ width: win.rect.width, height: win.rect.height }}
      minWidth={MIN_WIDTH}
      minHeight={MIN_HEIGHT}
      bounds="parent"
      dragHandleClassName="window-title"
      cancel=".window-controls"
      disableDragging={maximized}
      enableResizing={!maximized && !minimized}
      style={{ zIndex: win.zIndex }}
      onMouseDown={onFocus}
      onDragStop={(_e, d) => onMove({ ...win.rect, x: d.x, y: d.y })}
      onResizeStop={(_e, _dir, ref, _delta, position) =>
        onMove({ width: ref.offsetWidth, height: ref.offsetHeight, ...position })
      }
    >
      <section className="window-frame" aria-label={title} inert={minimized}>
        <header className="window-title" onDoubleClick={onToggleMaximize}>
          {icon && <span className="window-icon">{icon}</span>}
          <h2>{title}</h2>
          <div className="window-controls">
            <button type="button" aria-label="Réduire" title="Réduire" onClick={onMinimize}>
              <MinimizeIcon />
            </button>
            <button
              type="button"
              aria-label={maximized ? 'Restaurer' : 'Agrandir'}
              title={maximized ? 'Restaurer' : 'Agrandir'}
              onClick={onToggleMaximize}
            >
              {maximized ? <RestoreIcon /> : <MaximizeIcon />}
            </button>
          </div>
        </header>
        <div className="window-body">{children}</div>
      </section>
    </Rnd>
  )
}
