import { ChevronLeft, ChevronRight } from 'lucide-react'

// 1 2 3 4 5 ... 12  — a sliding window around the current page
function pageWindow(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)

  const pages = new Set([1, total, current])
  for (let offset = -2; offset <= 2; offset += 1) {
    const page = current + offset
    if (page > 1 && page < total) pages.add(page)
  }

  const sorted = [...pages].sort((a, b) => a - b)
  const withGaps = []
  sorted.forEach((page, index) => {
    if (index > 0 && page - sorted[index - 1] > 1) withGaps.push('...')
    withGaps.push(page)
  })
  return withGaps
}

export default function Pagination({ page, totalPages, onChange }) {
  if (!totalPages || totalPages <= 1) return null

  const base = 'inline-flex h-9 min-w-9 items-center justify-center rounded-lg border px-3 text-sm transition'

  return (
    <nav className="flex flex-wrap items-center justify-center gap-1.5 pt-2" aria-label="페이지 이동">
      <button
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        className={`${base} border-slate-200 bg-white text-slate-600 hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40`}
      >
        <ChevronLeft className="h-4 w-4" />
      </button>

      {pageWindow(page, totalPages).map((entry, index) =>
        entry === '...' ? (
          <span key={`gap-${index}`} className="px-1 text-slate-400">
            ...
          </span>
        ) : (
          <button
            key={entry}
            onClick={() => onChange(entry)}
            aria-current={entry === page ? 'page' : undefined}
            className={`${base} ${
              entry === page
                ? 'border-slate-900 bg-slate-900 font-semibold text-white'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-400'
            }`}
          >
            {entry}
          </button>
        ),
      )}

      <button
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
        className={`${base} border-slate-200 bg-white text-slate-600 hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40`}
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </nav>
  )
}
