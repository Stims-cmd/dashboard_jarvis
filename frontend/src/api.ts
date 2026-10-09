// Small wrapper around fetch for the Jarvis API (same origin, session cookie).

export class UnauthorizedError extends Error {}

export interface ModuleInfo {
  id: string
  title: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (response.status === 401) throw new UnauthorizedError()
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  // Some writes answer with an empty body (204, or 201 without content).
  const text = await response.text()
  return (text ? JSON.parse(text) : undefined) as T
}

export const api = {
  me: () => request<{ username: string }>('/api/auth/me'),
  login: (username: string, password: string) =>
    request<void>('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  modules: () => request<ModuleInfo[]>('/api/modules'),
  get: <T>(path: string) => request<T>(path),
  post: <T = void>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: (path: string, body: unknown) => request<void>(path, { method: 'PUT', body: JSON.stringify(body) }),
  del: (path: string) => request<void>(path, { method: 'DELETE' }),
}
