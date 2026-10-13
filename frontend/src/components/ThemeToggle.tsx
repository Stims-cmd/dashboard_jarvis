import { useState } from 'react'
import { saveTheme, savedTheme, systemTheme, type Theme } from '../theme'
import { MoonIcon, SunIcon } from './icons'

export default function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>(() => savedTheme() ?? systemTheme())
  const next: Theme = theme === 'dark' ? 'light' : 'dark'
  const label = next === 'light' ? 'Passer en thème clair' : 'Passer en thème sombre'

  return (
    <button
      type="button"
      className={className}
      title={label}
      aria-label={label}
      onClick={() => {
        saveTheme(next)
        setTheme(next)
      }}
    >
      {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
    </button>
  )
}
