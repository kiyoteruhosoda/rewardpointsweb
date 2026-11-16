/**
 * One gacha machine (ADR-0060): the machine art, the price, what is inside with each chance, and
 * the draw button.
 *
 * The button cannot be pressed when the balance does not cover the price, and says how many points
 * are still needed (the server refuses such a draw too). Parents also get edit and delete.
 */
import { useI18n } from '../i18n'
import { chanceOf, type Gacha } from '../services/gacha'
import { ActionButton } from './ActionButton'
import { GachaMachineArt, capsuleColor } from './GachaArt'

export type GachaAction = 'draw' | 'trial' | 'remove'

interface Props {
  gacha: Gacha
  balance: number
  canDraw: boolean
  canModify: boolean
  pending: GachaAction | null
  onDraw: () => void
  /** A parent's trial draw (nothing spent or recorded). */
  onTry: () => void
  onEdit: () => void
  onRemove: () => void
}

export function GachaMachineCard({
  gacha,
  balance,
  canDraw,
  canModify,
  pending,
  onDraw,
  onTry,
  onEdit,
  onRemove,
}: Props) {
  const { t } = useI18n()
  const short = gacha.price - balance

  return (
    <article className="card gacha-card" aria-label={gacha.name}>
      <header className="gacha-card-header">
        <h2 className="gacha-card-title">{gacha.name}</h2>
        <span className="gacha-card-price">{t('gacha.price', { points: gacha.price })}</span>
      </header>

      <div className="gacha-card-machine">
        <GachaMachineArt spinning={pending === 'draw' || pending === 'trial'} />
      </div>
      {(pending === 'draw' || pending === 'trial') && (
        <p className="gacha-card-turning" role="status">
          {t('gacha.turning')}
        </p>
      )}

      {canDraw && (
        <div className="gacha-card-draw">
          <ActionButton
            type="button"
            className="gacha-draw-button"
            pending={pending === 'draw'}
            disabled={short > 0 || pending !== null}
            aria-label={t('gacha.drawFor', { name: gacha.name, points: gacha.price })}
            onClick={onDraw}
          >
            {t('gacha.draw', { points: gacha.price })}
          </ActionButton>
          {short > 0 && <p className="gacha-card-short">{t('gacha.short', { points: short })}</p>}
        </div>
      )}

      {canModify && (
        // Lets a parent see the show and the odds before the child uses it
        <ActionButton
          type="button"
          className="gacha-trial-button"
          pending={pending === 'trial'}
          disabled={pending !== null}
          aria-label={t('gacha.tryFor', { name: gacha.name })}
          onClick={onTry}
        >
          {t('gacha.try')}
        </ActionButton>
      )}

      <details className="gacha-card-prizes">
        <summary>{t('gacha.prizes')}</summary>
        <ul>
          {gacha.prizes.map((prize, index) => (
            <li key={`${index}-${prize.name}`} className={prize.is_miss ? 'is-miss' : undefined}>
              <span
                className="gacha-prize-dot"
                style={{ background: prize.is_miss ? 'var(--slot-line)' : capsuleColor(index) }}
                aria-hidden="true"
              />
              <span className="gacha-prize-name">{prize.name}</span>
              <span className="gacha-prize-chance">
                {t('gacha.chance', { percent: chanceOf(prize, gacha.prizes) })}
              </span>
            </li>
          ))}
        </ul>
      </details>

      {canModify && (
        <footer className="gacha-card-footer">
          <button type="button" onClick={onEdit} disabled={pending !== null}>
            {t('gacha.edit')}
          </button>
          <ActionButton
            type="button"
            className="danger"
            pending={pending === 'remove'}
            disabled={pending !== null}
            onClick={onRemove}
          >
            {t('gacha.remove')}
          </ActionButton>
        </footer>
      )}
    </article>
  )
}
