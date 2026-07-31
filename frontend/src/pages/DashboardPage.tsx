/**
 * ホーム。家族みんなのポイント残高をひと目で見わたす画面。
 *
 * 管理者は親（家族）なので、システム運用の情報（API ドキュメント等）はここに
 * 置かない。システム管理へは ProfilePage（プロフィール設定）から入る。
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import { rewardPoints, type MemberSummary } from '../services/rewardPoints'
import { useAuth } from '../store/AuthContext'

export function DashboardPage() {
  const { t } = useI18n()
  const { user, hasScope } = useAuth()
  // guest 等、member:view を持たないアカウントもログイン直後にここへ来る。
  // scope が無いのに取得すると 403 が「メンバーがいない」に化けて誤解を招くので、
  // 取得も空の案内も member:view を持つ人にだけ行う。
  const canViewMembers = hasScope('member:view')
  const [members, setMembers] = useState<MemberSummary[] | null>(null)

  useEffect(() => {
    if (!canViewMembers) {
      setMembers([])
      return
    }
    void rewardPoints
      .listMembers()
      .then(setMembers)
      .catch(() => {
        setMembers([])
      })
  }, [canViewMembers])

  if (members === null) return <p className="loading">{t('common.loading')}</p>

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('dashboard.title')}</h1>
        <p className="page-subtitle">{t('dashboard.greeting', { name: user?.username ?? '' })}</p>
      </div>

      {canViewMembers &&
        (members.length === 0 ? (
          <div className="card">
            <p>{t('dashboard.empty')}</p>
            <p>
              <Link to="/members">{t('dashboard.goToMembers')}</Link>
            </p>
          </div>
        ) : (
          <div className="member-grid">
            {members.map((member) => (
              <Link key={member.id} to={`/members/${member.id}`} className="member-card">
                <span className="avatar" aria-hidden="true">
                  {member.name.slice(0, 1)}
                </span>
                <span className="member-card-name">
                  {member.name}
                  {member.is_self && ` (${t('members.self')})`}
                </span>
                <span className="member-card-balance">
                  {t('points.value', { points: member.balance })}
                </span>
              </Link>
            ))}
          </div>
        ))}
    </div>
  )
}
