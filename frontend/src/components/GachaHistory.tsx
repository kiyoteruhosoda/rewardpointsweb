/**
 * What was won (ADR-0060), newest first.
 *
 * Won prizes are real things a parent gives, so each row says whether it was handed over yet.
 * Parents mark it (and can take a mis-tap back); a child only sees the mark. Misses have nothing
 * to hand over and show no mark.
 */
import { useI18n } from '../i18n'
import type { GachaDraw } from '../services/gacha'
import { ActionButton } from './ActionButton'

interface Props {
  draws: GachaDraw[]
  canModify: boolean
  pendingOf: (drawId: number) => boolean
  onToggleHandOver: (draw: GachaDraw) => void
}

export function GachaHistory({ draws, canModify, pendingOf, onToggleHandOver }: Props) {
  const { t, locale } = useI18n()
  const waiting = draws.filter((draw) => !draw.is_miss && draw.handed_over_at === null).length

  return (
    <section className="card gacha-history">
      <h2>{t('gacha.historyTitle')}</h2>
      {draws.length === 0 ? (
        <p className="gacha-history-empty">{t('gacha.historyEmpty')}</p>
      ) : (
        <>
          {waiting > 0 && (
            <p className="gacha-history-waiting">{t('gacha.waiting', { count: waiting })}</p>
          )}
          <ul className="gacha-history-list">
            {draws.map((draw) => (
              <li key={draw.id} className={draw.is_miss ? 'is-miss' : undefined}>
                <div className="gacha-history-what">
                  <span className="gacha-history-prize">
                    {draw.is_miss
                      ? t('gacha.missPrize', { name: draw.prize_name })
                      : draw.prize_name}
                  </span>
                  <span className="gacha-history-meta">
                    {draw.gacha_name} · {new Date(draw.drawn_at).toLocaleString(locale)}
                  </span>
                </div>
                {!draw.is_miss && (
                  <div className="gacha-history-status">
                    <span
                      className={
                        draw.handed_over_at === null
                          ? 'gacha-status'
                          : 'gacha-status gacha-status-done'
                      }
                    >
                      {draw.handed_over_at === null
                        ? t('gacha.notHandedOver')
                        : t('gacha.handedOver')}
                    </span>
                    {canModify && (
                      <ActionButton
                        type="button"
                        pending={pendingOf(draw.id)}
                        aria-label={
                          draw.handed_over_at === null
                            ? t('gacha.markHandedOverFor', { name: draw.prize_name })
                            : t('gacha.takeBackFor', { name: draw.prize_name })
                        }
                        onClick={() => {
                          onToggleHandOver(draw)
                        }}
                      >
                        {draw.handed_over_at === null
                          ? t('gacha.markHandedOver')
                          : t('gacha.takeBack')}
                      </ActionButton>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
