import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError, healthApi, NetworkError } from './api'

function mockFetch(response: Response | Promise<Response> | Error): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => (response instanceof Error ? Promise.reject(response) : Promise.resolve(response))),
  )
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => {
  vi.unstubAllGlobals()
})

describe('api client', () => {
  it('trả về body đã parse khi thành công', async () => {
    mockFetch(jsonResponse({ id: 1, title: 'Nhân viên kinh doanh' }))
    await expect(api.get('/api/jobs/1')).resolves.toEqual({ id: 1, title: 'Nhân viên kinh doanh' })
  })

  it('trả về undefined cho 204 No Content', async () => {
    mockFetch(new Response(null, { status: 204 }))
    await expect(api.delete('/api/jobs/1/save')).resolves.toBeUndefined()
  })

  it('chuyển error envelope của backend thành ApiError', async () => {
    mockFetch(
      jsonResponse({ error: { code: 'not_found', message: 'Không tìm thấy job.' } }, 404),
    )
    await expect(api.get('/api/jobs/999')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      code: 'not_found',
      message: 'Không tìm thấy job.',
    })
  })

  it('giữ lại details trong error envelope', async () => {
    mockFetch(
      jsonResponse(
        { error: { code: 'validation_error', message: 'Sai dữ liệu', details: { field: 'email' } } },
        422,
      ),
    )
    await expect(api.get('/api/profile')).rejects.toMatchObject({
      details: { field: 'email' },
    })
  })

  it('không sập khi body lỗi không phải JSON', async () => {
    mockFetch(new Response('<html>502 Bad Gateway</html>', { status: 502 }))
    await expect(api.get('/api/jobs')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'invalid_response',
    })
  })

  it('báo NetworkError khi backend chưa chạy', async () => {
    mockFetch(new TypeError('Failed to fetch'))
    const error = await api.get('/api/jobs').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(NetworkError)
    expect((error as NetworkError).message).toContain('Không kết nối được')
  })

  it('gửi JSON body kèm đúng Content-Type khi POST', async () => {
    mockFetch(jsonResponse({ ok: true }))
    await api.post('/api/jobs/search', { keyword: '베트남' })

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(JSON.stringify({ keyword: '베트남' }))
    expect((init?.headers as Record<string, string>)['Content-Type']).toBe('application/json')
  })

  it('không gắn Content-Type khi GET không có body', async () => {
    mockFetch(jsonResponse({}))
    await api.get('/api/jobs')

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    expect((init?.headers as Record<string, string>)['Content-Type']).toBeUndefined()
  })
})

describe('ApiError.isRetryable', () => {
  it.each([500, 502, 503, 429])('coi %i là có thể thử lại', (status) => {
    expect(new ApiError(status, { code: 'x', message: 'y' }).isRetryable).toBe(true)
  })

  it.each([400, 401, 404, 409, 422])('coi %i là không nên thử lại', (status) => {
    expect(new ApiError(status, { code: 'x', message: 'y' }).isRetryable).toBe(false)
  })
})

describe('healthApi.ready', () => {
  it('giữ nguyên body khi backend trả 503', async () => {
    // Readiness dùng 503 để báo "database chết" nhưng body vẫn hợp lệ.
    // Nếu client coi đây là lỗi giao vận thì thông tin chẩn đoán sẽ mất sạch.
    mockFetch(
      jsonResponse(
        {
          status: 'not_ready',
          checks: {
            database: { status: 'down', error: 'OperationalError' },
            task_queue: { status: 'up', backend: 'thread' },
            ai_provider: { status: 'up', provider: 'null', configured: false },
          },
        },
        503,
      ),
    )

    const result = await healthApi.ready()
    expect(result.status).toBe('not_ready')
    expect(result.checks.database).toEqual({ status: 'down', error: 'OperationalError' })
    expect(result.checks.task_queue.backend).toBe('thread')
  })

  it('parse bình thường khi backend trả 200', async () => {
    mockFetch(
      jsonResponse({
        status: 'ready',
        checks: {
          database: { status: 'up', server_version: '8.0.46' },
          task_queue: { status: 'up', backend: 'thread' },
          ai_provider: { status: 'up', provider: 'null', configured: false },
        },
      }),
    )

    const result = await healthApi.ready()
    expect(result.status).toBe('ready')
    expect(result.checks.database['server_version']).toBe('8.0.46')
  })

  it('vẫn ném lỗi với các mã không được khai báo chấp nhận', async () => {
    mockFetch(jsonResponse({ error: { code: 'internal_error', message: 'Lỗi' } }, 500))
    await expect(healthApi.ready()).rejects.toBeInstanceOf(ApiError)
  })
})
