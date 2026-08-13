/**
 * 毎日のボーナス（ADR-0024）を家族設定に並べる（ADR-0027）。
 *
 * 家族の決めごとは家族設定に集める。子ども一人ひとりの台帳を開いて回らなくても、
 * 誰にいくつ渡しているかがこの 1 枚で見比べられる。
 *
 * **量は子ごとに違ってよい。** 家族に 1 つの設定にはせず、子の数だけ入力欄を出す
 * （年齢でお小遣いが違うのが普通なので、揃える方が例外）。
 *
 * 出るのは家族設定を開ける親だけ。台帳を変更できる相手（`point:manage`）でなければ
 * サーバーが断るので、押してから断られる操作にならないよう、呼び出し側が親のときだけ
 * 描く。
 */
import { useI18n } from '../i18n'
import { type FamilyDetail } from '../services/families'
import { DailyBonusForm } from './DailyBonusForm'

interface Props {
  family: FamilyDetail
  /** 保存・停止のあと、家族を読み直す。 */
  onChanged: () => Promise<unknown>
}

export function DailyBonusPanel({ family, onChanged }: Props) {
  const { t } = useI18n()
  // 台帳の見えない子は設定も返らない（ADR-0009）。親には全員ぶんが載る
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
            // 読み直すと設定が変わり得るので、入力欄はその都度作り直す
            // （保存した値を出したまま古い入力が残らないように）
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
