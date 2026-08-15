import { Briefcase } from 'lucide-react'

export default function Header() {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-5 sm:px-6">
        <span className="grid h-11 w-11 place-items-center rounded-xl bg-slate-900 text-xl">🇰🇷</span>
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight text-slate-900">
            Korea Job Finder
            <Briefcase className="h-4 w-4 text-slate-400" />
          </h1>
          <p className="text-sm text-slate-500">
            여러 채용 사이트를 한 번에 검색하세요
          </p>
        </div>
      </div>
    </header>
  )
}
