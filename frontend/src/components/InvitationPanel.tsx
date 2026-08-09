/**
 * 招待コードの発行と取り消し（親メンバー）。
 *
 * 出せる招待は立場で分かれる（ADR-0020）。子ども宛のコードは親（owner / parent）
 * なら配れるが、親を入れるコードは owner だけ — 誰をこの家族へ入れるかは owner が
 * 決める。
 *
 * 宛先は 2 通り。**すでにいる参加者を指す**コード（その人がログインできるように
 * なるだけで、顔ぶれは変わらない）と、**新しい人を入れる**コード（親のみ）。
 * バックアップから復元した家族では owner 以外が全員未紐付けで戻るので、指せる
 * 相手には子だけでなく親も並ぶ（ADR-0026）。
 *
 * 平文のコードは発行の応答にしか現れないので、受け取った直後だけ画面に出す。
 * 一覧へ戻ると二度と読めない（保存されているのはハッシュだけ。ADR-0009）。
 *
 * 渡すのはコードそのものより、コードを載せた URL を主にする。受け取った人は開く
 * だけで入力済みの状態から始められる（`invitationLink.ts`）。コードも併せて出す —
 * URL を開けない相手（口頭・別の端末）には打ち込んでもらう必要がある。
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
   * アカウント未紐付けの参加者。宛先を指す招待は必ずこのどれかを指す。
   *
   * 子だけとは限らない。バックアップから復元した家族では、owner 以外は全員
   * 未紐付けで戻る（ADR-0026）。その人を指して配れば、台帳の「記録した人」が
   * 元のまま残る — 新しく入れ直すと参照が外れる。
   */
  unlinkedMembers: Membership[]
  /** もう 1 人の親を招けるか（owner のみ）。宛先を指す親宛のコードも owner だけ。 */
  canInviteParent: boolean
  onChanged: () => Promise<void>
}

export function InvitationPanel({ familyId, unlinkedMembers, canInviteParent, onChanged }: Props) {
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

  const issue = async (target: Membership | null) => {
    if (issuingFor !== null) return
    setIssuingFor(target?.id ?? 'parent')
    try {
      // 宛先を指す場合の立場は、その参加者のもの（子には子、親には親のコード）
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

  // 親宛のコードを配れるのは owner だけ（ADR-0020）。押してから断られる操作を出さない
  const invitableMembers = unlinkedMembers.filter(
    (member) => member.role === 'child' || (member.role === 'parent' && canInviteParent),
  )

  // 出す URL は「いま見ている入口」から作る。別の宛先を持ち出すと、手元では
  // 開けるのに配った先で届かない URL になり得る。
  const issuedLink = issued?.code
    ? { code: issued.code, url: invitationUrl(issued.code, window.location.origin) }
    : null

  const [copyUrl, copying] = usePendingAction(async (url: string) => {
    try {
      // 安全でない出所（http のまま開いた場合など）ではクリップボードを触れない。
      // 参照した時点で例外になるので、失敗はここでまとめて拾う。URL は画面に
      // 出したままなので、手で選んで写すことはできる。
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
