/**
 * One child's gacha machines on a single screen (ADR-0060).
 *
 * The top shows the points that can be spent. Each machine has its own draw button; pressing it
 * turns the handle until the server answers, then the result opens over the screen. Each press
 * keeps one idempotency key until it succeeds, so pressing again after a failed connection asks
 * "did that draw go through?" instead of drawing a second time.
 *
 * A draw spends points from the ledger, so afterwards the family is reloaded too (the source of
 * balances in the navigation and dashboard; ADR-0021).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { capsuleColor } from '../components/GachaArt'
import { GachaBundleSummary } from '../components/GachaBundleSummary'
import { GachaForm } from '../components/GachaForm'
import { GachaHistory } from '../components/GachaHistory'
import { GachaMachineCard, type GachaAction } from '../components/GachaMachineCard'
import { GachaReveal } from '../components/GachaReveal'
import { useToast } from '../components/ToastNotification'
import { usePendingRows } from '../hooks/usePendingRows'
import { useRefreshOnReturn } from '../hooks/useRefreshOnReturn'
import { useI18n } from '../i18n'
import { errorMessageKey } from '../services/api'
import { newIdempotencyKey } from '../services/families'
import { waitForTurn } from '../services/gachaShow'
import {
  gacha as gachaApi,
  type Gacha,
  type GachaBoard,
  type GachaDesign,
  type GachaDraw,
  type GachaTrial,
} from '../services/gacha'
import { useFamily } from '../store/FamilyContext'

interface Revealed {
  draw: GachaTrial
  color: string
  /** null for a parent's trial draw and for draws within a bundle */
  balance: number | null
  trial?: boolean
  /** Where the draw is within a bundle */
  position?: { index: number; total: number; bonus: boolean }
}

interface BundleSummary {
  draws: GachaDraw[]
  colors: string[]
  balance: number
}

/** Colour of the capsule for a won prize: the prize's colour in the machine's list. */
function colorOf(machine: Gacha, draw: GachaTrial): string {
  const index = machine.prizes.findIndex((prize) => prize.name === draw.prize_name)
  return draw.is_miss ? '#c3c8d8' : capsuleColor(Math.max(index, 0))
}

