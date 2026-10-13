import { useCallback, useEffect, useMemo, useState } from 'react'
import { clampRect, gridRects, parseSaved, toState, type Rect, type Size, type WindowState } from './layout'

const STORAGE_KEY = 'jarvis.desktop'
const LEGACY_PREFIX = 'jarvis.window.' // one key per window, before the window manager

// Window positions are a per-browser convenience: storage may be unavailable, so never fail on it.
function load(ids: string[]): Record<string, WindowState> {
  try {
    const saved = parseSaved(localStorage.getItem(STORAGE_KEY))
    for (const id of ids) {
      const legacy = localStorage.getItem(LEGACY_PREFIX + id)
      if (saved[id] || !legacy) continue
      const state = toState(JSON.parse(legacy))
      if (state) saved[id] = state
    }
    return saved
  } catch {
    return {}
  }
}

function save(windows: Record<string, WindowState>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(windows))
  } catch {
    // ignore
  }
}

export interface ManagedWindow {
  id: string
  state: WindowState
  rect: Rect // where it is drawn: the whole area when maximized, clamped otherwise
  zIndex: number
  active: boolean
}

/**
 * State of every window: position, size, minimized/maximized, and stacking order.
 * `ids` must be known when the hook starts (the caller waits for the module list);
 * `area` is the size of the workspace, measured by the caller.
 */
export function useWindowManager(ids: string[], area: Size) {
  const [saved, setSaved] = useState<Record<string, WindowState>>(() => load(ids))
  // Window ids from back to front: the last one is drawn on top.
  const [order, setOrder] = useState<string[]>(ids)

  useEffect(() => save(saved), [saved])

  const defaults = useMemo(() => gridRects(ids.length, area), [ids.length, area])

  const stateOf = useCallback(
    (id: string): WindowState =>
      saved[id] ?? { ...defaults[Math.max(ids.indexOf(id), 0)], minimized: false, maximized: false },
    [saved, defaults, ids],
  )

  const update = useCallback(
    (id: string, change: Partial<WindowState>) =>
      setSaved((current) => ({ ...current, [id]: { ...stateOf(id), ...current[id], ...change } })),
    [stateOf],
  )

  const visibleOrder = order.filter((id) => !stateOf(id).minimized)
  const activeId = visibleOrder.at(-1) ?? null

  const focus = useCallback((id: string) => setOrder((current) => [...current.filter((x) => x !== id), id]), [])

  const windows: ManagedWindow[] = ids.map((id) => {
    const state = stateOf(id)
    return {
      id,
      state,
      rect: state.maximized ? { x: 0, y: 0, ...area } : clampRect(state, area),
      zIndex: order.indexOf(id) + 1,
      active: id === activeId,
    }
  })

  return {
    ready: area.width > 0 && area.height > 0,
    windows,
    activeId,
    focus,
    move: (id: string, rect: Rect) => update(id, rect),
    minimize: (id: string) => update(id, { minimized: true }),
    toggleMaximize: (id: string) => {
      update(id, { maximized: !stateOf(id).maximized, minimized: false })
      focus(id)
    },
    /** Taskbar button, as on Windows: restore, minimize if already in front, else bring to front. */
    taskbarClick: (id: string) => {
      if (stateOf(id).minimized) {
        update(id, { minimized: false })
        focus(id)
      } else if (id === activeId) {
        update(id, { minimized: true })
      } else {
        focus(id)
      }
    },
    /** Lays the visible windows out in a grid (and un-maximizes them). */
    arrange: () => {
      const visible = ids.filter((id) => !stateOf(id).minimized)
      const rects = gridRects(visible.length, area)
      setSaved((current) => {
        const next = { ...current }
        visible.forEach((id, index) => {
          next[id] = { ...stateOf(id), ...rects[index], maximized: false, minimized: false }
        })
        return next
      })
    },
  }
}
