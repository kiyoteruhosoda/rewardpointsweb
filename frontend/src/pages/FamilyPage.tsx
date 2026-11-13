/**
 * Family details (family settings). Lists participants and the balances visible to the viewer.
 *
 * Ordered "things seen daily -> things touched occasionally": participants -> family settings
 * (family rules; the daily bonus follows here) -> invitations -> adding children -> backup.
 * Adding children and handing out invitation codes happen only when setting up the family,
 * so they are not placed at the top of a screen opened every day.
 *
 * Per-participant actions are shown solely by the permissions the server returns (`can_*`).
 * Adding children and inviting are decided by the viewer's role, also aligned with where "the
 * server refuses under the same conditions" (ADR-0009 authorization table). A child opening it
 * sees only the entry to their own ledger (siblings' balances are never returned).
 *
 * There are two ways to remove a child from this family.
 *
 * - **Independence** (ADR-0014) … only children with an account. A parent requests it and the
 *   child approves it. The request can be withdrawn until approved. Once done, membership and
 *   records leave the family, and the child's account remains as a member with no family.
 * - **Delete** … only participants with no ledger records. Even one record would make this a path
 *   for silently erasing history, so the server refuses (ADR-0010). The screen hides it too.
 */
import { useState, type SubmitEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ActionButton } from '../components/ActionButton'
import { DailyBonusPanel } from '../components/DailyBonusPanel'
import { FamilyArchivePanel } from '../components/FamilyArchivePanel'
import { FamilySettingsPanel } from '../components/FamilySettingsPanel'
import { InvitationPanel } from '../components/InvitationPanel'
import { MemberList, type MemberAction } from '../components/MemberList'
import { useToast } from '../components/ToastNotification'
import { usePendingAction } from '../hooks/usePendingAction'
import { usePendingRows } from '../hooks/usePendingRows'
import { useSessionValue } from '../hooks/useSessionDraft'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, parseUtc, type Membership, type TemporaryPassword } from '../services/families'
import { useAuth } from '../store/AuthContext'
import { useFamily } from '../store/FamilyContext'

