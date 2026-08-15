import { Loader2, Search } from 'lucide-react'

export default function LoadingState({ sources }) {
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="flex items-center gap-2 font-semibold text-slate-900">
          <Search className="h-5 w-5 animate-pulse text-slate-400" />
          검색 중입니다...
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          {sources.map((source) => (
            <span
              key={source.name}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600"
            >
              <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
              {source.label}
            </span>
          ))}
        </div>
      </div>

      {[0, 1, 2].map((index) => (
        <div key={index} className="animate-pulse rounded-2xl border border-slate-200 bg-white p-5">
          <div className="h-4 w-20 rounded bg-slate-100" />
          <div className="mt-3 h-5 w-2/3 rounded bg-slate-100" />
          <div className="mt-2 h-4 w-1/3 rounded bg-slate-100" />
          <div className="mt-4 flex gap-4">
            <div className="h-4 w-24 rounded bg-slate-100" />
            <div className="h-4 w-20 rounded bg-slate-100" />
            <div className="h-4 w-28 rounded bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  )
}
