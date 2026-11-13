/**
 * Client for the family and ledger APIs.
 *
 * Screens only build the presentation; paths and response shapes are collected here.
 * "Whether to show modification UI" is decided by the server-returned `can_modify` (not by
 * role names).
 */
import { api, type Fetched } from './api'

/** `display` is not a person but a display device (signage, ADR-0047). */
export type FamilyRole = 'owner' | 'parent' | 'child' | 'display'

export interface Membership {
  id: number
  display_name: string
  role: FamilyRole
  /** Whether linked to an account. If false, the person cannot sign in yet. */
  is_linked: boolean
  is_me: boolean
  username: string | null
  /** Only role = child has a ledger. null for people the viewer cannot see. */
  ledger_id: number | null
  balance: number | null
  /**
   * Daily bonus setting (ADR-0024). null if not set.
   *
   * It is set on the family settings screen (ADR-0027). The amount differs per child, so
   * it is carried per participant rather than per family.
   */
  daily_bonus: DailyBonus | null
  /** Whether a parent has requested independence (ADR-0014). Done once the child approves. */
  independence_proposed: boolean
  /**
   * Actions the viewer can perform on this participant.
   *
   * If the screen rebuilt these from roles, it would show actions the server refuses (e.g.
   * "delete" for a child with records). Gating is decided by these 3 alone.
   */
  can_reset_password: boolean
  /** Independence request — only children with an account. ADR-0014 */
  can_propose_independence: boolean
  /** Delete — owner only, not self, and only when the ledger has no records */
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
  /** The family's agreed rules (ADR-0027). null if not written yet. */
  rules: string | null
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
  /** The plaintext code is returned only in the issue response. Always null in listings. */
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
  /** Signed. Additions are positive, spending negative. */
  amount: number
  reason: string
  occurred_at: string
  created_at: string
  /** For a reversal record, the ID of the record it reverses. */
  reversal_of_id: number | null
  /** For a corrected record, the ID of the record it restates (ADR-0022). */
  corrects_id: number | null
  /** Whether this record has been reversed. */
  is_reversed: boolean
  granted_by: string | null
}

/** The 2 rows added to the ledger by one correction. The original stays in history (ADR-0022). */
export interface Correction {
  reversal: Transaction
  correction: Transaction
}

/**
 * Daily bonus setting (ADR-0024).
 *
 * Once set, this amount is added to the ledger as one row each time the date changes. The
 * server's scheduled job adds it; the screen only sets it.
 */
export interface DailyBonus {
  ledger_id: number
  /** Amount added each day (positive only). */
  amount: number
  reason: string
  /** First day to grant (the day after it was set). Never goes back before it. */
  starts_on: string
  /** Last day granted. null if none granted yet. */
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
  /** null if not set. */
  daily_bonus: DailyBonus | null
}

/**
 * Backup of the whole family (ADR-0026).
 *
 * Both the export response and the import body. The same shape is used both ways, so
 * sending the saved JSON back as is restores it.
 *
 * Links between rows (who recorded, which record a reversal targets) use `ref`, valid only
 * inside the file rather than DB IDs, because all IDs change at the restore target.
 *
 * **Accounts are not included.** No login IDs, passwords or invitation codes are included, so
 * taking the backup elsewhere does not reach anyone's account.
 */
export interface ArchivedTransaction {
  ref: string
  amount: number
  reason: string
  occurred_at: string
  /** ref of the participant who recorded. null for daily bonus rows and people who left. */
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
  /** Written order (oldest first). */
  transactions: ArchivedTransaction[]
  daily_bonus: ArchivedDailyBonus | null
}

export interface ArchivedMember {
  ref: string
  display_name: string
  role: FamilyRole
  /** Only role = child has a ledger. */
  ledger: ArchivedLedger | null
}

export interface FamilyArchive {
  format: string
  version: number
  exported_at: string
  family_name: string
  /** The family's agreed rules (ADR-0027). Not present in version 1 backups. */
  family_rules?: string | null
  members: ArchivedMember[]
}

