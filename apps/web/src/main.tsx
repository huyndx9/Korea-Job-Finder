import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from '@/App'
import { ApiError } from '@/services/api'

import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Lỗi do client gửi sai (4xx) thì thử lại cũng vô ích.
        if (error instanceof ApiError && !error.isRetryable) return false
        return failureCount < 2
      },
    },
  },
})

const container = document.getElementById('root')
if (!container) {
  throw new Error('Không tìm thấy phần tử #root — index.html có thể đã bị sửa.')
}

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
