import { useEffect, useState, type FormEvent } from 'react'
import { api, UnauthorizedError } from './api'
import { ReactorLogo } from './components/icons'
import ThemeToggle from './components/ThemeToggle'

export default function LoginPage({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  // Second factor asked only when the server has a TOTP secret.
  const [totp, setTotp] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    api
      .authConfig()
      .then((config) => setTotp(config.totp))
      // On failure, show the field anyway: an unneeded code is simply ignored.
      .catch(() => setTotp(true))
  }, [])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      await api.login(username, password, code)
      onLoggedIn()
    } catch (err) {
      setError(err instanceof UnauthorizedError ? 'Identifiants incorrects.' : 'Connexion impossible, réessaie plus tard.')
    } finally {
      setPassword('')
      setCode('')
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
        {totp && (
          <label>
            Code de vérification
            <input
              className="login-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="\d{6}"
              maxLength={6}
              placeholder="000000"
              title="Les 6 chiffres affichés par ton application d'authentification"
              required
            />
          </label>
        )}
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