export function GachaPage() {
  const { familyId, ledgerId } = useParams<{ familyId: string; ledgerId: string }>()
  const { t } = useI18n()
  const { notify } = useToast()
  const { reload: reloadFamily } = useFamily()
  const [board, setBoard] = useState<GachaBoard | null>(null)
  const [failed, setFailed] = useState(false)
  const [editing, setEditing] = useState<number | null>(null)
  const [revealed, setRevealed] = useState<Revealed | null>(null)
  const machines = usePendingRows<GachaAction>()
  const handOvers = usePendingRows<'hand-over'>()
  // One key per press, per machine. Kept until the press succeeds (ADR-0010)
  const pressKeys = useRef<Map<number, string>>(new Map())

  const [summary, setSummary] = useState<BundleSummary | null>(null)
  // Resolves when the open result is closed (a bundle then moves on to its next draw)
  const nextRef = useRef<(() => void) | null>(null)
  const bundleKeys = useRef<Map<number, string>>(new Map())
  const closeSummary = useCallback(() => {
    setSummary(null)
  }, [])

  const closeReveal = useCallback(() => {
    setRevealed(null)
    const next = nextRef.current
    nextRef.current = null
    next?.()
  }, [])

  const family = Number(familyId)
  const ledger = Number(ledgerId)

  const reload = useCallback(
    () =>
      gachaApi
        .board(family, ledger)
        .then((result) => {
          setBoard(result)
          setFailed(false)
        })
        .catch((error: unknown) => {
          setFailed(true)
          notify('error', t(errorMessageKey(error)))
        }),
    [family, ledger, notify, t],
  )

  useEffect(() => {
    setBoard(null)
    void reload()
  }, [reload])

  // Points added on another device do not reach this screen
  useRefreshOnReturn(reload)

  const draw = (machine: Gacha) => {
    void machines.runForRow(machine.id, 'draw', async () => {
      const key = pressKeys.current.get(machine.id) ?? newIdempotencyKey()
      pressKeys.current.set(machine.id, key)
      const startedAt = Date.now()
      try {
        const result = await gachaApi.draw(family, ledger, machine.id, key)
        pressKeys.current.delete(machine.id)
        // The handle keeps turning for the whole show, however fast the answer came (task #1045)
        await waitForTurn(startedAt)
        setBoard((current) =>
          current === null
            ? current
            : { ...current, balance: result.balance, draws: [result.draw, ...current.draws] },
        )
        setRevealed({
          draw: result.draw,
          color: colorOf(machine, result.draw),
          balance: result.balance,
        })
        await reloadFamily()
      } catch (error) {
        notify('error', t(errorMessageKey(error)))
        await reload()
      }
    })
  }

  /** Shows one result and resolves once it is closed. */
  const showAndWait = (value: Revealed) =>
    new Promise<void>((resolve) => {
      nextRef.current = resolve
      setRevealed(value)
    })

  /**
   * Ten draws plus one free (task #1047): the server draws all eleven at once, then each is
   * shown with the full turn of the handle, one after another, and a summary at the end.
   */
  const drawBundle = (machine: Gacha) => {
    void machines.runForRow(machine.id, 'bundle', async () => {
      const key = bundleKeys.current.get(machine.id) ?? newIdempotencyKey()
      bundleKeys.current.set(machine.id, key)
      let startedAt = Date.now()
      try {
        const result = await gachaApi.bundle(family, ledger, machine.id, key)
        bundleKeys.current.delete(machine.id)
        const colors = result.draws.map((won) => colorOf(machine, won))
        for (const [index, won] of result.draws.entries()) {
          await waitForTurn(startedAt)
          await showAndWait({
            draw: won,
            color: colors[index] ?? colorOf(machine, won),
            balance: null,
            position: { index: index + 1, total: result.draws.length, bonus: won.is_bonus },
          })
          startedAt = Date.now()
        }
        setBoard((current) =>
          current === null
            ? current
            : {
                ...current,
                balance: result.balance,
                draws: [...[...result.draws].reverse(), ...current.draws],
              },
        )
        setSummary({ draws: result.draws, colors, balance: result.balance })
        await reloadFamily()
      } catch (error) {
        notify('error', t(errorMessageKey(error)))
        await reload()
      }
    })
  }

  /** A parent's trial draw: the same show and pick, with nothing spent or recorded. */
  const tryDraw = (machine: Gacha) => {
    void machines.runForRow(machine.id, 'trial', async () => {
      const startedAt = Date.now()
      try {
        const result = await gachaApi.trial(family, ledger, machine.id)
        await waitForTurn(startedAt)
        setRevealed({ draw: result, color: colorOf(machine, result), balance: null, trial: true })
      } catch (error) {
        notify('error', t(errorMessageKey(error)))
      }
    })
  }

  /** Rethrow on failure (keeps the input). */
  const save = async (design: GachaDesign, gachaId: number | null) => {
    try {
      if (gachaId === null) await gachaApi.create(family, ledger, design)
      else await gachaApi.update(family, ledger, gachaId, design)
    } catch (error) {
      notify('error', t(errorMessageKey(error)))
      throw error
    }
    notify('success', gachaId === null ? t('gacha.created') : t('common.saved'))
    setEditing(null)
    await reload()
  }

  const remove = (machine: Gacha) => {
    if (!window.confirm(t('gacha.confirmRemove', { name: machine.name }))) return
    void machines.runForRow(machine.id, 'remove', async () => {
      try {
        await gachaApi.remove(family, ledger, machine.id)
        notify('success', t('gacha.removed'))
      } catch (error) {
        notify('error', t(errorMessageKey(error)))
      }
      await reload()
    })
  }

  const toggleHandOver = (target: GachaDraw) => {
    void handOvers.runForRow(target.id, 'hand-over', async () => {
      try {
        const updated =
          target.handed_over_at === null
            ? await gachaApi.handOver(family, ledger, target.id)
            : await gachaApi.takeBackHandOver(family, ledger, target.id)
        setBoard((current) =>
          current === null
            ? current
            : { ...current, draws: current.draws.map((d) => (d.id === updated.id ? updated : d)) },
        )
      } catch (error) {
        notify('error', t(errorMessageKey(error)))
        await reload()
      }
    })
  }

  if (board === null) {
    return failed ? (
      <p className="error">{t('gacha.unavailable')}</p>
    ) : (
      <p className="loading">{t('common.loading')}</p>
    )
  }

  return (
    <div className="page page-wide">
      <div className="page-heading page-heading-row">
        <h1>{t('gacha.title', { name: board.display_name })}</h1>
        <Link className="page-heading-link" to={`/families/${family}/ledgers/${ledger}`}>
          {t('gacha.backToLedger')}
        </Link>
      </div>

      <p className="gacha-balance">
        {t('gacha.balance')} <strong>{t('points.value', { points: board.balance })}</strong>
      </p>

      {board.can_modify && (
        // Keep it open when there are none yet (the first thing to do is make one)
        <details className="card gacha-create" open={board.gachas.length === 0}>
          <summary>{t('gacha.createTitle')}</summary>
          <p className="gacha-form-hint">{t('gacha.createHint')}</p>
          <GachaForm onSubmit={(design) => save(design, null)} />
        </details>
      )}

      {board.gachas.length === 0 ? (
        <p className="gacha-empty">{board.can_modify ? t('gacha.empty') : t('gacha.emptyChild')}</p>
      ) : (
        <section className="gacha-board" aria-label={t('gacha.machinesSection')}>
          {board.gachas.map((machine) =>
            editing === machine.id ? (
              <div key={machine.id} className="card gacha-card gacha-card-editing">
                <h2 className="gacha-card-title">{t('gacha.editTitle', { name: machine.name })}</h2>
                <GachaForm
                  initial={machine}
                  onSubmit={(design) => save(design, machine.id)}
                  onCancel={() => {
                    setEditing(null)
                  }}
                />
              </div>
            ) : (
              <GachaMachineCard
                key={machine.id}
                gacha={machine}
                balance={board.balance}
                canDraw={board.can_draw}
                canModify={board.can_modify}
                pending={machines.pendingActionOf(machine.id)}
                onDraw={() => {
                  draw(machine)
                }}
                onTry={() => {
                  tryDraw(machine)
                }}
                onDrawBundle={() => {
                  drawBundle(machine)
                }}
                onEdit={() => {
                  setEditing(machine.id)
                }}
                onRemove={() => {
                  remove(machine)
                }}
              />
            ),
          )}
        </section>
      )}

      <GachaHistory
        draws={board.draws}
        canModify={board.can_modify}
        pendingOf={(drawId) => handOvers.pendingActionOf(drawId) !== null}
        onToggleHandOver={toggleHandOver}
      />

      {revealed !== null && (
        <GachaReveal
          draw={revealed.draw}
          color={revealed.color}
          balance={revealed.balance}
          {...(revealed.trial === true ? { trial: true } : {})}
          {...(revealed.position === undefined ? {} : { position: revealed.position })}
          onClose={closeReveal}
        />
      )}
      {summary !== null && (
        <GachaBundleSummary
          draws={summary.draws}
          colors={summary.colors}
          balance={summary.balance}
          onClose={closeSummary}
        />
      )}
    </div>
  )
}
