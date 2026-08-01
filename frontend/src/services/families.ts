/**
 * 家族・台帳 API のクライアント。
 *
 * 画面が組み立てるのは表示だけで、パスとレスポンスの形はここに集める。
 * 「変更 UI を出すか」はサーバーが返す `can_modify` で決める（立場の名前では
 * 判断しない）。
 */
import { api, type Fetched } from './api'

export type FamilyRole = 'owner' | 'parent' | 'child'

export interface Membership {
  id: number
  display_name: string
  role: FamilyRole
  /** アカウントと結び付いているか。偽なら本人はまだログインできない。 */
  is_linked: boolean
  is_me: boolean
  username: string | null
  /** 台帳を持つのは role = child だけ。見えない相手のものは null。 */
  ledger_id: number | null
  balance: number | null
  /** 親から独立の指示が出ているか（ADR-0014）。子本人の承認で成立する。 */
  independence_proposed: boolean
}

export interface FamilySummary {
  id: number
  name: string
  my_membership_id: number
  my_role: FamilyRole
  member_count: number
}

export interface FamilyDetail {
  id: number
  name: string
  my_membership_id: number
  my_role: FamilyRole
  memberships: Membership[]
}

export interface Invitation {
  id: number
  role: FamilyRole
  target_membership_id: number | null
  target_display_name: string | null
  expires_at: string
  /** 平文のコードは発行の応答でだけ返る。一覧では常に null。 */
  code: string | null
}

export interface RedeemedInvitation {
  family_id: number
  family_name: string
  membership_id: number
  role: FamilyRole
  username: string
}

export interface TemporaryPassword {
  membership_id: number
  username: string
  password: string
  expires_at: string
}

export interface Transaction {
  id: number
  /** 符号付き。加算は正、消費は負。 */
  amount: number
  reason: string
  occurred_at: string
  created_at: string
  /** 打ち消しレコードなら、打ち消した相手の ID。 */
  reversal_of_id: number | null
  /** このレコードが打ち消されているか。 */
  is_reversed: boolean
  granted_by: string | null
}

export interface Ledger {
  ledger_id: number
  family_id: number
  membership_id: number
  display_name: string
  balance: number
  can_modify: boolean
  transactions: Transaction[]
}

/**
 * サーバーの時刻は UTC だが、タイムゾーンの接尾辞は付かない
 * （`2026-07-30T08:54:13`）。JavaScript はそれを **ローカル時刻** として解釈する
 * ため、そのまま `new Date()` に渡すと時差の分だけずれて表示される。
 */
export function parseUtc(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

/**
 * 冪等キー。送信ボタンを二度押ししても台帳に 2 行入らないよう、1 回の記録に
 * 1 つ発行して同じ値で再送する（ADR-0010）。
 */
export function newIdempotencyKey(): string {
  return crypto.randomUUID()
}

export interface NewTransaction {
  amount: number
  reason: string
  idempotencyKey: string
}

const ledgerPath = (familyId: number, ledgerId: number) =>
  `/api/families/${familyId}/ledgers/${ledgerId}`

export const families = {
  list: () => api.get<FamilySummary[]>('/api/families'),

  create: (name: string) => api.post<FamilyDetail>('/api/families', { name }),

  view: (familyId: number) => api.get<FamilyDetail>(`/api/families/${familyId}`),

  rename: (familyId: number, name: string) =>
    api.patch<FamilyDetail>(`/api/families/${familyId}`, { name }),

  /** 家族から抜ける（親のみ。他にアカウントの結び付いた親が残る場合に限る）。 */
  leave: (familyId: number) => api.post<undefined>(`/api/families/${familyId}/leave`),

  /** 家族を解散する（owner のみ。自分以外の参加者がいないこと）。 */
  dissolve: (familyId: number) => api.delete<undefined>(`/api/families/${familyId}`),

  /** 子の独立を指示する（親メンバー）。子本人の承認までは取り下げられる（ADR-0014）。 */
  proposeIndependence: (familyId: number, membershipId: number) =>
    api.post<Membership>(
      `/api/families/${familyId}/memberships/${membershipId}/independence-proposal`,
    ),

  revokeIndependenceProposal: (familyId: number, membershipId: number) =>
    api.delete<undefined>(
      `/api/families/${familyId}/memberships/${membershipId}/independence-proposal`,
    ),

  /** 独立を承認する（指示を受けた子本人）。成立すると台帳ごと家族から消える。 */
  approveIndependence: (familyId: number) =>
    api.post<undefined>(`/api/families/${familyId}/independence`),

  addChild: (familyId: number, displayName: string) =>
    api.post<Membership>(`/api/families/${familyId}/memberships`, { display_name: displayName }),

  removeMembership: (familyId: number, membershipId: number) =>
    api.delete<undefined>(`/api/families/${familyId}/memberships/${membershipId}`),

  resetChildPassword: (familyId: number, membershipId: number) =>
    api.post<TemporaryPassword>(
      `/api/families/${familyId}/memberships/${membershipId}/password-reset`,
    ),

  listInvitations: (familyId: number) =>
    api.get<Invitation[]>(`/api/families/${familyId}/invitations`),

  issueInvitation: (familyId: number, role: FamilyRole, targetMembershipId: number | null) =>
    api.post<Invitation>(`/api/families/${familyId}/invitations`, {
      role,
      target_membership_id: targetMembershipId,
    }),

  revokeInvitation: (familyId: number, invitationId: number) =>
    api.delete<undefined>(`/api/families/${familyId}/invitations/${invitationId}`),

  acceptInvitation: (code: string, displayName: string | null) =>
    api.post<RedeemedInvitation>('/api/families/invitations/accept', {
      code,
      display_name: displayName,
    }),

  /** 未認証で呼ぶ。招待コードと引き換えにアカウントを作る（ADR-0011）。 */
  redeemInvitation: (code: string, username: string, password: string, displayName: string) =>
    api.post<RedeemedInvitation>('/api/families/invitations/redeem', {
      code,
      username,
      password,
      display_name: displayName,
    }),

  /** その家族でよく使われている理由（入力候補）。頻度の高い順。 */
  reasonSuggestions: (familyId: number) =>
    api.get<string[]>(`/api/families/${familyId}/reason-suggestions`),

  /** 取得時刻付き。オフラインではキャッシュが返り、時刻がその古さを示す（ADR-0015）。 */
  viewLedger: (familyId: number, ledgerId: number): Promise<Fetched<Ledger>> =>
    api.getFetched<Ledger>(ledgerPath(familyId, ledgerId)),

  record: (familyId: number, ledgerId: number, entry: NewTransaction) =>
    api.post<Transaction>(`${ledgerPath(familyId, ledgerId)}/transactions`, {
      amount: entry.amount,
      reason: entry.reason,
      idempotency_key: entry.idempotencyKey,
    }),

  reverse: (familyId: number, ledgerId: number, transactionId: number, idempotencyKey: string) =>
    api.post<Transaction>(
      `${ledgerPath(familyId, ledgerId)}/transactions/${transactionId}/reversals`,
      { idempotency_key: idempotencyKey },
    ),
}
