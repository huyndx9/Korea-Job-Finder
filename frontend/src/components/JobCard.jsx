import { MapPin, Briefcase, Wallet, UserRound, ExternalLink, Calendar, FlaskConical, Hourglass } from 'lucide-react'

const SOURCE_LABELS = {
  saramin: '사람인',
  jobkorea: '잡코리아',
  wanted: '원티드',
  work24: '워크24',
  albamon: '알바몬',
  alba: '알바천국',
  indeed: '인디드',
  mock: '샘플',
}

function formatDate(value) {
  if (!value) return '등록일 미상'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '등록일 미상'
  return `등록일 ${date.toISOString().slice(0, 10)}`
}

// "D-3" while there is time left, "오늘 마감" on the last day, nothing once past.
// A missing deadline means 상시채용, not "unknown", so we say so.
function deadlineBadge(value) {
  if (!value) return { text: '상시채용', urgent: false, muted: true }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null

  const startOfToday = new Date()
  startOfToday.setHours(0, 0, 0, 0)
  const days = Math.ceil((date - startOfToday) / 86400000)

  if (days < 0) return { text: '마감', urgent: false, muted: true }
  if (days === 0) return { text: '오늘 마감', urgent: true }
  if (days <= 7) return { text: `D-${days}`, urgent: true }
  return { text: `D-${days}`, urgent: false }
}

function Meta({ icon: Icon, children }) {
  if (!children) return null
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-slate-600">
      <Icon className="h-4 w-4 shrink-0 text-slate-400" />
      {children}
    </span>
  )
}

export default function JobCard({ job, sourceLabels }) {
  // user-added sites are not in SOURCE_LABELS, so fall back to the live source list
  const sourceName = sourceLabels?.[job.source] ?? SOURCE_LABELS[job.source] ?? job.source
  const deadline = deadlineBadge(job.deadline)

  return (
    <article className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-slate-300 hover:shadow-md">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
              {sourceName}
            </span>
            {job.is_mock && (
              <span
                title="개발용 샘플 데이터입니다 (실제 공고가 아님)"
                className="inline-flex items-center gap-1 rounded-md bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800"
              >
                <FlaskConical className="h-3 w-3" />
                DEMO
              </span>
            )}
          </div>

          <h3 className="line-clamp-2 text-base font-semibold text-slate-900">{job.title}</h3>
          <p className="mt-1 text-sm font-medium text-slate-700">{job.company}</p>

          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
            <Meta icon={MapPin}>{job.location || job.location_region}</Meta>
            <Meta icon={Briefcase}>{job.employment_type}</Meta>
            <Meta icon={Wallet}>{job.salary}</Meta>
            <Meta icon={UserRound}>{job.experience}</Meta>
          </div>

          {job.description && (
            <p className="mt-3 line-clamp-2 text-sm text-slate-500">{job.description}</p>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-400">
            <span className="inline-flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5" />
              {formatDate(job.posted_at)}
            </span>
            {deadline && (
              <span
                className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium ${
                  deadline.urgent
                    ? 'bg-rose-50 text-rose-600'
                    : deadline.muted
                      ? 'text-slate-400'
                      : 'bg-slate-100 text-slate-600'
                }`}
              >
                <Hourglass className="h-3 w-3" />
                {deadline.text}
              </span>
            )}
          </div>
        </div>

        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-700 transition group-hover:border-slate-900 group-hover:bg-slate-900 group-hover:text-white"
        >
          원문 보기
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    </article>
  )
}
