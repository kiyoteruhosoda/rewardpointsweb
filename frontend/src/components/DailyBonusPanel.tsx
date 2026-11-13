/**
 * Lists the daily bonus (ADR-0024) in family settings (ADR-0027).
 *
 * Family-wide rules are gathered in family settings. Without opening each child's ledger in turn,
 * this one card lets you compare how much each child is given.
 *
 * **The amount may differ per child.** Rather than one setting per family, show one input per child
 * (allowance usually varies by age, so equal amounts are the exception).
 *
 * Only parents who can open family settings see it. The server refuses anyone who cannot change the ledger
 * (`point:manage`), so to avoid an action that is refused after pressing, the caller renders it only
 * for parents.
 */
import { useI18n } from '../i18n'
import { type FamilyDetail } from '../services/families'
import { DailyBonusForm } from './DailyBonusForm'

interface Props {
  family: FamilyDetail
  /** Reloads the family after save/stop. */
  onChanged: () => Promise<unknown>
}

export function DailyBonusPanel({ family, onChanged }: Props) {
  const { t } = useI18n()
  // Children whose ledger is not visible return no setting either (ADR-0009). Parents get everyone
  const children = family.memberships.flatMap((member) =>
    member.role === 'child' && member.ledger_id !== null
      ? [
          {
            id: member.id,
            name: member.display_name,
            ledgerId: member.ledger_id,
            bonus: member.daily_bonus,
          },
        ]
      : [],
  )

  return (
    <section className="card">
      <h2>{t('dailyBonus.title')}</h2>
      <p>{t('dailyBonus.hint')}</p>
      {children.length === 0 ? (
        <p>{t('dailyBonus.noChildren')}</p>
      ) : (
        children.map((child) => (
          <DailyBonusForm
            // Reloading may change the setting, so the input is rebuilt each time
            // (so stale input does not remain while the saved value is shown)
            key={`${child.id}:${child.bonus?.amount ?? 'none'}:${child.bonus?.reason ?? ''}`}
            familyId={family.id}
            ledgerId={child.ledgerId}
            childName={child.name}
            bonus={child.bonus}
            onChanged={onChanged}
          />
        ))
      )}
    </section>
  )
}
