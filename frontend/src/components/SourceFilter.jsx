import { Plus, Trash2, PlugZap, RefreshCw, Loader2 } from 'lucide-react'

import { statusMeta, TONE_TEXT } from '../sourceStatus'

export default function SourceFilter({
  sources,
  selected,
  onToggle,
  onSelectAll,
  onClearAll,
  onAddClick,
  onDelete,
  loadError,
  loading,
  onRetry,
}) {
  const problems = sources.filter((source) => !source.available)

  // An empty panel is never "no sources exist" - it means we could not reach the
  // backend. Say so, and offer a way out that is not "somehow know to press F5".
  if (!sources.length) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 font-semibold text-slate-900">채용 사이트</h2>
        <div className="flex flex-col items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3.5">
          <p className="flex items-start gap-2 text-sm text-amber-900">
            <PlugZap className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              <strong>백엔드에 연결할 수 없습니다.</strong>
              <br />
              <code className="rounded bg-amber-100 px-1">run-backend.bat</code> (또는{' '}
              <code className="rounded bg-amber-100 px-1">start.bat</code>)을 실행한 뒤 “다시 시도”를 눌러 주세요.
              {loadError && <span className="mt-1 block text-xs text-amber-800/80">({loadError})</span>}
            </span>
          </p>
          <button
            onClick={onRetry}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm font-medium text-amber-900 transition hover:border-amber-500 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            다시 시도
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold text-slate-900">채용 사이트</h2>
        <div className="flex items-center gap-2 text-sm">
          <button onClick={onSelectAll} className="text-slate-600 underline-offset-2 hover:text-slate-900 hover:underline">
            모두 선택
          </button>
          <span className="text-slate-300">|</span>
          <button onClick={onClearAll} className="text-slate-600 underline-offset-2 hover:text-slate-900 hover:underline">
            모두 해제
          </button>
          <button
            onClick={onAddClick}
            className="ml-1 inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2.5 py-1 font-medium text-slate-700 transition hover:border-slate-900 hover:bg-slate-900 hover:text-white"
          >
            <Plus className="h-3.5 w-3.5" />
            사이트 추가
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {sources.map((source) => {
          const checked = selected.includes(source.name)
          const meta = statusMeta(source.status)
          const Icon = meta.icon
          return (
            <label
              key={source.name}
              title={source.message || meta.hint}
              className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3.5 py-2 text-sm transition ${
                checked
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : 'border-slate-200 bg-white text-slate-700 hover:border-slate-400'
              }`}
            >
              <input type="checkbox" checked={checked} onChange={() => onToggle(source.name)} className="sr-only" />
              <span>{source.label}</span>
              {source.custom && (
                <span
                  className={`rounded px-1 text-[10px] font-semibold ${
                    checked ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  직접
                </span>
              )}
              <Icon
                className={`h-3.5 w-3.5 ${
                  checked && meta.tone !== 'bad' ? 'text-white/70' : TONE_TEXT[meta.tone]
                }`}
                aria-label={meta.label}
              />
              {source.custom && (
                <button
                  type="button"
                  title={`${source.label} 삭제`}
                  onClick={(event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    onDelete(source)
                  }}
                  className={`-mr-1 rounded p-0.5 ${
                    checked ? 'text-white/60 hover:text-white' : 'text-slate-400 hover:text-rose-600'
                  }`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </label>
          )
        })}
      </div>

      {problems.length > 0 && (
        <ul className="mt-3 space-y-1">
          {problems.map((source) => {
            const meta = statusMeta(source.status)
            return (
              <li key={source.name} className="text-xs text-slate-500">
                <strong className="text-slate-700">{source.label}</strong>
                <span className={`mx-1.5 ${TONE_TEXT[meta.tone]}`}>· {meta.label} ·</span>
                {source.message || meta.hint}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
