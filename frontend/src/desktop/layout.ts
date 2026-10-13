// Pure geometry of the desktop: no React, no DOM, easy to reason about.

export interface Size {
  width: number
  height: number
}

export interface Rect extends Size {
  x: number
  y: number
}

export interface WindowState extends Rect {
  minimized: boolean
  maximized: boolean
}

export const MIN_WIDTH = 260
export const MIN_HEIGHT = 160
const GAP = 14

/** Grid of `count` windows filling the area: ceil(sqrt(count)) columns. */
export function gridRects(count: number, area: Size): Rect[] {
  if (count === 0) return []
  const cols = Math.ceil(Math.sqrt(count))
  const rows = Math.ceil(count / cols)
  const width = Math.max(MIN_WIDTH, Math.floor((area.width - GAP * (cols + 1)) / cols))
  const height = Math.max(MIN_HEIGHT, Math.floor((area.height - GAP * (rows + 1)) / rows))
  return Array.from({ length: count }, (_, index) => ({
    x: GAP + (index % cols) * (width + GAP),
    y: GAP + Math.floor(index / cols) * (height + GAP),
    width,
    height,
  }))
}

/** Keeps a window inside the area (after the browser window was made smaller). */
export function clampRect(rect: Rect, area: Size): Rect {
  const width = Math.min(Math.max(rect.width, MIN_WIDTH), Math.max(area.width, MIN_WIDTH))
  const height = Math.min(Math.max(rect.height, MIN_HEIGHT), Math.max(area.height, MIN_HEIGHT))
  return {
    width,
    height,
    x: Math.min(Math.max(rect.x, 0), Math.max(area.width - width, 0)),
    y: Math.min(Math.max(rect.y, 0), Math.max(area.height - height, 0)),
  }
}

/** One saved window state, or null if malformed (storage is never trusted). */
export function toState(value: unknown): WindowState | null {
  if (typeof value !== 'object' || value === null) return null
  const v = value as Record<string, unknown>
  const numbers = ['x', 'y', 'width', 'height'].every((key) => typeof v[key] === 'number' && Number.isFinite(v[key]))
  if (!numbers) return null
  return {
    x: v.x as number,
    y: v.y as number,
    width: v.width as number,
    height: v.height as number,
    minimized: v.minimized === true,
    maximized: v.maximized === true,
  }
}

/** Parses the saved states of all windows, dropping anything malformed. */
export function parseSaved(raw: string | null): Record<string, WindowState> {
  try {
    const data = JSON.parse(raw ?? '{}') as unknown
    if (typeof data !== 'object' || data === null) return {}
    const result: Record<string, WindowState> = {}
    for (const [id, value] of Object.entries(data)) {
      const state = toState(value)
      if (state) result[id] = state
    }
    return result
  } catch {
    return {}
  }
}
