import { useCallback, useEffect, useState } from 'react'
import { api, UnauthorizedError } from './api'
import Desktop from './Desktop'
import LoginPage from './LoginPage'

type AuthState = 'loading' | 'anonymous' | 'authenticated'

export default function App() {
  const [auth, setAuth] = useState<AuthState>('loading')
  const handleLoggedOut = useCallback(() => setAuth('anonymous'), [])

  useEffect(() => {
    api
      .me()
      .then(() => setAuth('authenticated'))
      .catch((error: unknown) => {
        if (!(error instanceof UnauthorizedError)) console.error(error)
        setAuth('anonymous')
      })
  }, [])

  if (auth === 'loading') return <p className="centered">Chargement…</p>
  if (auth === 'anonymous') return <LoginPage onLoggedIn={() => setAuth('authenticated')} />
  return <Desktop onLoggedOut={handleLoggedOut} />
}
