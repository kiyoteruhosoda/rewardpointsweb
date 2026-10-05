/**
 * 表示端末（サイネージ）の API（ADR-0047）。
 *
 * 端末の側（認証なし）: ペアリングを始める・受け取る。資格情報からアクセストークンへの
 * 取り直しは `api.ts` の `openDisplaySession`（401 の取り直しと同じ入口に置くため）。
 *
 * 運用管理者の側（`display:approve`）: 承認する・映す家族を選ぶ・一覧・外す。
 */
import { ApiError, api } from './api'

export interface StartedPairing {
  /** 画面に出す確認コード（`KQ7M-3XPA`） */
  user_code: string
  /** 端末だけが知る秘密。画面には出さない */
  device_code: string
  expires_in: number
  /** 受け取りを問い合わせる間隔（秒） */
  interval: number
  /** 承認の画面を指す QR コード（SVG の data URI）。 */
  qr_code: string | null
}

export interface DisplayDevice {
  account_id: number
  family_id: number
  family_name: string
  name: string
  created_at: string
  /** 受け取る前なら null */
  last_used_at: string | null
}

export interface DisplayableFamily {
  id: number
  name: string
}

/** 受け取りの問い合わせの結果。 */
export type ClaimOutcome =
  | { kind: 'claimed'; credential: string }
  | { kind: 'pending' }
  /** 期限切れ・受け取り済み。ペアリングをやり直す */
  | { kind: 'expired' }

/** 承認の画面のパス。QR コードもここを指す（確認コードは `#` の後ろ）。 */
export const APPROVE_PATH = '/admin/displays/approve'

export function startPairing(origin: string): Promise<StartedPairing> {
  return api.post<StartedPairing>('/api/display/pairings', { origin })
}

export async function claimPairing(deviceCode: string): Promise<ClaimOutcome> {
  try {
    const claimed = await api.post<{ device_credential: string }>('/api/display/pairings/claim', {
      device_code: deviceCode,
    })
    return { kind: 'claimed', credential: claimed.device_credential }
  } catch (error) {
    if (error instanceof ApiError && error.code === 'authorization_pending')
      return { kind: 'pending' }
    if (error instanceof ApiError && error.code === 'expired_token') return { kind: 'expired' }
    throw error
  }
}

export function approvePairing(body: {
  user_code: string
  family_id: number
  name: string
}): Promise<DisplayDevice> {
  return api.post<DisplayDevice>('/api/display/pairings/approve', body)
}

export function listDisplayableFamilies(): Promise<DisplayableFamily[]> {
  return api.get<DisplayableFamily[]>('/api/display/families')
}

export function listDisplayDevices(): Promise<DisplayDevice[]> {
  return api.get<DisplayDevice[]>('/api/display/devices')
}

export function removeDisplayDevice(accountId: number): Promise<void> {
  return api.delete<void>(`/api/display/devices/${accountId}`)
}

/** ログインの往復のあいだ、承認の画面へ戻るための確認コードを預ける場所（同じタブ限り）。 */
const PENDING_APPROVAL_KEY = 'pendingDisplayApproval'

/**
 * 未ログインで承認の画面（QR コード）を開いたとき、確認コードを預ける。
 *
 * SSO は IdP の画面を挟むので `#` が失われる。招待コードと同じく、クエリへは移さず
 * `sessionStorage` に預ける（`invitationLink.ts` と同じ理由）。
 */
export function rememberPendingApproval(hash: string): void {
  sessionStorage.setItem(PENDING_APPROVAL_KEY, hash)
}

/** 預けた承認の行き先を取り出す（1 度だけ）。無ければ null。 */
export function takePendingApproval(): string | null {
  const hash = sessionStorage.getItem(PENDING_APPROVAL_KEY)
  if (hash === null) return null
  sessionStorage.removeItem(PENDING_APPROVAL_KEY)
  return `${APPROVE_PATH}${hash}`
}

/** QR コード・リンクで渡された確認コード（`#KQ7M-3XPA`）を読む。無ければ空文字。 */
export function userCodeFromHash(hash: string): string {
  return decodeURIComponent(hash.replace(/^#/, '')).trim()
}
