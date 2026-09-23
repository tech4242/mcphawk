async function request(method, path, { params, body } = {}) {
  const url = new URL(path, window.location.origin)
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value)
  }
  const response = await fetch(url, {
    method,
    headers: {
      'X-MCPHawk': '1',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `${response.status} ${response.statusText}`)
  return data
}

export const api = {
  stats: () => request('GET', '/api/stats'),
  runs: () => request('GET', '/api/runs'),
  run: (key) => request('GET', `/api/runs/${encodeURIComponent(key)}`),
  sessions: (params) => request('GET', '/api/sessions', { params }),
  session: (id) => request('GET', `/api/sessions/${id}`),
  sessionMessages: (id) => request('GET', `/api/sessions/${id}/messages`),
  sessionLint: (id) => request('GET', `/api/sessions/${id}/lint`),
  exchanges: (params) => request('GET', '/api/exchanges', { params }),
  exchange: (id) => request('GET', `/api/exchanges/${id}`),
  message: (id) => request('GET', `/api/messages/${id}`),
  problems: (params) => request('GET', '/api/problems', { params }),
  cost: (params) => request('GET', '/api/cost', { params }),
  compare: (before, after) => request('GET', '/api/compare', { params: { before, after } }),
  setup: () => request('GET', '/api/setup'),
  replay: (id, params) => request('POST', `/api/exchanges/${id}/replay`, { body: { params } }),
  clear: () => request('DELETE', '/api/data', { params: { confirm: true } }),
}
