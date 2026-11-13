/**
 * Issuing and revoking invitation codes (parent members).
 *
 * Which invitations can be issued depends on role (ADR-0020). Codes for children can be handed out by
 * parents (owner / parent), but codes that add a parent are owner only — the owner decides who joins
 * this family.
 *
 * Two kinds of target. A code **pointing at an existing participant** (it only lets that person log in;
 * the membership doesn't change) and a code that **adds a new person** (parents only).
 * In a family restored from backup, everyone except the owner comes back unlinked, so the targets
 * that can be pointed at include parents as well as children (ADR-0026).
 *
 * The plaintext code appears only in the issue response, so it is shown only right after receiving it.
 * Once back on the list it can never be read again (only the hash is stored; ADR-0009).
 *
 * What is handed out is primarily the URL containing the code rather than the code itself. Recipients
 * just open it and start with it pre-filled (`invitationLink.ts`). The code is shown too —
 * recipients who cannot open the URL (by voice, another device) need to type it in.
 */
import { useEffect, useState } from 'react'

import { usePendingAction } from '../hooks/usePendingAction'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, parseUtc, type Invitation, type Membership } from '../services/families'
import { invitationUrl } from '../services/invitationLink'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

interface Props {
  familyId: number
  /**
   * Participants not linked to an account. An invitation with a target always points at one of these.
   *
   * Not necessarily only children. In a family restored from backup, everyone except the owner
   * comes back unlinked (ADR-0026). Handing out a code that points at that person keeps the ledger's
   * "recorded by" intact — re-adding them anew would break the reference.
   */
  unlinkedMembers: Membership[]
  /** Whether another parent can be invited (owner only). Codes for parents with a target are owner only too. */
  canInviteParent: boolean
  onChanged: () => Promise<void>
}

export function InvitationPanel({ familyId, unlinkedMembers, canInviteParent, onChanged }: Props) {
  const { t, locale } = useI18n()
  const { notify } = useToast()
  const [pending, setPending] = useState<Invitation[]>([])
  const [issued, setIssued] = useState<Invitation | null>(null)
  // The target being issued (`'parent'` for parents, the participant ID for children) and the invitation being revoked.
  // Keep which one is running so the spinner shows only on the pressed button.
  const [issuingFor, setIssuingFor] = useState<number | 'parent' | null>(null)
  const [revokingId, setRevokingId] = useState<number | null>(null)

  const reload = () => families.listInvitations(familyId).then(setPending)

  useEffect(() => {
    void families
      .listInvitations(familyId)
      .then(setPending)
      .catch(() => {
        setPending([])
      })
  }, [familyId])

  const issue = async (target: Membership | null) => {
    if (issuingFor !== null) return
    setIssuingFor(target?.id ?? 'parent')
    try {
      // When pointing at a target, the role is that participant's (child code for a child, parent code for a parent)
      const invitation = await families.issueInvitation(
        familyId,
        target === null ? 'parent' : target.role,
        target?.id ?? null,
      )
      setIssued(invitation)
      await reload()
      await onChanged()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    } finally {
      setIssuingFor(null)
    }
  }

  const revoke = async (invitationId: number) => {
    if (revokingId !== null) return
    setRevokingId(invitationId)
    try {
      await families.revokeInvitation(familyId, invitationId)
      setIssued(null)
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    } finally {
      setRevokingId(null)
    }
  }

  // Only the owner can hand out parent codes (ADR-0020). Don't show actions that get refused after pressing
  const invitableMembers = unlinkedMembers.filter(
    (member) => member.role === 'child' || (member.role === 'parent' && canInviteParent),
  )

  // Build the URL from "the entry currently being viewed". Using another origin could produce a URL
  // that opens locally but does not reach the recipients.
  const issuedLink = issued?.code
    ? { code: issued.code, url: invitationUrl(issued.code, issued.role, window.location.origin) }
    : null

  const [copyUrl, copying] = usePendingAction(async (url: string) => {
    try {
      // On insecure origins (e.g. opened over plain http) the clipboard is not accessible.
      // Accessing it throws, so failures are caught here together. The URL stays on screen,
      // so it can still be selected and copied by hand.
      await navigator.clipboard.writeText(url)
      notify('success', t('invitations.linkCopied'))
    } catch {
      notify('error', t('invitations.linkCopyFailed'))
    }
  })

  return (
    <section className="card">
      <h2>{t('invitations.title')}</h2>
      <p>{t('invitations.hint')}</p>

      {issuedLink && (
        <div className="card-inset">
          <p>{t('invitations.linkHint')}</p>
          <p className="invitation-link">
            <a href={issuedLink.url}>{issuedLink.url}</a>
          </p>
          <ActionButton
            type="button"
            pending={copying}
            onClick={() => {
              copyUrl(issuedLink.url)
            }}
          >
            {t('invitations.copyLink')}
          </ActionButton>
          <p className="balance">
            {t('invitations.issued')}: <strong>{issuedLink.code}</strong>
          </p>
        </div>
      )}

      <div className="inline-form">
        {canInviteParent && (
          <ActionButton
            type="button"
            pending={issuingFor === 'parent'}
            disabled={issuingFor !== null}
            onClick={() => {
              void issue(null)
            }}
          >
            {t('invitations.inviteParent')}
          </ActionButton>
        )}
        {invitableMembers.map((member) => (
          <ActionButton
            key={member.id}
            type="button"
            pending={issuingFor === member.id}
            disabled={issuingFor !== null}
            onClick={() => {
              void issue(member)
            }}
          >
            {t('invitations.inviteMember', { name: member.display_name })}
          </ActionButton>
        ))}
      </div>

      {pending.length === 0 ? (
        <p>{t('invitations.empty')}</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t('invitations.for')}</th>
                <th>{t('invitations.expiresAt')}</th>
                <th>{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {pending.map((invitation) => (
                <tr key={invitation.id}>
                  <td>{invitation.target_display_name ?? t(`families.role.${invitation.role}`)}</td>
                  <td>{parseUtc(invitation.expires_at).toLocaleString(locale)}</td>
                  <td>
                    <ActionButton
                      type="button"
                      pending={revokingId === invitation.id}
                      disabled={revokingId !== null}
                      onClick={() => {
                        void revoke(invitation.id)
                      }}
                    >
                      {t('invitations.revoke')}
                    </ActionButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
