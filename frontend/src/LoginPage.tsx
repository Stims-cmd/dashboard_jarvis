import { useState, type FormEvent } from 'react'
import { api, UnauthorizedError } from './api'
import { ReactorLogo } from './components/icons'
import ThemeToggle from './components/ThemeToggle'

export default function LoginPage({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      await api.login(username, password)
      onLoggedIn()
    } catch (err) {
      setError(err instanceof UnauthorizedError ? 'Identifiants incorrects.' : 'Connexion impossible, réessaie plus tard.')
    } finally {
      setPassword('')
      setPending(false)
    }
  }

  return (
    <main className="login-screen">
      <form className="login" onSubmit={handleSubmit}>
        <ThemeToggle className="login-theme" />
        <div className="login-brand">
          <ReactorLogo size={64} spinning />
          <h1>JARVIS</h1>
          <p className="login-subtitle">Accès sécurisé</p>
        </div>
        <label>
          Utilisateur
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>
        <label>
          Mot de passe
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={pending}>
          {pending ? 'Connexion…' : 'Se connecter'}
        </button>
      </form>
    </main>
  )
}
