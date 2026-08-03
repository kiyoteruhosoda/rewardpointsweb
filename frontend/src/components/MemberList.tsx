/**
 * 家族の参加者一覧。
 *
 * 表ではなく行のカードで組む。列を持つと、狭い画面では操作が右へ流れて画面外に
 * 隠れる（横送りの表に押し込むと、指で探し当てるまで気付けない）。名前・立場・
 * 残高・操作をひとかたまりにして、幅が足りなければ操作だけを次の行へ折り返す。
 *
 * 出す操作はサーバーが返す可否（`can_*`）だけで決める。立場から組み立て直すと、
 * 押した先で断られる操作（記録の残る子の削除など）まで出てしまう。
 */
import { Link } from 'react-router-dom'

import { useI18n } from '../i18n'
import type { FamilyDetail, Membership } from '../services/families'
import { ActionButton } from './ActionButton'

/** 参加者ごとに実行しうる操作。押したボタンにだけ実行中の目印を出すために使う。 */
export type MemberAction = 'independence' | 'removal' | 'passwordReset'

export interface MemberActions {
  /** 独立を指示する（ADR-0014）。子本人の承認で成立する。 */
  onProposeIndependence: (member: Membership) => void
  /** 独立の指示を取り下げる（承認前ならいつでも）。 */
  onWithdrawIndependence: (member: Membership) => void
  /** 参加ごと削除する（台帳が空のときだけ出る）。 */
  onRemove: (member: Membership) => void
  onResetPassword: (member: Membership) => void
  /** その参加者で実行中の操作（実行していなければ `null`）。 */
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
  // 1 人の参加者に対する操作は 1 つずつ（結果の取り違えを防ぐ）。
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
          {t('families.remove')}
        </ActionButton>
      )}
    </>
  )
}
