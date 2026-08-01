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

export interface MemberActions {
  /** 卒業を指示する（ADR-0014 の独立。画面では「卒業」と呼ぶ）。 */
  onGraduate: (member: Membership) => void
  /** 卒業の指示を取り下げる。 */
  onWithdrawGraduation: (member: Membership) => void
  /** 参加ごと削除する（台帳が空のときだけ出る）。 */
  onRemove: (member: Membership) => void
  onResetPassword: (member: Membership) => void
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
                <span className="tag tag-notice">{t('families.graduation.proposed')}</span>
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

  return (
    <>
      {member.ledger_id !== null && (
        <Link to={`/families/${String(familyId)}/ledgers/${String(member.ledger_id)}`}>
          {t('points.history')}
        </Link>
      )}
      {member.can_reset_password && (
        <button
          type="button"
          onClick={() => {
            actions.onResetPassword(member)
          }}
        >
          {t('families.resetPassword')}
        </button>
      )}
      {member.can_graduate &&
        (member.independence_proposed ? (
          <button
            type="button"
            onClick={() => {
              actions.onWithdrawGraduation(member)
            }}
          >
            {t('families.graduation.withdraw')}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => {
              actions.onGraduate(member)
            }}
          >
            {t('families.graduation.propose')}
          </button>
        ))}
      {member.can_remove && (
        <button
          type="button"
          className="danger"
          onClick={() => {
            actions.onRemove(member)
          }}
        >
          {t('families.remove')}
        </button>
      )}
    </>
  )
}
