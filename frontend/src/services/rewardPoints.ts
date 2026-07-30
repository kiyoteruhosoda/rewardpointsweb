/**
 * ポイント API のクライアント。
 *
 * 画面が組み立てるのは表示だけで、パスとレスポンスの形はここに集める。
 * `access_level` はサーバーが決めた「そのメンバーへ触れる範囲」で、画面は変更 UI
 * の出し分けにこれを使う（役割名では判断しない）。
 */
import { api } from './api'

export type AccessLevel = 'view' | 'manage'
export type PointEntryType = 'addition' | 'consumption'

export interface MemberSummary {
  id: number
  name: string
  balance: number
  access_level: AccessLevel
  is_self: boolean
  has_linked_user: boolean
}

export interface Member {
  id: number
  name: string
  balance: number
  access_level: AccessLevel
  is_self: boolean
  linked_user_email: string | null
}

export interface PointEntry {
  id: number
  entry_type: PointEntryType
  occurred_at: string
  points: number
  signed_points: number
  description: string
}

export interface PointLedger {
  member_id: number
  member_name: string
  balance: number
  access_level: AccessLevel
  entries: PointEntry[]
}

export interface MemberShare {
  user_id: number
  email: string
  username: string
  access_level: AccessLevel
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

export const rewardPoints = {
  listMembers: () => api.get<MemberSummary[]>('/api/members'),

  createMember: (name: string, linkedUserEmail: string | null) =>
    api.post<Member>('/api/members', { name, linked_user_email: linkedUserEmail }),

  deleteMember: (memberId: number) => api.delete<undefined>(`/api/members/${memberId}`),

  viewPoints: (memberId: number) => api.get<PointLedger>(`/api/members/${memberId}/points`),

  addPoints: (memberId: number, points: number, reason: string) =>
    api.post<PointEntry>(`/api/members/${memberId}/points/additions`, { points, reason }),

  consumePoints: (memberId: number, points: number, application: string) =>
    api.post<PointEntry>(`/api/members/${memberId}/points/consumptions`, {
      points,
      application,
    }),

  deleteEntry: (memberId: number, entryId: number) =>
    api.delete<undefined>(`/api/members/${memberId}/points/${entryId}`),

  listShares: (memberId: number) => api.get<MemberShare[]>(`/api/members/${memberId}/shares`),

  shareMember: (memberId: number, email: string, accessLevel: AccessLevel) =>
    api.post<MemberShare>(`/api/members/${memberId}/shares`, {
      email,
      access_level: accessLevel,
    }),

  revokeShare: (memberId: number, targetUserId: number) =>
    api.delete<undefined>(`/api/members/${memberId}/shares/${targetUserId}`),
}
