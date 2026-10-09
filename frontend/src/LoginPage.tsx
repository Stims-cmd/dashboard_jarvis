import { useState, type FormEvent } from 'react'
import { api, UnauthorizedError } from './api'

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
    <form className="login" onSubmit={handleSubmit}>
      <h1>Jarvis</h1>
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
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={pending}>
        {pending ? 'Connexion…' : 'Se connecter'}
      </button>
    </form>
  )
}
