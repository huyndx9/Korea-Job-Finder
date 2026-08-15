import { Search, Loader2 } from 'lucide-react'

const EXAMPLES = ['베트남어', '외국인', '베트남어 통역']

export default function SearchBar({ value, onChange, onSearch, loading }) {
  function handleSubmit(event) {
    event.preventDefault()
    onSearch()
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-4 h-5 w-5 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="예: 베트남어 통역 — 키워드를 띄어쓰기로 구분하세요"
            aria-label="검색 키워드"
            className="w-full rounded-xl border border-slate-300 bg-white py-3.5 pr-4 pl-12 text-base shadow-sm outline-none placeholder:text-slate-400 focus:border-slate-900 focus:ring-2 focus:ring-slate-900/10"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-7 py-3.5 font-semibold text-white shadow-sm transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Search className="h-5 w-5" />}
          {loading ? '검색 중...' : '검색'}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-slate-500">추천 검색어:</span>
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => onChange(example)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-600 transition hover:border-slate-900 hover:text-slate-900"
          >
            {example}
          </button>
        ))}
      </div>
    </form>
  )
}
