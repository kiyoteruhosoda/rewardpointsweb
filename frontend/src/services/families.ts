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
  /**
   * 見ている人がこの参加者に対して行える操作。
   *
   * 立場から画面が組み立て直すと、サーバーが断る操作まで出てしまう（記録の
   * 残る子の「削除」など）。出し分けはこの 3 つだけを見て決める。
   */
  can_reset_password: boolean
  /** 独立の指示 — アカウントのある子だけ。ADR-0014 */
  can_propose_independence: boolean
  /** 削除 — owner だけ、自分以外、台帳に記録が無いとき */
  can_remove: boolean
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
  /** 訂正後のレコードなら、言い直した相手の ID（ADR-0022）。 */
  corrects_id: number | null
  /** このレコードが打ち消されているか。 */
  is_reversed: boolean
  granted_by: string | null
}

/** 1 回の訂正で台帳に足された 2 行。元のレコードは履歴に残る（ADR-0022）。 */
export interface Correction {
  reversal: Transaction
  correction: Transaction
}

/**
 * 毎日のボーナスの設定（ADR-0024）。
 *
 * 決めておくと、日付が変わるたびにこの量が台帳へ 1 行足される。足すのはサーバー
 * 側の定期実行で、画面は決めるだけ。
 */
export interface DailyBonus {
  ledger_id: number
  /** 毎日足す量（正の数のみ）。 */
  amount: number
  reason: string
  /** 最初に渡す日（決めた日の翌日）。これより前へは遡らない。 */
  starts_on: string
  /** 渡し終えた最後の日。まだ 1 日も渡していなければ null。 */
  granted_through: string | null
}

export interface Ledger {
  ledger_id: number
  family_id: number
  membership_id: number
  display_name: string
  balance: number
  can_modify: boolean
  transactions: Transaction[]
  /** 決めていなければ null。 */
  daily_bonus: DailyBonus | null
}

/**
 * 家族まるごとの控え（バックアップ。ADR-0025）。
 *
 * 書き出しの応答であり、取り込みの本文でもある。同じ形を両方向で使うので、
 * 保存した JSON をそのまま送り返せば元に戻る。
 *
 * 行どうしの繋がり（誰が記録したか・どの記録の打ち消しか）は、DB の ID ではなく
 * ファイルの中だけで通じる `ref` で表す。復元先では ID が全部変わるため。
 *
 * **アカウントは入らない。** ログイン ID もパスワードも招待コードも載らないので、
 * 控えを持ち出しても誰かのアカウントには届かない。
 */
export interface ArchivedTransaction {
  ref: string
  amount: number
  reason: string
  occurred_at: string
  /** 記録した参加者の ref。毎日のボーナスと、家族を離れた人の行では null。 */
  granted_by: string | null
  reverses: string | null
  corrects: string | null
}

export interface ArchivedDailyBonus {
  amount: number
  reason: string
  starts_on: string
  granted_through: string | null
}

export interface ArchivedLedger {
  /** 書いた順（古い行が先）。 */
  transactions: ArchivedTransaction[]
  daily_bonus: ArchivedDailyBonus | null
}

export interface ArchivedMember {
  ref: string
  display_name: string
  role: FamilyRole
  /** 台帳を持つのは role = child だけ。 */
  ledger: ArchivedLedger | null
}

export interface FamilyArchive {
  format: string
  version: number
  exported_at: string
  family_name: string
  members: ArchivedMember[]
}

/** 取り込みの結果。戻った量を人が確かめられるように数が返る。 */
export interface ImportedFamily {
  family_id: number
  name: string
  member_count: number
  transaction_count: number
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

  /**
   * 家族まるごとを控えとして受け取る（親のみ。ADR-0025）。
   *
   * 子どもの台帳と履歴が全部入る。保存の仕方は `familyArchiveFile.ts`。
   */
  exportArchive: (familyId: number) => api.get<FamilyArchive>(`/api/families/${familyId}/export`),

  /**
   * 控えから家族を作り直す（復元）。作られるのは **新しい家族** で、呼んだ人が
   * owner になる。どこかに所属したままでは呼べない（ADR-0013）。
   */
  importArchive: (archive: FamilyArchive) =>
    api.post<ImportedFamily>('/api/families/import', archive),

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

  /** 子を並べる順を決める（親メンバー）。並びは家族に 1 つで、誰が見ても同じ。 */
  reorderMembers: (familyId: number, membershipIds: number[]) =>
    api.put<FamilyDetail>(`/api/families/${familyId}/member-order`, {
      membership_ids: membershipIds,
    }),

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

  /**
   * 入力の間違いを直す。元のレコードは書き換わらず、打ち消しと正しい内容の
   * 2 行が足される（ADR-0022）。発生日時は元のレコードから引き継ぐ。
   */
  correct: (
    familyId: number,
    ledgerId: number,
    transactionId: number,
    entry: NewTransaction,
  ): Promise<Correction> =>
    api.post<Correction>(
      `${ledgerPath(familyId, ledgerId)}/transactions/${transactionId}/corrections`,
      {
        amount: entry.amount,
        reason: entry.reason,
        idempotency_key: entry.idempotencyKey,
      },
    ),

  /**
   * 毎日のボーナスを決める（すでに決まっていれば書き換える。ADR-0024）。
   *
   * 決めた時点では台帳は動かない。最初の 1 行が入るのは次に日付が変わったとき。
   */
  setDailyBonus: (familyId: number, ledgerId: number, amount: number, reason: string) =>
    api.put<DailyBonus>(`${ledgerPath(familyId, ledgerId)}/daily-bonus`, { amount, reason }),

  /** やめる。すでに渡したポイントはそのまま残る。 */
  stopDailyBonus: (familyId: number, ledgerId: number) =>
    api.delete<undefined>(`${ledgerPath(familyId, ledgerId)}/daily-bonus`),
}
