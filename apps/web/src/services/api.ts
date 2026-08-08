/**
 * HTTP client cho backend.
 *
 * Mọi lời gọi API đi qua đây để việc xử lý lỗi, timeout và parse response là
 * thống nhất. Component không bao giờ gọi `fetch` trực tiếp.
 */

/** Lỗi có cấu trúc do backend trả về (khớp với `AppError.to_payload()`). */
export interface ApiErrorPayload {
  code: string
  message: string
  details?: Record<string, unknown>
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message)
    this.name = 'ApiError'
    this.status = status
    this.code = payload.code
    this.details = payload.details ?? {}
  }

  /** True khi thử lại có khả năng thành công (lỗi tạm thời của hạ tầng). */
  get isRetryable(): boolean {
    return this.status >= 500 || this.status === 429
  }
}

/** Backend không phản hồi: mất mạng, server chưa chạy, hoặc quá hạn chờ. */
export class NetworkError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options)
    this.name = 'NetworkError'
  }
}

const DEFAULT_TIMEOUT_MS = 30_000

export interface RequestOptions extends Omit<RequestInit, 'body' | 'headers'> {
  body?: unknown
  timeoutMs?: number
  signal?: AbortSignal
  /**
   * Siết hẹp hơn `HeadersInit` của DOM một cách có chủ đích.
   *
   * `HeadersInit` còn cho phép `Headers` và `string[][]`, mà cả hai đều không
   * spread được vào object literal: `{...['a','b']}` cho ra `{0:'a',1:'b'}` —
   * header hỏng trong im lặng. Chỉ chấp nhận record khiến lỗi đó không thể xảy ra.
   */
  headers?: Record<string, string>
  /**
   * Các mã HTTP không-2xx được coi là phản hồi hợp lệ và trả về nguyên body
   * thay vì ném lỗi.
   *
   * Cần cho những endpoint dùng status code để truyền đạt trạng thái nghiệp vụ
   * chứ không phải lỗi — ví dụ `/health/ready` trả 503 kèm body mô tả đầy đủ
   * dependency nào đang hỏng. Nếu không có tuỳ chọn này, body đó sẽ bị vứt đi
   * và thay bằng một lỗi HTTP chung chung.
   */
  acceptStatuses?: readonly number[]
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    body,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal,
    headers,
    acceptStatuses = [],
    ...rest
  } = options

  // Timeout riêng, kết hợp với signal của caller (ví dụ khi React Query huỷ query).
  const timeoutController = new AbortController()
  const timer = setTimeout(() => {
    timeoutController.abort()
  }, timeoutMs)
  const combinedSignal = signal
    ? AbortSignal.any([signal, timeoutController.signal])
    : timeoutController.signal

  let response: Response
  try {
    response = await fetch(path, {
      ...rest,
      signal: combinedSignal,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    })
  } catch (cause) {
    // Caller chủ động huỷ thì không phải lỗi — ném lại nguyên trạng.
    if (signal?.aborted) throw cause
    if (timeoutController.signal.aborted) {
      throw new NetworkError(`Yêu cầu quá ${timeoutMs / 1000}s không phản hồi.`, { cause })
    }
    throw new NetworkError(
      'Không kết nối được tới máy chủ. Kiểm tra backend đã chạy chưa (make api).',
      { cause },
    )
  } finally {
    clearTimeout(timer)
  }

  if (response.status === 204) return undefined as T

  const accepted = response.ok || acceptStatuses.includes(response.status)

  const raw = await response.text()
  let parsed: unknown = undefined
  if (raw) {
    try {
      parsed = JSON.parse(raw)
    } catch {
      // Body không phải JSON — chỉ là vấn đề khi response cũng là lỗi.
      if (!accepted) {
        throw new ApiError(response.status, {
          code: 'invalid_response',
          message: `Máy chủ trả về phản hồi không hợp lệ (HTTP ${response.status}).`,
        })
      }
    }
  }

  if (!accepted) {
    const envelope = parsed as { error?: ApiErrorPayload } | undefined
    throw new ApiError(
      response.status,
      envelope?.error ?? {
        code: 'http_error',
        message: `Yêu cầu thất bại với mã HTTP ${response.status}.`,
      },
    )
  }

  return parsed as T
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'DELETE' }),
}

/* ---------------------------------------------------------------------------
 * Kiểu dữ liệu endpoint health — khớp với app/api/routes/health.py
 * ------------------------------------------------------------------------- */

export interface HealthResponse {
  status: string
  app: string
  version: string
  env: string
  uptime_seconds: number
}

export interface DependencyCheck {
  status: string
  [key: string]: unknown
}

export interface ReadinessResponse {
  status: 'ready' | 'not_ready'
  checks: {
    database: DependencyCheck
    task_queue: DependencyCheck
    ai_provider: DependencyCheck
  }
}

export const healthApi = {
  live: () => api.get<HealthResponse>('/health'),
  /**
   * Readiness trả HTTP 503 khi database chết, kèm body mô tả dependency nào
   * hỏng. 503 ở đây là câu trả lời hợp lệ chứ không phải lỗi giao vận, nên
   * phải khai báo `acceptStatuses` để giữ lại body.
   */
  ready: () =>
    api.get<ReadinessResponse>('/health/ready', { acceptStatuses: [503] }),
}
