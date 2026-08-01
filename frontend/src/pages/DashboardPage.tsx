/**
 * ホーム。所属する家族の子どもたちの残高をひと目で見わたす画面。
 *
 * **家族の中での立場で見た目を変えない。** owner でも、招待で加わった親でも、
 * 同じ並び・同じカードが出る。家族の管理（招待・改名・解散）だけが owner の
 * 役目であって、日々の残高の見え方はそこに引きずられない（ADR-0009）。
 * 何人分が並ぶかはサーバーが返す台帳の範囲で決まる — 子には自分の台帳だけが
 * 返るので、兄弟の残高はここにも出ない。
 *
 * 並ぶ順は家族が決めた順（家族設定で変えられる）。左のナビゲーションと同じ順に
 * するため、並べ替えはサーバーが済ませて返す。
 *
 * 管理者は親（家族）なので、システム運用の情報（API ドキュメント等）はここに
 * 置かない。システム管理へは ProfilePage（プロフィール設定）から入る。
 */
import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import { useAuth } from '../store/AuthContext'
import { useFamily } from '../store/FamilyContext'

export function DashboardPage() {
  const { t } = useI18n()
  const { user, hasScope } = useAuth()
  // guest 等、family:view を持たないアカウントもログイン直後にここへ来る。
  // scope が無い人に「家族がない」と案内しても行き先が無いので、空の案内は出さない。
  const canView = hasScope('family:view')
  const { family, loading } = useFamily()

  if (loading) return <p className="loading">{t('common.loading')}</p>

  const children = (family?.memberships ?? []).filter((member) => member.ledger_id !== null)

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('dashboard.title')}</h1>
        <p className="page-subtitle">
          {t('dashboard.greeting', { name: user?.display_name ?? '' })}
        </p>
      </div>

      {canView &&
        (children.length === 0 ? (
          <div className="card">
            <p>{t('dashboard.empty')}</p>
            <p>
              <Link to="/families">{t('dashboard.goToFamilies')}</Link>
            </p>
          </div>
        ) : (
          <div className="member-grid">
            {children.map((member) => (
              <Link
                key={member.id}
                to={`/families/${family?.id ?? 0}/ledgers/${member.ledger_id ?? 0}`}
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
