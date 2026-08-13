/**
 * 家族の詳細（家族設定）。参加者と、見える範囲の残高が並ぶ。
 *
 * 参加者ごとの操作は、サーバーが返す可否（`can_*`）だけで出し分ける。子の追加と
 * 招待は自分の立場から決めるが、これも「サーバーが同じ条件で断る」場所に揃えて
 * ある（ADR-0009 の認可表）。子が開いた場合は自分の台帳への入り口だけが残る
 * （兄弟の残高は最初から返ってこない）。
 *
 * 子をこの家族から外す道は 2 つある。
 *
 * - **独立**（ADR-0014）… アカウントのある子だけ。親が指示し、子本人が
 *   承認して成立する。指示は承認まで取り下げられる。成立すると参加も記録も
 *   家族から消え、本人のアカウントは所属なしのメンバーとして残る。
 * - **削除** … 台帳に記録が無い参加者だけ。記録が 1 件でもあれば履歴が黙って
 *   消える経路になるので、サーバーが断る（ADR-0010）。画面にも出さない。
 */
import { useState, type FormEvent } from 'react'
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
  const [childName, setChildName] = useState('')
  const [issued, setIssued] = useState<TemporaryPassword | null>(null)
  const { pendingActionOf, runForRow } = usePendingRows<MemberAction>()

  /** 失敗はどれも「文言を出して読み直す」で終わる。成否で分岐する呼び出し元は無い。 */
  const run = async (action: () => Promise<unknown>) => {
    try {
      await action()
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const [addChild, addingChild] = usePendingAction(async (event: FormEvent) => {
    event.preventDefault()
    if (!family) return
    const familyId = family.id
    await run(async () => {
      await families.addChild(familyId, childName)
      setChildName('')
    })
  })

  // 成立すると scope が変わる（guest → member）。scope は JWT に焼き込まれて
  // いるため、ログアウトして再ログインするまで新しい権限は効かない（ADR-0014）。
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
  // 所属は 1 家族まで（ADR-0013）。URL が今の所属と違えば、もう見られない家族。
  if (!family || family.id !== Number(familyId)) {
    return <p className="error">{t('families.unavailable')}</p>
  }

  const id = family.id
  const isGuardian = family.my_role === 'owner' || family.my_role === 'parent'
  const isOwner = family.my_role === 'owner'
  // 毎日のボーナスを決める入口は台帳を書き換える操作（point:manage）。立場だけで
  // 出すと、運用者がロールの権限を編集した後に必ず 403 になるボタンが並ぶ
  // （ADR-0019 と同じ考え方）
  const canManagePoints = hasScope('point:manage')
  // 未紐付けなのは、親が作ったばかりの子と、バックアップから戻した参加者（ADR-0026）
  const unlinkedMembers = family.memberships.filter((m) => !m.is_linked && m.role !== 'owner')
  const me = family.memberships.find((m) => m.is_me)
  const independenceProposedToMe = family.my_role === 'child' && me?.independence_proposed === true

  /** 参加者ごとの操作。終わるまでその参加者の次の操作を受け付けない。 */
  const runForMember = (
    member: Membership,
    action: MemberAction,
    request: () => Promise<unknown>,
  ) => runForRow(member.id, action, () => run(request))

  const remove = (member: Membership) => {
    if (!window.confirm(t('families.confirmRemove', { name: member.display_name }))) return
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

      {isGuardian && (
        <InvitationPanel
          familyId={family.id}
          unlinkedMembers={unlinkedMembers}
          canInviteParent={isOwner}
          onChanged={reload}
        />
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

      {isGuardian && <FamilySettingsPanel family={family} onChanged={reload} />}

      {/* 毎日のボーナス（ADR-0024）は家族の決めごとなので家族設定に置く
          （ADR-0027）。量は子ごとに違ってよく、入力欄も子の数だけ並ぶ */}
      {isGuardian && canManagePoints && <DailyBonusPanel family={family} onChanged={reload} />}

      {isGuardian && <FamilyArchivePanel familyId={id} />}

      <p>
        <Link to="/">{t('common.back')}</Link>
      </p>
    </div>
  )
}