export function FamilyPage() {
  const { familyId } = useParams<{ familyId: string }>()
  const { t, locale } = useI18n()
  const { notify } = useToast()
  const { hasScope, logout } = useAuth()
  const { family, loading, reload } = useFamily()
  // Keep unfinished input across the login round trip (ADR-0058)
  const [childName, setChildName] = useSessionValue('family.childName', '')
  const [issued, setIssued] = useState<TemporaryPassword | null>(null)
  const { pendingActionOf, runForRow } = usePendingRows<MemberAction>()

  /** Every failure ends with "show a message and reload". No caller branches on the outcome. */
  const run = async (action: () => Promise<unknown>) => {
    try {
      await action()
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const [addChild, addingChild] = usePendingAction(async (event: SubmitEvent) => {
    event.preventDefault()
    if (!family) return
    const familyId = family.id
    await run(async () => {
      await families.addChild(familyId, childName)
      setChildName('')
    })
  })

  // Once approved the scope changes (guest -> member). Scopes are baked into the JWT,
  // so the new permissions apply only after logging out and back in (ADR-0014).
  const [approveIndependence, approving] = usePendingAction(async () => {
    if (!family) return
    if (!window.confirm(t('families.independence.confirmApprove'))) return
    try {
      await families.approveIndependence(family.id)
      notify('success', t('families.independence.approved'))
      logout()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  })

  if (loading) return <p className="loading">{t('common.loading')}</p>
  // One family per person at most (ADR-0013). A URL for another family is no longer viewable.
  if (!family || family.id !== Number(familyId)) {
    return <p className="error">{t('families.unavailable')}</p>
  }

  const id = family.id
  const isGuardian = family.my_role === 'owner' || family.my_role === 'parent'
  const isOwner = family.my_role === 'owner'
  // Setting the daily bonus rewrites ledgers (point:manage). Showing it by role alone would
  // display buttons that always 403 after an operator edits the role's permissions
  // (same idea as ADR-0019)
  const canManagePoints = hasScope('point:manage')
  // Unlinked: children a parent just created, and participants restored from a backup (ADR-0026)
  const unlinkedMembers = family.memberships.filter((m) => !m.is_linked && m.role !== 'owner')
  const me = family.memberships.find((m) => m.is_me)
  const independenceProposedToMe = family.my_role === 'child' && me?.independence_proposed === true

  /** Per-participant action. Further actions on that participant wait until it finishes. */
  const runForMember = (
    member: Membership,
    action: MemberAction,
    request: () => Promise<unknown>,
  ) => runForRow(member.id, action, () => run(request))

  const remove = (member: Membership) => {
    // A display leaves no records or account owner; word it unlike removing a person (ADR-0047)
    const question =
      member.role === 'display' ? 'families.confirmRemoveDisplay' : 'families.confirmRemove'
    if (!window.confirm(t(question, { name: member.display_name }))) return
    void runForMember(member, 'removal', () => families.removeMembership(id, member.id))
  }

  const resetPassword = (member: Membership) => {
    void runForMember(member, 'passwordReset', async () => {
      setIssued(await families.resetChildPassword(id, member.id))
    })
  }

  const proposeIndependence = (member: Membership) => {
    if (!window.confirm(t('families.independence.confirmPropose', { name: member.display_name }))) {
      return
    }
    void runForMember(member, 'independence', () => families.proposeIndependence(id, member.id))
  }

  const withdrawIndependence = (member: Membership) => {
    void runForMember(member, 'independence', () =>
      families.revokeIndependenceProposal(id, member.id),
    )
  }

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{family.name}</h1>
        <p className="page-subtitle">{t(`families.role.${family.my_role}`)}</p>
      </div>

      <section className="card">
        <h2>{t('families.members')}</h2>
        {isGuardian && <p>{t('families.membersHint')}</p>}
        <MemberList
          family={family}
          onProposeIndependence={proposeIndependence}
          onWithdrawIndependence={withdrawIndependence}
          onRemove={remove}
          onResetPassword={resetPassword}
          pendingActionOf={(member) => pendingActionOf(member.id)}
        />

        {issued && (
          <p className="balance">
            {t('families.temporaryPassword', { username: issued.username })}:{' '}
            <strong>{issued.password}</strong> (
            {t('families.temporaryPasswordUntil', {
              until: parseUtc(issued.expires_at).toLocaleString(locale),
            })}
            )
          </p>
        )}
      </section>

      {isGuardian && <FamilySettingsPanel family={family} onChanged={reload} />}

      {/* The daily bonus (ADR-0024) is a family rule, so it lives in family settings
          (ADR-0027). Amounts may differ per child, with one input per child */}
      {isGuardian && canManagePoints && <DailyBonusPanel family={family} onChanged={reload} />}

      {isGuardian && (
        <InvitationPanel
          familyId={family.id}
          unlinkedMembers={unlinkedMembers}
          canInviteParent={isOwner}
          onChanged={reload}
        />
      )}

      {isGuardian && (
        <section className="card">
          <h2>{t('families.addChild')}</h2>
          <p>{t('families.addChildHint')}</p>
          <form className="inline-form" onSubmit={addChild}>
            <label>
              {t('families.name')}
              <input
                value={childName}
                onChange={(event) => {
                  setChildName(event.target.value)
                }}
                required
              />
            </label>
            <ActionButton type="submit" pending={addingChild}>
              {t('families.addChild')}
            </ActionButton>
          </form>
        </section>
      )}

      {independenceProposedToMe && (
        <section className="card">
          <h2>{t('families.independence.title')}</h2>
          <p>{t('families.independence.approveHint')}</p>
          <ActionButton type="button" pending={approving} onClick={approveIndependence}>
            {t('families.independence.approve')}
          </ActionButton>
        </section>
      )}

      {isGuardian && <FamilyArchivePanel familyId={id} />}

      <p>
        <Link to="/">{t('common.back')}</Link>
      </p>
    </div>
  )
}
