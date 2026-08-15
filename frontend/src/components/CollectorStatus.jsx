import { AlertTriangle } from 'lucide-react'
import { statusMeta, TONE_TEXT } from '../sourceStatus'

export default function CollectorStatus({ sources }) {
  if (!sources?.length) return null

  return (
    <div className="flex flex-wrap gap-2">
      {sources.map((source) => {
        const meta = statusMeta(source.status)
        const Icon = meta.icon
        return (
          <span
            key={source.source}
            title={source.error ?? `${source.elapsed_ms}ms`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm"
          >
            <Icon className={`h-4 w-4 ${TONE_TEXT[meta.tone]}`} />
            <span className="font-medium text-slate-700">{source.label}</span>
            <span className={source.ok ? 'text-slate-500' : TONE_TEXT[meta.tone]}>
              {source.ok ? source.count : meta.label}
            </span>
          </span>
        )
      })}
    </div>
  )
}

export function CollectorErrors({ sources }) {
  const failed = (sources ?? []).filter((source) => source.error)
  if (!failed.length) return null

  const anyBad = failed.some((source) => statusMeta(source.status).tone === 'bad')

  return (
    <div
      className={`space-y-1.5 rounded-xl border px-4 py-3 ${
        anyBad ? 'border-rose-200 bg-rose-50' : 'border-amber-200 bg-amber-50'
      }`}
    >
      {failed.map((source) => {
        const meta = statusMeta(source.status)
        const bad = meta.tone === 'bad'
        return (
          <p
            key={source.source}
            className={`flex items-start gap-2 text-sm ${bad ? 'text-rose-900' : 'text-amber-900'}`}
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              <strong>{source.label}</strong>
              <span className="mx-1.5 font-medium">· {meta.label} ·</span>
              {source.is_mock && <span className="mr-1">샘플 데이터로 대체됨 —</span>}
              <span className={bad ? 'text-rose-800/80' : 'text-amber-800/80'}>{source.error}</span>
            </span>
          </p>
        )
      })}
    </div>
  )
}
