/**
 * 家族の詳細。参加者と、見える範囲の残高が並ぶ。
 *
 * 子の追加と一時パスワードの発行は `my_role` が親（owner / parent）のとき、
 * 招待と除名は owner のときだけ出す。家族の構成を変えるのは owner の役目
 * （ADR-0009 の認可表）。子が開いた場合は自分の台帳への入り口だけが残る
 * （兄弟の残高は最初から返ってこない）。
 *
 * 独立（ADR-0014）は 2 段階: 親がアカウントの結び付いた子へ指示し、子本人が
 * 承認する。指示は承認まで取り下げられる。承認で参加と記録が家族から消える
 * ので、両方の確認文で「記録が削除される」ことを示す。
 */
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { FamilySettingsPanel } from '../components/FamilySettingsPanel'
import { InvitationPanel } from '../components/InvitationPanel'
import { useToast } from '../components/ToastNotification'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { families, parseUtc, type FamilyDetail, type TemporaryPassword } from '../services/families'
import { useAuth } from '../store/AuthContext'

export function FamilyPage() {
  const { familyId } = useParams<{ familyId: string }>()
  const { t, locale } = useI18n()
  const { notify } = useToast()
  const { logout } = useAuth()
  const [family, setFamily] = useState<FamilyDetail | null>(null)
  const [failed, setFailed] = useState(false)
  const [childName, setChildName] = useState('')
  const [issued, setIssued] = useState<TemporaryPassword | null>(null)

  const id = Number(familyId)

  const reload = useCallback(
    () =>
      families
        .view(id)
        .then(setFamily)
        .catch((error: unknown) => {
          setFailed(true)
          notify('error', t(errorMessageKey(error)))
        }),
    [id, notify, t],
  )

  useEffect(() => {
    void reload()
  }, [reload])

  const addChild = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await families.addChild(id, childName)
      setChildName('')
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const remove = async (membershipId: number, name: string) => {
    if (!window.confirm(t('families.confirmRemove', { name }))) return
    try {
      await families.removeMembership(id, membershipId)
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const resetPassword = async (membershipId: number) => {
    try {
      setIssued(await families.resetChildPassword(id, membershipId))
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const proposeIndependence = async (membershipId: number, name: string) => {
    if (!window.confirm(t('families.independence.confirmPropose', { name }))) return
    try {
      await families.proposeIndependence(id, membershipId)
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  const withdrawIndependence = async (membershipId: number) => {
    try {
      await families.revokeIndependenceProposal(id, membershipId)
      await reload()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  // 成立すると scope が変わる（member → manager）。scope は JWT に焼き込まれて
  // いるため、ログアウトして再ログインするまで新しい権限は効かない（ADR-0014）。
  const approveIndependence = async () => {
    if (!window.confirm(t('families.independence.confirmApprove'))) return
    try {
      await families.approveIndependence(id)
      notify('success', t('families.independence.approved'))
      logout()
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
    }
  }

  if (failed) return <p className="error">{t('families.unavailable')}</p>
  if (family === null) return <p className="loading">{t('common.loading')}</p>

  const isGuardian = family.my_role === 'owner' || family.my_role === 'parent'
  const isOwner = family.my_role === 'owner'
  const unlinkedChildren = family.memberships.filter((m) => m.role === 'child' && !m.is_linked)
  const me = family.memberships.find((m) => m.is_me)
  const independenceProposedToMe = family.my_role === 'child' && me?.independence_proposed === true

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{family.name}</h1>
        <p className="page-subtitle">{t(`families.role.${family.my_role}`)}</p>
      </div>

      <section className="card">
        <h2>{t('families.members')}</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t('families.name')}</th>
                <th>{t('families.roleColumn')}</th>
                <th>{t('points.balance')}</th>
                <th>{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {family.memberships.map((member) => (
                <tr key={member.id}>
                  <td>
                    {member.display_name}
                    {member.is_me && ` (${t('families.self')})`}
                    {member.role === 'child' &&
                      !member.is_linked &&
                      ` (${t('families.noAccount')})`}
                    {member.independence_proposed && ` (${t('families.independence.proposed')})`}
                  </td>
                  <td>{t(`families.role.${member.role}`)}</td>
                  <td>
                    {member.balance === null ? '—' : t('points.value', { points: member.balance })}
                  </td>
                  <td>
                    {member.ledger_id !== null && (
                      <Link to={`/families/${family.id}/ledgers/${member.ledger_id}`}>
                        {t('points.history')}
                      </Link>
                    )}
                    {isGuardian && member.role === 'child' && member.is_linked && (
                      <>
                        {' '}
                        <button
                          type="button"
                          onClick={() => {
                            void resetPassword(member.id)
                          }}
                        >
                          {t('families.resetPassword')}
                        </button>{' '}
                        {member.independence_proposed ? (
                          <button
                            type="button"
                            onClick={() => {
                              void withdrawIndependence(member.id)
                            }}
                          >
                            {t('families.independence.withdraw')}
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              void proposeIndependence(member.id, member.display_name)
                            }}
                          >
                            {t('families.independence.propose')}
                          </button>
                        )}
                      </>
                    )}
                    {isOwner && !member.is_me && (
                      <>
                        {' '}
                        <button
                          type="button"
                          onClick={() => {
                            void remove(member.id, member.display_name)
                          }}
                        >
                          {t('families.remove')}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

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
          <form
            className="inline-form"
            onSubmit={(event) => {
              void addChild(event)
            }}
          >
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

      {independenceProposedToMe && (
        <section className="card">
          <h2>{t('families.independence.title')}</h2>
          <p>{t('families.independence.approveHint')}</p>
          <button
            type="button"
            onClick={() => {
              void approveIndependence()
            }}
          >
            {t('families.independence.approve')}
          </button>
        </section>
      )}

      {isGuardian && <FamilySettingsPanel family={family} onRenamed={reload} />}

      <p>
        <Link to="/families">{t('common.back')}</Link>
      </p>
    </div>
  )
}
