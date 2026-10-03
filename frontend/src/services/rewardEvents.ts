/**
 * イベント（がんばりカード。ADR-0042）の API クライアント。
 *
 * 目標・達成でもらえるポイント・達成回数を決めて作り、1 回達成するたびにシールを
 * 1 枚貼る。マスが全部埋まると、サーバーが台帳へ達成のポイントを 1 行足す。
 *
 * シールは **番号つき** で貼る。送るのは「次に貼る番号」で、同じ番号を 2 度送っても
 * 1 枚にしかならない（二重タップ・通信の再送で 2 枚にならない）。
 */
import { api } from './api'

export interface Sticker {
  /** 1 から始まる通し番号。 */
  number: number
  stuck_at: string
}

export interface RewardEvent {
  id: number
  ledger_id: number
  /** 目標。達成したときの台帳の理由にもなる。 */
  title: string
  reward_points: number
  /** 達成回数（＝マスの数）。 */
  goal_count: number
  /** 番号の小さい順。 */
  stickers: Sticker[]
  /** マスが埋まった日時。まだなら null。 */
  completed_at: string | null
  created_at: string
  /** この日のうちに埋めれば達成（YYYY-MM-DD）。決めていなければ null。ADR-0043 */
  deadline: string | null
  /** 期限を過ぎても埋まっていない。判定はサーバー（家族の 1 日の区切り）。 */
  is_expired: boolean
}

export interface RewardEventBoard {
  ledger_id: number
  display_name: string
  /** 作る・貼る・はがす・消すの入口を出すか。 */
  can_modify: boolean
  /** 作った順。 */
  events: RewardEvent[]
}

export interface NewRewardEvent {
  title: string
  reward_points: number
  goal_count: number
  /** YYYY-MM-DD。null で期限なし。 */
  deadline: string | null
}

/** 達成回数の上限（サーバーの MAX_GOAL_COUNT と同じ）。 */
export const MAX_GOAL_COUNT = 50

/** 目標の長さの上限（サーバーの TITLE_MAX_LENGTH と同じ）。 */
export const TITLE_MAX_LENGTH = 100

const eventsPath = (familyId: number, ledgerId: number) =>
  `/api/families/${familyId}/ledgers/${ledgerId}/events`

const stickerPath = (familyId: number, ledgerId: number, eventId: number, number: number) =>
  `${eventsPath(familyId, ledgerId)}/${eventId}/stickers/${number}`

export const rewardEvents = {
  board: (familyId: number, ledgerId: number) =>
    api.get<RewardEventBoard>(eventsPath(familyId, ledgerId)),

  create: (familyId: number, ledgerId: number, event: NewRewardEvent) =>
    api.post<RewardEvent>(eventsPath(familyId, ledgerId), event),

  /** *number* 枚目を貼る。最後のマスならポイントが台帳に入る。 */
  stick: (familyId: number, ledgerId: number, eventId: number, number: number) =>
    api.put<RewardEvent>(stickerPath(familyId, ledgerId, eventId, number)),

  /** 期限を決め直す（null で期限なし）。期限切れのカードも、延ばせばまた貼れる。 */
  changeDeadline: (familyId: number, ledgerId: number, eventId: number, deadline: string | null) =>
    api.put<RewardEvent>(`${eventsPath(familyId, ledgerId)}/${eventId}/deadline`, { deadline }),

  /** 最後の 1 枚をはがす（押し間違いを戻す）。達成した後ははがせない。 */
  peel: (familyId: number, ledgerId: number, eventId: number, number: number) =>
    api.delete<RewardEvent>(stickerPath(familyId, ledgerId, eventId, number)),

  /** 消す。達成で足したポイントは台帳に残る。 */
  remove: (familyId: number, ledgerId: number, eventId: number) =>
    api.delete<undefined>(`${eventsPath(familyId, ledgerId)}/${eventId}`),
}