/** Import result. Counts are returned so a person can check how much was restored. */
export interface ImportedFamily {
  family_id: number
  name: string
  member_count: number
  transaction_count: number
}

/**
 * Server times are UTC but carry no time zone suffix
 * (`2026-07-30T08:54:13`). JavaScript parses that as **local time**,
 * so passing it to `new Date()` as is shows it shifted by the offset.
 */
export function parseUtc(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

/**
 * Idempotency key. Issue one per record and resend with the same value, so a double tap
 * on submit does not add 2 rows to the ledger (ADR-0010).
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
   * Rewrite the family's agreed rules (parent members, ADR-0027).
   *
   * Sending an empty string clears them (the server turns it into null).
   */
  setRules: (familyId: number, rules: string) =>
    api.put<FamilyDetail>(`/api/families/${familyId}/rules`, { rules }),

  /**
   * Receive the whole family as a backup (parents only, ADR-0026).
   *
   * Contains all children's ledgers and history. Saving is handled by `familyArchiveFile.ts`.
   */
  exportArchive: (familyId: number) => api.get<FamilyArchive>(`/api/families/${familyId}/export`),

  /**
   * Recreate a family from a backup (restore). It creates a **new family**, and the caller
   * becomes owner. Cannot be called while belonging to a family (ADR-0013).
   */
  importArchive: (archive: FamilyArchive) =>
    api.post<ImportedFamily>('/api/families/import', archive),

  /** Leave the family (parents only; only if another parent linked to an account remains). */
  leave: (familyId: number) => api.post<undefined>(`/api/families/${familyId}/leave`),

  /** Dissolve the family (owner only; no participants other than self). */
  dissolve: (familyId: number) => api.delete<undefined>(`/api/families/${familyId}`),

  /** Request a child's independence (parent members). Withdrawable until the child approves (ADR-0014). */
  proposeIndependence: (familyId: number, membershipId: number) =>
    api.post<Membership>(
      `/api/families/${familyId}/memberships/${membershipId}/independence-proposal`,
    ),

  revokeIndependenceProposal: (familyId: number, membershipId: number) =>
    api.delete<undefined>(
      `/api/families/${familyId}/memberships/${membershipId}/independence-proposal`,
    ),

  /** Approve independence (the requested child). Once done, they leave with their ledger. */
  approveIndependence: (familyId: number) =>
    api.post<undefined>(`/api/families/${familyId}/independence`),

  /** Set the order of children (parent members). One order per family, the same for everyone. */
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

  /** Called unauthenticated. Creates an account in exchange for an invitation code (ADR-0011). */
  redeemInvitation: (code: string, username: string, password: string, displayName: string) =>
    api.post<RedeemedInvitation>('/api/families/invitations/redeem', {
      code,
      username,
      password,
      display_name: displayName,
    }),

  /** Reasons often used in the family (input suggestions), most frequent first. */
  reasonSuggestions: (familyId: number) =>
    api.get<string[]>(`/api/families/${familyId}/reason-suggestions`),

  /** With fetch time. Offline returns the cache, and the time shows how old it is (ADR-0015). */
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
   * Fix an input mistake. The original record is not rewritten; a reversal and the correct
   * content are added as 2 rows (ADR-0022). The occurred-at time is taken from the original.
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
   * Set the daily bonus (rewrites it if already set, ADR-0024).
   *
   * Setting it does not touch the ledger. The first row comes the next time the date changes.
   */
  setDailyBonus: (familyId: number, ledgerId: number, amount: number, reason: string) =>
    api.put<DailyBonus>(`${ledgerPath(familyId, ledgerId)}/daily-bonus`, { amount, reason }),

  /** Stop it. Points already granted stay as is. */
  stopDailyBonus: (familyId: number, ledgerId: number) =>
    api.delete<undefined>(`${ledgerPath(familyId, ledgerId)}/daily-bonus`),
}
