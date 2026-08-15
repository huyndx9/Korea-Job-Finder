import { useState } from 'react'
import { X, FlaskConical, Save, Loader2, CheckCircle2, AlertTriangle, Wand2 } from 'lucide-react'

import { createCustomSource, testCustomSource } from '../api'

const EMPTY = {
  name: '',
  label: '',
  kind: 'html',
  site_url: '',
  search_url: '',
  item_selector: '',
  title_selector: '',
  company_selector: '',
  location_selector: '',
  salary_selector: '',
  date_selector: '',
  description_selector: '',
  link_selector: '',
  link_template: '',
  enabled: true,
}

// A real, working configuration — press "예시 채우기" to see the shape of each field.
const EXAMPLE = {
  ...EMPTY,
  name: 'incruit-manual',
  label: '인크루트 (직접 추가)',
  kind: 'html',
  site_url: 'https://job.incruit.com',
  search_url: 'https://job.incruit.com/jobdb_list/searchjob.asp?kw={keyword}',
  item_selector: 'ul.c_row',
  title_selector: 'a[href*="jobdb_info"]',
  company_selector: '.cell_first a',
  link_selector: 'a[href*="jobdb_info"]',
  description_selector: 'div.cell_mid',
}

const HTML_FIELDS = [
  ['item_selector', '공고 선택자 *', '공고 하나를 감싸는 요소 (예: ul.c_row)', true],
  ['title_selector', '제목 선택자 *', '예: a[href*="jobdb_info"]', true],
  ['link_selector', '링크 선택자', '비우면 항목 안의 첫 <a> 를 사용', false],
  ['company_selector', '회사명 선택자', '예: .cell_first a', false],
  ['location_selector', '지역 선택자', '비우면 본문에서 추측', false],
  ['salary_selector', '급여 선택자', '비우면 본문에서 추측', false],
  ['date_selector', '등록일 선택자', '예: .date', false],
  ['description_selector', '설명 선택자', '예: div.cell_mid', false],
]

const JSON_FIELDS = [
  ['item_selector', '목록 경로 *', '공고 배열까지의 경로 (예: result.positions)', true],
  ['title_selector', '제목 경로 *', '예: title', true],
  ['link_selector', '링크/ID 경로', '예: id 또는 url', false],
  ['link_template', '링크 템플릿', '예: https://site.com/jobs/{value}', false],
  ['company_selector', '회사명 경로', '예: companyName', false],
  ['location_selector', '지역 경로', '예: address.location', false],
  ['salary_selector', '급여 경로', '예: salary.name', false],
  ['date_selector', '등록일 경로', '예: created_at', false],
  ['description_selector', '설명 경로', '예: category', false],
]

function Field({ name, label, hint, required, value, onChange }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        type="text"
        value={value}
        required={required}
        onChange={(event) => onChange(name, event.target.value)}
        placeholder={hint}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-slate-900"
      />
    </label>
  )
}

export default function AddSourceModal({ open, onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY)
  const [keyword, setKeyword] = useState('베트남어')
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  if (!open) return null

  const fields = form.kind === 'json' ? JSON_FIELDS : HTML_FIELDS
  const canSubmit = form.name && form.label && form.search_url && form.item_selector

  function update(name, value) {
    setForm((current) => ({ ...current, [name]: value }))
    setResult(null)
  }

  function close() {
    setForm(EMPTY)
    setResult(null)
    setError(null)
    onClose()
  }

  async function handleTest() {
    setTesting(true)
    setError(null)
    try {
      setResult(await testCustomSource({ ...form, keyword }))
    } catch (err) {
      setError(err.message)
      setResult(null)
    } finally {
      setTesting(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      await createCustomSource(form)
      onSaved(form.name)
      close()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm">
      <div className="my-8 w-full max-w-3xl rounded-2xl bg-white shadow-xl">
        <header className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">채용 사이트 직접 추가</h2>
            <p className="text-sm text-slate-500">
              코드 수정 없이 채용 사이트를 직접 등록합니다
            </p>
          </div>
          <button onClick={close} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="space-y-5 px-6 py-5">
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3">
            <p className="text-sm text-slate-600">
              처음이라면 예시를 채워 넣고 <strong>테스트</strong>를 눌러보세요.
            </p>
            <button
              onClick={() => {
                setForm(EXAMPLE)
                setResult(null)
              }}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:border-slate-900"
            >
              <Wand2 className="h-4 w-4" />
              예시 채우기
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field name="name" label="ID (영문 소문자) *" hint="mysite" required value={form.name} onChange={update} />
            <Field name="label" label="표시 이름 *" hint="마이사이트" required value={form.label} onChange={update} />
          </div>

          <div>
            <span className="text-sm font-medium text-slate-700">유형</span>
            <div className="mt-1 flex gap-2">
              {[
                ['html', 'HTML 페이지 (CSS 선택자)'],
                ['json', 'JSON API (경로)'],
              ].map(([value, text]) => (
                <button
                  key={value}
                  onClick={() => update('kind', value)}
                  className={`rounded-lg border px-3.5 py-2 text-sm transition ${
                    form.kind === value
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-200 text-slate-600 hover:border-slate-400'
                  }`}
                >
                  {text}
                </button>
              ))}
            </div>
          </div>

          <Field
            name="search_url"
            label="검색 URL *  —  {keyword} 자리에 검색어가 들어갑니다"
            hint="https://example.com/jobs?q={keyword}"
            required
            value={form.search_url}
            onChange={update}
          />
          <Field name="site_url" label="사이트 주소" hint="https://example.com" value={form.site_url} onChange={update} />

          <div className="grid gap-4 sm:grid-cols-2">
            {fields.map(([name, label, hint, required]) => (
              <Field
                key={name}
                name={name}
                label={label}
                hint={hint}
                required={required}
                value={form[name]}
                onChange={update}
              />
            ))}
          </div>

          <div className="rounded-xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex-1">
                <span className="text-sm font-medium text-slate-700">테스트 검색어</span>
                <input
                  type="text"
                  value={keyword}
                  onChange={(event) => setKeyword(event.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
                />
              </label>
              <button
                onClick={handleTest}
                disabled={testing || !canSubmit}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-900 disabled:opacity-40"
              >
                {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
                테스트
              </button>
            </div>

            {result && (
              <div
                className={`mt-3 rounded-lg border px-3 py-2.5 text-sm ${
                  result.ok ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-900'
                }`}
              >
                <p className="flex items-center gap-1.5 font-medium">
                  {result.ok ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                  {result.message}
                </p>
                <p className="mt-1 text-xs opacity-70">
                  항목 {result.items_found}개 발견 · 공고 {result.jobs_parsed}개 해석 · {result.requested_url}
                </p>
                {result.jobs?.length > 0 && (
                  <ul className="mt-2 space-y-1.5 border-t border-current/10 pt-2">
                    {result.jobs.map((job, index) => (
                      <li key={index} className="text-xs">
                        <strong>{job.title}</strong>
                        <span className="opacity-70">
                          {' '}
                          · {job.company}
                          {job.location ? ` · ${job.location}` : ''}
                          {job.employment_type ? ` · ${job.employment_type}` : ''}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          {error && (
            <p className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              {error}
            </p>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 px-6 py-4">
          <button onClick={close} className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !canSubmit}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:bg-slate-300"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            저장
          </button>
        </footer>
      </div>
    </div>
  )
}
