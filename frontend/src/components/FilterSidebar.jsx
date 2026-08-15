import { MapPin, Briefcase, UserRound, RotateCcw } from 'lucide-react'

export const REGIONS = ['서울', '경기', '인천', '부산', '대전', '대구', '광주', '충남', '경남', '전국']
export const EMPLOYMENT_TYPES = ['정규직', '계약직', '아르바이트', '인턴', '프리랜서']
export const EXPERIENCES = ['신입', '경력', '경력무관']

function Group({ icon: Icon, title, options, selected, onToggle }) {
  return (
    <div className="border-b border-slate-100 px-5 py-4 last:border-0">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
        <Icon className="h-4 w-4 text-slate-400" />
        {title}
      </h3>
      <div className="space-y-1.5">
        {options.map((option) => (
          <label key={option} className="flex cursor-pointer items-center gap-2.5 text-sm text-slate-600 hover:text-slate-900">
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => onToggle(option)}
              className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
            />
            {option}
          </label>
        ))}
      </div>
    </div>
  )
}

export default function FilterSidebar({ filters, onToggle, onReset }) {
  const activeCount =
    filters.locations.length + filters.employmentTypes.length + filters.experiences.length

  return (
    <aside className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <h2 className="font-semibold text-slate-900">
          상세 필터
          {activeCount > 0 && (
            <span className="ml-2 rounded-full bg-slate-900 px-2 py-0.5 text-xs text-white">{activeCount}</span>
          )}
        </h2>
        {activeCount > 0 && (
          <button
            onClick={onReset}
            className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            초기화
          </button>
        )}
      </div>

      <Group
        icon={MapPin}
        title="지역"
        options={REGIONS}
        selected={filters.locations}
        onToggle={(value) => onToggle('locations', value)}
      />
      <Group
        icon={Briefcase}
        title="고용형태"
        options={EMPLOYMENT_TYPES}
        selected={filters.employmentTypes}
        onToggle={(value) => onToggle('employmentTypes', value)}
      />
      <Group
        icon={UserRound}
        title="경력"
        options={EXPERIENCES}
        selected={filters.experiences}
        onToggle={(value) => onToggle('experiences', value)}
      />
    </aside>
  )
}
