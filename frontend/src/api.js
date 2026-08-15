// Thin wrapper over the FastAPI backend.
// Empty base = same origin, which the Vite dev proxy forwards to :8000.
const BASE = import.meta.env.VITE_API_BASE ?? ''

async function request(path, options) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new Error('백엔드에 연결할 수 없습니다. run-backend.bat 을 실행해 주세요.')
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep the status-code message */
    }
    throw new Error(detail)
  }
  if (response.status === 204) return null // DELETE answers with no body
  return response.json()
}

export function getHealth() {
  return request('/api/health')
}

export function getSources() {
  return request('/api/sources')
}

export function searchJobs({ keywords, sources, page = 1, limit = 20, sort = 'latest' }) {
  return request('/api/search', {
    method: 'POST',
    body: JSON.stringify({ keywords, sources, page, limit, sort }),
  })
}

// ---- user-added job sites --------------------------------------------------

export function testCustomSource(config) {
  return request('/api/sources/custom/test', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export function createCustomSource(config) {
  return request('/api/sources/custom', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export function deleteCustomSource(name) {
  return request(`/api/sources/custom/${encodeURIComponent(name)}`, { method: 'DELETE' })
}

export function listJobs({ keywords = [], sources = [], locations = [], employmentTypes = [], experiences = [], page = 1, limit = 20, sort = 'latest' }) {
  const params = new URLSearchParams()
  keywords.forEach((k) => params.append('keyword', k))
  sources.forEach((s) => params.append('source', s))
  locations.forEach((l) => params.append('location', l))
  employmentTypes.forEach((t) => params.append('employment_type', t))
  experiences.forEach((e) => params.append('experience', e))
  params.set('page', page)
  params.set('limit', limit)
  params.set('sort', sort)
  return request(`/api/jobs?${params.toString()}`)
}
