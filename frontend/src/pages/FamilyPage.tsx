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
 * - **卒業**（ADR-0014 の独立）… アカウントのある子だけ。親が指示し、子本人が
 *   承認して成立する。指示は承認まで取り下げられる。成立すると参加も記録も
 *   家族から消え、本人のアカウントは所属なしのメンバーとして残る。
 * - **削除** … 台帳に記録が無い参加者だけ。記録が 1 件でもあれば履歴が黙って
 *   消える経路になるので、サーバーが断る（ADR-0010）。画面にも出さない。
 */
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { FamilySettingsPanel } from '../components/FamilySettingsPanel'
import { InvitationPanel } from '../components/InvitationPanel'
import { MemberList } from '../components/MemberList'
import { useToast } from '../components/ToastNotification'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, parseUtc, type Membership, type TemporaryPassword } from '../services/families'
import { useAuth } from '../store/AuthContext'
import { useFamily } from '../store/FamilyContext'

export function FamilyPage() {
  const { familyId } = useParams<{ familyId: string }>()
  const { t, locale } = useI18n()
  const { notify } = useToast()
  const { logout } = useAuth()
  const { family, loading, reload } = useFamily()
  const [childName, setChildName] = useState('')
  const [issued, setIssued] = useState<TemporaryPassword | null>(null)

  /** 失敗はどれも「文言を出して読み直す」で終わる。成否で分岐する呼び出し元は無い。 */
  const run = async (action: () => Promise<unknown>) => {
    try {
      await action()
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  if (loading) return <p className="loading">{t('common.loading')}</p>
  // 所属は 1 家族まで（ADR-0013）。URL が今の所属と違えば、もう見られない家族。
  if (!family || family.id !== Number(familyId)) {
    return <p className="error">{t('families.unavailable')}</p>
  }

  const id = family.id
  const isGuardian = family.my_role === 'owner' || family.my_role === 'parent'
  const isOwner = family.my_role === 'owner'
  const unlinkedChildren = family.memberships.filter((m) => m.role === 'child' && !m.is_linked)
  const me = family.memberships.find((m) => m.is_me)
  const graduationProposedToMe = family.my_role === 'child' && me?.independence_proposed === true

  const addChild = (event: FormEvent) => {
    event.preventDefault()
    void run(async () => {
      await families.addChild(id, childName)
      setChildName('')
    })
  }

  const remove = (member: Membership) => {
    if (!window.confirm(t('families.confirmRemove', { name: member.display_name }))) return
    void run(() => families.removeMembership(id, member.id))
  }

  const resetPassword = (member: Membership) => {
    void run(async () => {
      setIssued(await families.resetChildPassword(id, member.id))
    })
  }

  const graduate = (member: Membership) => {
    if (!window.confirm(t('families.graduation.confirmPropose', { name: member.display_name }))) {
      return
    }
    void run(() => families.proposeIndependence(id, member.id))
  }

  const withdrawGraduation = (member: Membership) => {
    void run(() => families.revokeIndependenceProposal(id, member.id))
  }

  // 成立すると scope が変わる（guest → member）。scope は JWT に焼き込まれて
  // いるため、ログアウトして再ログインするまで新しい権限は効かない（ADR-0014）。
  const approveGraduation = async () => {
    if (!window.confirm(t('families.graduation.confirmApprove'))) return
    try {
      await families.approveIndependence(id)
      notify('success', t('families.graduation.approved'))
      logout()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
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
          onGraduate={graduate}
          onWithdrawGraduation={withdrawGraduation}
          onRemove={remove}
          onResetPassword={resetPassword}
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
            <button type="submit">{t('families.addChild')}</button>
          </form>
        </section>
      )}

      {isOwner && (
        <InvitationPanel
          familyId={family.id}
          unlinkedChildren={unlinkedChildren}
          onChanged={reload}
        />
      )}

      {graduationProposedToMe && (
        <section className="card">
          <h2>{t('families.graduation.title')}</h2>
          <p>{t('families.graduation.approveHint')}</p>
          <button
            type="button"
            onClick={() => {
              void approveGraduation()
            }}
          >
            {t('families.graduation.approve')}
          </button>
        </section>
      )}

      {isGuardian && <FamilySettingsPanel family={family} onChanged={reload} />}

      <p>
        <Link to="/">{t('common.back')}</Link>
      </p>
    </div>
  )
}
