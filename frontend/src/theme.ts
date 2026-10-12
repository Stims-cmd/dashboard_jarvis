// Light / dark theme. Without an explicit choice, the system setting decides.
// The choice is a per-browser convenience: storage may be unavailable, so never fail on it.

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'jarvis.theme'

export function savedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

export function systemTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Sets data-theme on <html>: index.css picks the colour tokens from it. */
export function applyTheme(theme: Theme | null) {
  if (theme) document.documentElement.dataset.theme = theme
  else delete document.documentElement.dataset.theme
}

export function saveTheme(theme: Theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // ignore
  }
  applyTheme(theme)
}
