/**
 * List of family participants.
 *
 * Built as row cards rather than a table. With columns, on narrow screens the actions flow right and
 * hide off-screen (squeezed into a horizontally scrolling table, you don't notice them until you find
 * them by finger). Name, role, balance and actions form one block, and only the actions wrap to the next line when space runs out.
 *
 * Which actions are shown is decided solely by the server's flags (`can_*`). Rebuilding them from role
 * would also show actions that are refused after pressing (e.g. deleting a child who still has records).
 */
import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import type { FamilyDetail, Membership } from '../services/families'
import { ActionButton } from './ActionButton'

/** Actions that can run per participant. Used to show the running marker only on the pressed button. */
export type MemberAction = 'independence' | 'removal' | 'passwordReset'

export interface MemberActions {
  /** Instructs independence (ADR-0014). Takes effect when the child approves. */
  onProposeIndependence: (member: Membership) => void
  /** Withdraws the independence instruction (any time before approval). */
  onWithdrawIndependence: (member: Membership) => void
  /** Deletes the participant entirely (shown only when the ledger is empty). */
  onRemove: (member: Membership) => void
  onResetPassword: (member: Membership) => void
  /** The action running for that participant (`null` if none). */
  pendingActionOf: (member: Membership) => MemberAction | null
}

interface Props extends MemberActions {
  family: FamilyDetail
}

export function MemberList({ family, ...actions }: Props) {
  const { t } = useI18n()

  return (
    <ul className="member-list">
      {family.memberships.map((member) => (
        <li key={member.id} className="member-row">
          <span className="avatar" aria-hidden="true">
            {member.display_name.slice(0, 1)}
          </span>
          <div className="member-row-identity">
            <p className="member-row-name">{member.display_name}</p>
            <p className="member-row-meta">
              <span>{t(`families.role.${member.role}`)}</span>
              {member.is_me && <span className="tag">{t('families.self')}</span>}
              {!member.is_linked && <span className="tag">{t('families.noAccount')}</span>}
              {member.independence_proposed && (
                <span className="tag tag-notice">{t('families.independence.proposed')}</span>
              )}
            </p>
          </div>
          {member.balance !== null && (
            <span className="member-row-balance">
              {t('points.value', { points: member.balance })}
            </span>
          )}
          <div className="member-row-actions">
            <MemberActionButtons member={member} familyId={family.id} {...actions} />
          </div>
        </li>
      ))}
    </ul>
  )
}

interface ButtonProps extends MemberActions {
  member: Membership
  familyId: number
}

function MemberActionButtons({ member, familyId, ...actions }: ButtonProps) {
  const { t } = useI18n()
  const pendingAction = actions.pendingActionOf(member)
  // One action at a time per participant (prevents mixing up results).
  const busy = pendingAction !== null

  return (
    <>
      {member.ledger_id !== null && (
        <Link to={`/families/${String(familyId)}/ledgers/${String(member.ledger_id)}`}>
          {t('points.history')}
        </Link>
      )}
      {member.can_reset_password && (
        <ActionButton
          type="button"
          pending={pendingAction === 'passwordReset'}
          disabled={busy}
          onClick={() => {
            actions.onResetPassword(member)
          }}
        >
          {t('families.resetPassword')}
        </ActionButton>
      )}
      {member.can_propose_independence &&
        (member.independence_proposed ? (
          <ActionButton
            type="button"
            pending={pendingAction === 'independence'}
            disabled={busy}
            onClick={() => {
              actions.onWithdrawIndependence(member)
            }}
          >
            {t('families.independence.withdraw')}
          </ActionButton>
        ) : (
          <ActionButton
            type="button"
            pending={pendingAction === 'independence'}
            disabled={busy}
            onClick={() => {
              actions.onProposeIndependence(member)
            }}
          >
            {t('families.independence.propose')}
          </ActionButton>
        ))}
      {member.can_remove && (
        <ActionButton
          type="button"
          className="danger"
          pending={pendingAction === 'removal'}
          disabled={busy}
          onClick={() => {
            actions.onRemove(member)
          }}
        >
          {member.role === 'display' ? t('families.removeDisplay') : t('families.remove')}
        </ActionButton>
      )}
    </>
  )
}
