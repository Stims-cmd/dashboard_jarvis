import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Display font, bundled with the app: nothing is loaded from Google Fonts.
import '@fontsource/rajdhani/latin-500.css'
import '@fontsource/rajdhani/latin-600.css'
import '@fontsource/rajdhani/latin-700.css'
import './index.css'
import App from './App.tsx'
import { applyTheme, savedTheme } from './theme'

// Before the first render, so the page never flashes in the wrong theme.
applyTheme(savedTheme())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
