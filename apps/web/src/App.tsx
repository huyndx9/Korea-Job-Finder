import { useQuery } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, Loader2, RefreshCw, XCircle } from 'lucide-react'
import type { JSX } from 'react'

import { cn } from '@/lib/utils'
import { healthApi, type DependencyCheck, type ReadinessResponse } from '@/services/api'

/**
 * Trang trạng thái hệ thống.
 *
 * Ở Phase 1 đây là màn hình duy nhất, và nó có mục đích thật: xác nhận
 * frontend ↔ backend ↔ database đã thông suốt. Mọi giá trị hiển thị đều đến
 * từ backend, không có dữ liệu cứng.
 *
 * Phase 10 sẽ thay bằng dashboard đầy đủ; trang này chuyển thành /admin/health.
 */
export function App(): JSX.Element {
  const live = useQuery({ queryKey: ['health', 'live'], queryFn: healthApi.live })
  const ready = useQuery({
    queryKey: ['health', 'ready'],
    queryFn: healthApi.ready,
    refetchInterval: 15_000,
  })

  return (
    <div className="min-h-full">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-6 py-5">
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-ink">VietJob Korea AI</h1>
            <p className="text-sm text-ink-muted">Tổng hợp việc làm tại Hàn Quốc cho người Việt</p>
          </div>
          <button
            type="button"
            onClick={() => {
              void live.refetch()
              void ready.refetch()
            }}
            disabled={ready.isFetching}
            className={cn(
              'inline-flex shrink-0 items-center gap-2 rounded-lg border border-line-strong',
              'px-3 py-2 text-sm font-medium text-ink',
              'transition-colors hover:bg-surface-sunken',
              'disabled:cursor-not-allowed disabled:opacity-60',
            )}
          >
            <RefreshCw className={cn('size-4', ready.isFetching && 'animate-spin')} aria-hidden />
            Kiểm tra lại
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8">
        <section aria-labelledby="status-heading">
          <h2 id="status-heading" className="mb-1 text-base font-semibold tracking-tight text-ink">
            Trạng thái hệ thống
          </h2>
          <p className="mb-5 text-sm text-ink-muted">
            Phase 1 — kiểm chứng frontend, backend và database đã kết nối được với nhau.
          </p>

          {live.isPending ? (
            <StatusSkeleton />
          ) : live.isError ? (
            <BackendUnreachable error={live.error} />
          ) : (
            <dl className="rounded-card border border-line bg-surface px-4 shadow-card">
              <InfoRow label="Ứng dụng" value={live.data.app} />
              <InfoRow label="Phiên bản" value={live.data.version} />
              <InfoRow label="Môi trường" value={live.data.env} />
              <InfoRow
                label="Thời gian chạy"
                value={`${Math.round(live.data.uptime_seconds)} giây`}
              />
            </dl>
          )}
        </section>

        <section aria-labelledby="deps-heading" className="mt-10">
          <h2 id="deps-heading" className="mb-4 text-base font-semibold tracking-tight text-ink">
            Thành phần phụ thuộc
          </h2>

          {ready.isPending ? (
            <StatusSkeleton rows={3} />
          ) : ready.isError ? (
            <BackendUnreachable error={ready.error} />
          ) : (
            <DependencyList checks={ready.data.checks} />
          )}
        </section>
      </main>
    </div>
  )
}

function DependencyList({ checks }: { checks: ReadinessResponse['checks'] }): JSX.Element {
  return (
    <ul className="space-y-3">
      <DependencyCard name="MySQL" check={checks.database} detailKey="server_version" />
      <DependencyCard name="Hàng đợi tác vụ" check={checks.task_queue} detailKey="backend" />
      <DependencyCard name="AI provider" check={checks.ai_provider} detailKey="provider" />
    </ul>
  )
}

function DependencyCard({
  name,
  check,
  detailKey,
}: {
  name: string
  check: DependencyCheck
  detailKey: string
}): JSX.Element {
  const isUp = check.status === 'up'
  const detail = check[detailKey]
  const error = check['error']

  return (
    <li
      className={cn(
        'flex items-start gap-3 rounded-card border bg-surface p-4 shadow-card',
        isUp ? 'border-line' : 'border-danger/40',
      )}
    >
      {isUp ? (
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" aria-hidden />
      ) : (
        <XCircle className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span className="font-medium text-ink">{name}</span>
          <span className={cn('text-sm font-medium', isUp ? 'text-success' : 'text-danger')}>
            {isUp ? 'Hoạt động' : 'Không kết nối'}
          </span>
        </div>
        {typeof detail === 'string' && (
          <p className="mt-1 truncate text-sm text-ink-muted">{detail}</p>
        )}
        {typeof error === 'string' && (
          <p className="mt-1 text-sm text-danger">
            {error === 'OperationalError'
              ? 'Chưa cấu hình được kết nối. Chạy scripts/mysql_setup.sql rồi điền DATABASE_URL vào .env.'
              : error}
          </p>
        )}
      </div>
    </li>
  )
}

function InfoRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-3 last:border-0">
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="font-mono text-sm text-ink">{value}</dd>
    </div>
  )
}

function StatusSkeleton({ rows = 4 }: { rows?: number }): JSX.Element {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Đang tải">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-14 animate-pulse rounded-card bg-surface" />
      ))}
    </div>
  )
}

function BackendUnreachable({ error }: { error: Error }): JSX.Element {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-card border border-danger/40 bg-surface p-4"
    >
      <AlertCircle className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
      <div>
        <p className="font-medium text-ink">Không gọi được backend</p>
        <p className="mt-1 text-sm text-ink-muted">{error.message}</p>
        <p className="mt-2 text-sm text-ink-subtle">
          Khởi động backend bằng lệnh <code className="font-mono">.\make.ps1 api</code> rồi thử lại.
        </p>
      </div>
    </div>
  )
}

/** Dùng lại ở các màn hình sau. */
export function Spinner(): JSX.Element {
  return <Loader2 className="size-4 animate-spin" aria-hidden />
}
