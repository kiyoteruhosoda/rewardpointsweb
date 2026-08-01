/**
 * ホーム。所属する家族の子どもたちの残高をひと目で見わたす画面。
 *
 * 管理者は親（家族）なので、システム運用の情報（API ドキュメント等）はここに
 * 置かない。システム管理へは ProfilePage（プロフィール設定）から入る。
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import { families, type FamilyDetail } from '../services/families'
import { useAuth } from '../store/AuthContext'

export function DashboardPage() {
  const { t } = useI18n()
  const { user, hasScope } = useAuth()
  // guest 等、family:view を持たないアカウントもログイン直後にここへ来る。
  // scope が無いのに取得すると 403 が「家族がいない」に化けて誤解を招くので、
  // 取得も空の案内も family:view を持つ人にだけ行う。
  const canView = hasScope('family:view')
  const [details, setDetails] = useState<FamilyDetail[] | null>(null)

  useEffect(() => {
    if (!canView) {
      setDetails([])
      return
    }
    void families
      .list()
      .then((list) => Promise.all(list.map((family) => families.view(family.id))))
      .then(setDetails)
      .catch(() => {
        setDetails([])
      })
  }, [canView])

  if (details === null) return <p className="loading">{t('common.loading')}</p>

  const ledgers = details.flatMap((family) =>
    family.memberships
      .filter((member) => member.ledger_id !== null)
      .map((member) => ({ family, member })),
  )

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('dashboard.title')}</h1>
        <p className="page-subtitle">
          {t('dashboard.greeting', { name: user?.display_name ?? '' })}
        </p>
      </div>

      {canView &&
        (ledgers.length === 0 ? (
          <div className="card">
            <p>{t('dashboard.empty')}</p>
            <p>
              <Link to="/families">{t('dashboard.goToFamilies')}</Link>
            </p>
          </div>
        ) : (
          <div className="member-grid">
            {ledgers.map(({ family, member }) => (
              <Link
                key={`${family.id}-${member.id}`}
                to={`/families/${family.id}/ledgers/${member.ledger_id ?? 0}`}
                className="member-card"
              >
                <span className="avatar" aria-hidden="true">
                  {member.display_name.slice(0, 1)}
                </span>
                <span className="member-card-name">
                  {member.display_name}
                  {member.is_me && ` (${t('families.self')})`}
                </span>
                <span className="member-card-balance">
                  {t('points.value', { points: member.balance ?? 0 })}
                </span>
              </Link>
            ))}
          </div>
        ))}
    </div>
  )
}
