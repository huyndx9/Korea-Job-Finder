// One place that decides how every source status is worded and coloured,
// shared by the source picker and the post-search status strip.
import { Check, X, AlertTriangle, Clock, FlaskConical, KeyRound, Ban, Timer, Minus } from 'lucide-react'

export const STATUS_META = {
  connected: { icon: Check, tone: 'ok', label: '연결됨', hint: 'API 정상' },
  idle: { icon: Minus, tone: 'muted', label: '대기', hint: '아직 검색하지 않음' },
  demo: { icon: FlaskConical, tone: 'warn', label: 'DEMO', hint: '샘플 데이터 (실제 공고 아님)' },
  not_configured: { icon: KeyRound, tone: 'warn', label: 'API 키 필요', hint: '.env에 API 키를 설정하세요' },
  invalid_key: { icon: KeyRound, tone: 'bad', label: 'API 키 오류', hint: 'API 키가 유효하지 않습니다' },
  invalid_request: { icon: AlertTriangle, tone: 'bad', label: '요청 오류', hint: '요청 파라미터가 잘못되었습니다' },
  rate_limited: { icon: Timer, tone: 'bad', label: '호출 한도 초과', hint: '일일 API 호출 한도를 초과했습니다' },
  api_error: { icon: X, tone: 'bad', label: 'API 오류', hint: '채용 사이트 API가 오류를 반환했습니다' },
  error: { icon: X, tone: 'bad', label: '오류', hint: '요청에 실패했습니다' },
  timeout: { icon: Clock, tone: 'bad', label: '시간 초과', hint: '응답이 너무 늦습니다' },
  unavailable: { icon: Ban, tone: 'muted', label: '수집 불가', hint: '공개 수집이 불가능한 사이트입니다' },
}

export const TONE_TEXT = {
  ok: 'text-emerald-600',
  warn: 'text-amber-600',
  bad: 'text-rose-600',
  muted: 'text-slate-400',
}

export function statusMeta(status) {
  return STATUS_META[status] ?? STATUS_META.error
}
