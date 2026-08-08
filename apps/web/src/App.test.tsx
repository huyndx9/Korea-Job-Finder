import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { JSX, ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { healthApi } from './services/api'

vi.mock('./services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./services/api')>()
  return { ...actual, healthApi: { live: vi.fn(), ready: vi.fn() } }
})

function renderApp(): void {
  // retry: false — nếu không, test lỗi sẽ phải chờ hết các lần thử lại.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const Wrapper = ({ children }: { children: ReactNode }): JSX.Element => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  render(<App />, { wrapper: Wrapper })
}

const LIVE_OK = {
  status: 'ok',
  app: 'VietJob Korea AI',
  version: '0.1.0',
  env: 'development',
  uptime_seconds: 12.7,
}

beforeEach(() => {
  vi.mocked(healthApi.live).mockReset()
  vi.mocked(healthApi.ready).mockReset()
})

describe('App', () => {
  it('hiển thị skeleton trong lúc đang tải', () => {
    vi.mocked(healthApi.live).mockReturnValue(new Promise(() => {}))
    vi.mocked(healthApi.ready).mockReturnValue(new Promise(() => {}))

    renderApp()
    expect(screen.getAllByLabelText('Đang tải').length).toBeGreaterThan(0)
  })

  it('hiển thị thông tin ứng dụng lấy từ backend', async () => {
    vi.mocked(healthApi.live).mockResolvedValue(LIVE_OK)
    vi.mocked(healthApi.ready).mockReturnValue(new Promise(() => {}))

    renderApp()
    expect(await screen.findByText('0.1.0')).toBeInTheDocument()
    expect(screen.getByText('development')).toBeInTheDocument()
    expect(screen.getByText('13 giây')).toBeInTheDocument()
  })

  it('hiển thị dependency đang hoạt động', async () => {
    vi.mocked(healthApi.live).mockResolvedValue(LIVE_OK)
    vi.mocked(healthApi.ready).mockResolvedValue({
      status: 'ready',
      checks: {
        database: { status: 'up', server_version: '8.0.46' },
        task_queue: { status: 'up', backend: 'thread' },
        ai_provider: { status: 'up', provider: 'null', configured: false },
      },
    })

    renderApp()
    expect(await screen.findByText('8.0.46')).toBeInTheDocument()
    expect(screen.getAllByText('Hoạt động')).toHaveLength(3)
  })

  it('hiển thị hướng dẫn khắc phục khi database không kết nối được', async () => {
    vi.mocked(healthApi.live).mockResolvedValue(LIVE_OK)
    vi.mocked(healthApi.ready).mockResolvedValue({
      status: 'not_ready',
      checks: {
        database: { status: 'down', error: 'OperationalError' },
        task_queue: { status: 'up', backend: 'thread' },
        ai_provider: { status: 'up', provider: 'null', configured: false },
      },
    })

    renderApp()
    expect(await screen.findByText('Không kết nối')).toBeInTheDocument()
    // Thông báo lỗi phải chỉ ra hành động cụ thể, không chỉ nêu tên exception.
    expect(screen.getByText(/mysql_setup\.sql/)).toBeInTheDocument()
  })

  it('báo lỗi rõ ràng khi backend chưa chạy', async () => {
    vi.mocked(healthApi.live).mockRejectedValue(new Error('Không kết nối được tới máy chủ.'))
    vi.mocked(healthApi.ready).mockRejectedValue(new Error('Không kết nối được tới máy chủ.'))

    renderApp()
    expect(await screen.findAllByRole('alert')).not.toHaveLength(0)
    expect(screen.getAllByText('Không gọi được backend').length).toBeGreaterThan(0)
  })
})
