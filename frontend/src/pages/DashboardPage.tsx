/**
 * Home. A screen that shows the balances of the children in your family at a glance.
 *
 * **The view does not change with your role in the family.** An owner and a parent who joined by invitation
 * see the same order and the same cards. Managing the family (invite, rename, dissolve) is the owner's
 * job alone, and how daily balances look is not tied to it (ADR-0009).
 * How many are listed depends on the ledgers the server returns: a child gets only their own ledger,
 * so siblings' balances don't appear here either.
 *
 * The order is the one the family chose (changeable in family settings). To match the left navigation,
 * the server does the sorting and returns the result.
 *
 * Admins are parents (the family), so system operation info (API docs etc.) does not belong
 * here. System administration is reached from ProfilePage (profile settings).
 */
import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import type { FamilyDetail } from '../services/families'
import { useAuth } from '../store/AuthContext'
import { useFamily } from '../store/FamilyContext'

export function DashboardPage() {
  const { t } = useI18n()
  const { user, hasScope } = useAuth()
  // Accounts without family:view, such as guest, also land here right after login.
  // Telling someone without the scope "no family" leads nowhere, so show no empty-state guidance.
  const canView = hasScope('family:view')
  const { family, failed, loading } = useFamily()

  if (loading) return <p className="loading">{t('common.loading')}</p>

  return (
    <div className="page">
      <div className="page-heading">
        <h1>{t('dashboard.title')}</h1>
        <p className="page-subtitle">
          {t('dashboard.greeting', { name: user?.display_name ?? '' })}
        </p>
      </div>

      {canView && <Balances family={family} failed={failed} />}
    </div>
  )
}

interface BalancesProps {
  family: FamilyDetail | null
  failed: boolean
}

function Balances({ family, failed }: BalancesProps) {
  const { t } = useI18n()

  // Saying "no children" when loading failed would be false (there may be a family)
  if (failed) {
    return (
      <div className="card">
        <p>{t('families.unavailable')}</p>
      </div>
    )
  }

  const children = (family?.memberships ?? []).filter((member) => member.ledger_id !== null)
  if (children.length === 0) {
    return (
      <div className="card">
        <p>{t('dashboard.empty')}</p>
        <p>
          <Link to="/families">{t('dashboard.goToFamilies')}</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="member-grid">
      {children.map((member) => (
        <Link
          key={member.id}
          to={`/families/${String(family?.id ?? 0)}/ledgers/${String(member.ledger_id ?? 0)}`}
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
  )
}
