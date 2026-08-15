import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Clock, Globe, Layers, SearchX } from 'lucide-react'

import { deleteCustomSource, getSources, listJobs, searchJobs } from './api'
import Header from './components/Header'
import SearchBar from './components/SearchBar'
import SourceFilter from './components/SourceFilter'
import FilterSidebar from './components/FilterSidebar'
import JobCard from './components/JobCard'
import CollectorStatus, { CollectorErrors } from './components/CollectorStatus'
import Pagination from './components/Pagination'
import LoadingState from './components/LoadingState'
import AddSourceModal from './components/AddSourceModal'

const PAGE_SIZE = 20
const EMPTY_FILTERS = { locations: [], employmentTypes: [], experiences: [] }

const SORT_OPTIONS = [
  { value: 'latest', label: '최신순' },
  { value: 'oldest', label: '오래된순' },
  { value: 'salary_desc', label: '연봉 높은순' },
  { value: 'salary_asc', label: '연봉 낮은순' },
]

function toggleIn(list, value) {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
}

export default function App() {
  const [sources, setSources] = useState([])
  const [selectedSources, setSelectedSources] = useState([])

  const [query, setQuery] = useState('베트남어')
  const [searchedKeywords, setSearchedKeywords] = useState([])

  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [sort, setSort] = useState('latest')
  const [page, setPage] = useState(1)

  const [jobs, setJobs] = useState([])
  const [pagination, setPagination] = useState(null)
  const [collectorStatuses, setCollectorStatuses] = useState([])
  const [searchMeta, setSearchMeta] = useState(null)

  const [addOpen, setAddOpen] = useState(false)
  const [sourcesError, setSourcesError] = useState(null)
  const [loadingSources, setLoadingSources] = useState(false)
  const [searching, setSearching] = useState(false)
  const [loadingList, setLoadingList] = useState(false)
  const [error, setError] = useState(null)

  // ---- source list -------------------------------------------------------
  // /api/sources is an object keyed by source name; the UI wants an ordered list
  const loadSources = useCallback(async (selectDefaults) => {
    setLoadingSources(true)
    try {
      const byName = await getSources()
      const list = Object.values(byName)
      setSources(list)
      setSourcesError(null)
      if (selectDefaults) {
        setSelectedSources(list.filter((source) => source.default).map((source) => source.name))
      }
      return true
    } catch (err) {
      // keep this out of the generic error banner: the source panel explains it
      // in place, with a retry button
      setSourcesError(err.message)
      return false
    } finally {
      setLoadingSources(false)
    }
  }, [])

  useEffect(() => {
    loadSources(true)
  }, [loadSources])

  // The backend is usually started a moment after the page. Keep retrying
  // quietly so the app heals itself instead of sitting empty until a reload.
  useEffect(() => {
    if (!sourcesError) return undefined
    const timer = setInterval(() => loadSources(true), 5000)
    return () => clearInterval(timer)
  }, [sourcesError, loadSources])

  // ---- reading the stored results (filters / sort / paging all land here) --
  const loadJobs = useCallback(async () => {
    if (!searchedKeywords.length) return
    setLoadingList(true)
    try {
      const data = await listJobs({
        keywords: searchedKeywords,
        sources: selectedSources,
        locations: filters.locations,
        employmentTypes: filters.employmentTypes,
        experiences: filters.experiences,
        page,
        limit: PAGE_SIZE,
        sort,
      })
      setJobs(data.jobs)
      setPagination(data.pagination)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingList(false)
    }
  }, [searchedKeywords, selectedSources, filters, page, sort])

  useEffect(() => {
    loadJobs()
  }, [loadJobs])

  // ---- collecting from the sites ------------------------------------------
  async function handleSearch() {
    const keywords = query.trim().split(/\s+/).filter(Boolean)
    if (!keywords.length) return
    if (!sources.length) {
      // no sources at all means the backend is unreachable, not a user mistake
      setError('백엔드가 실행 중이 아닙니다. run-backend.bat 을 실행한 뒤 다시 시도해 주세요.')
      return
    }
    if (!selectedSources.length) {
      setError('채용 사이트를 최소 한 개 선택해 주세요.')
      return
    }

    setSearching(true)
    setError(null)
    try {
      // collect + store; the list itself is then read back through /api/jobs so
      // that searching, filtering, sorting and paging all share one code path
      const result = await searchJobs({ keywords, sources: selectedSources, page: 1, limit: 1 })
      setCollectorStatuses(result.sources)
      setSearchMeta({
        elapsedMs: result.elapsed_ms,
        duplicatesRemoved: result.duplicates_removed,
        siteCount: result.sources.length,
      })
      setFilters(EMPTY_FILTERS)
      setPage(1)
      setSearchedKeywords(keywords)
      // refresh the source panel so it shows live health (connected / invalid_key / ...)
      loadSources(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setSearching(false)
    }
  }

  function handleToggleFilter(group, value) {
    setFilters((current) => ({ ...current, [group]: toggleIn(current[group], value) }))
    setPage(1)
  }

  function handleToggleSource(name) {
    setSelectedSources((current) => toggleIn(current, name))
    setPage(1)
  }

  async function handleDeleteSource(source) {
    if (!window.confirm(`'${source.label}' 사이트를 삭제할까요?`)) return
    try {
      await deleteCustomSource(source.name)
      setSelectedSources((current) => current.filter((name) => name !== source.name))
      await loadSources(false)
    } catch (err) {
      setError(err.message)
    }
  }

  const hasSearched = searchedKeywords.length > 0
  const selectedSourceObjects = sources.filter((source) => selectedSources.includes(source.name))
  const sourceLabels = Object.fromEntries(sources.map((source) => [source.name, source.label]))

  return (
    <div className="min-h-full">
      <Header />

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6">
        <SearchBar value={query} onChange={setQuery} onSearch={handleSearch} loading={searching} />

        <SourceFilter
          sources={sources}
          selected={selectedSources}
          onToggle={handleToggleSource}
          onSelectAll={() => setSelectedSources(sources.map((source) => source.name))}
          onClearAll={() => setSelectedSources([])}
          onAddClick={() => setAddOpen(true)}
          onDelete={handleDeleteSource}
          loadError={sourcesError}
          loading={loadingSources}
          onRetry={() => loadSources(true)}
        />

        <AddSourceModal
          open={addOpen}
          onClose={() => setAddOpen(false)}
          onSaved={async (name) => {
            await loadSources(false)
            setSelectedSources((current) => [...current, name])
          }}
        />

        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
          <FilterSidebar
            filters={filters}
            onToggle={handleToggleFilter}
            onReset={() => {
              setFilters(EMPTY_FILTERS)
              setPage(1)
            }}
          />

          <section className="space-y-4">
            {searching ? (
              <LoadingState sources={selectedSourceObjects} />
            ) : (
              <>
                {hasSearched && (
                  <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="flex flex-wrap items-baseline justify-between gap-3">
                      <h2 className="text-lg font-bold text-slate-900">
                        검색 결과 <span className="text-slate-900">{pagination?.total ?? 0}</span>건
                      </h2>
                      <label className="flex items-center gap-2 text-sm text-slate-600">
                        정렬
                        <select
                          value={sort}
                          onChange={(event) => {
                            setSort(event.target.value)
                            setPage(1)
                          }}
                          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-slate-900"
                        >
                          {SORT_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    {searchMeta && (
                      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-500">
                        <span className="inline-flex items-center gap-1.5">
                          <Globe className="h-4 w-4" />
                          {searchMeta.siteCount}개 사이트 검색 완료
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <Clock className="h-4 w-4" />
                          검색 시간: {(searchMeta.elapsedMs / 1000).toFixed(1)}초
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <Layers className="h-4 w-4" />
                          중복 제거: {searchMeta.duplicatesRemoved}건
                        </span>
                      </div>
                    )}

                    <CollectorStatus sources={collectorStatuses} />
                  </div>
                )}

                <CollectorErrors sources={collectorStatuses} />

                {!hasSearched ? (
                  <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
                    <p className="text-4xl">🔍</p>
                    <p className="mt-3 font-semibold text-slate-900">키워드를 입력하고 검색해 보세요</p>
                    <p className="mt-1 text-sm text-slate-500">
                      예: 베트남어 · 외국인 · 베트남어 통역
                    </p>
                  </div>
                ) : jobs.length === 0 && !loadingList ? (
                  <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
                    <SearchX className="mx-auto h-10 w-10 text-slate-300" />
                    <p className="mt-3 font-semibold text-slate-900">조건에 맞는 공고가 없습니다</p>
                    <p className="mt-1 text-sm text-slate-500">필터를 줄이거나 다른 키워드로 검색해 보세요.</p>
                  </div>
                ) : (
                  <div className={`space-y-3 ${loadingList ? 'opacity-50' : ''}`}>
                    {jobs.map((job) => (
                      <JobCard key={job.id} job={job} sourceLabels={sourceLabels} />
                    ))}
                  </div>
                )}

                <Pagination
                  page={pagination?.page ?? 1}
                  totalPages={pagination?.total_pages ?? 0}
                  onChange={(next) => {
                    setPage(next)
                    window.scrollTo({ top: 0, behavior: 'smooth' })
                  }}
                />
              </>
            )}
          </section>
        </div>
      </main>

      <footer className="mx-auto max-w-7xl px-4 pb-10 text-center text-xs text-slate-400 sm:px-6">
        Korea Job Finder · 공고 원문의 권리는 각 채용 사이트에 있습니다.
      </footer>
    </div>
  )
}
