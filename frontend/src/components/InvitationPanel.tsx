/**
 * 招待コードの発行と取り消し（親メンバー）。
 *
 * 出せる招待は立場で分かれる（ADR-0020）。子ども宛のコードは親（owner / parent）
 * なら配れるが、もう 1 人の親を招くのは owner だけ — 誰をこの家族へ入れるかは
 * owner が決める。
 *
 * 平文のコードは発行の応答にしか現れないので、受け取った直後だけ画面に出す。
 * 一覧へ戻ると二度と読めない（保存されているのはハッシュだけ。ADR-0009）。
 */
import { useEffect, useState } from 'react'

import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, parseUtc, type Invitation, type Membership } from '../services/families'
import { ActionButton } from './ActionButton'
import { useToast } from './ToastNotification'

interface Props {
  familyId: number
  /** アカウント未紐付けの子。子ども宛の招待は必ずこのどれかを指す。 */
  unlinkedChildren: Membership[]
  /** もう 1 人の親を招けるか（owner のみ）。 */
  canInviteParent: boolean
  onChanged: () => Promise<void>
}

export function InvitationPanel({ familyId, unlinkedChildren, canInviteParent, onChanged }: Props) {
  const { t, locale } = useI18n()
  const { notify } = useToast()
  const [pending, setPending] = useState<Invitation[]>([])
  const [issued, setIssued] = useState<Invitation | null>(null)
  // 発行中の宛先（親宛は `'parent'`、子宛はその参加 ID）と取り消し中の招待。
  // 押したボタンにだけスピナーを出すため、どれを実行中かまで持つ。
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

  const issue = async (targetMembershipId: number | null) => {
    if (issuingFor !== null) return
    setIssuingFor(targetMembershipId ?? 'parent')
    try {
      const invitation = await families.issueInvitation(
        familyId,
        targetMembershipId === null ? 'parent' : 'child',
        targetMembershipId,
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

  return (
    <section className="card">
      <h2>{t('invitations.title')}</h2>
      <p>{t('invitations.hint')}</p>

      {issued?.code && (
        <p className="balance">
          {t('invitations.issued')}: <strong>{issued.code}</strong>
        </p>
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
        {unlinkedChildren.map((child) => (
          <ActionButton
            key={child.id}
            type="button"
            pending={issuingFor === child.id}
            disabled={issuingFor !== null}
            onClick={() => {
              void issue(child.id)
            }}
          >
            {t('invitations.inviteChild', { name: child.display_name })}
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
