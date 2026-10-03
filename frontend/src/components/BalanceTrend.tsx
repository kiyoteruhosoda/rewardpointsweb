/**
 * ポイントの推移（残高の折れ線）。
 *
 * 残高は記録のたびに段で変わるので、階段状の線で描く（記録と記録のあいだを斜めに
 * つなぐと、存在しない残高を通ったように見える）。線の終わりは「いま」まで伸ばす。
 *
 * 指（またはマウス）を置くと、いちばん近い記録に縦線が合い、その時点の残高と
 * 何が増減したかが出る。キーボードでは左右の矢印で記録を 1 つずつ移る。数字の
 * 一覧は同じ画面の履歴の表が受け持つ。
 */
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'

import { useI18n } from '../i18n'
import {
  balanceSeries,
  niceTicks,
  trendWindow,
  TREND_RANGES,
  type BalancePoint,
  type TrendRange,
} from '../services/balanceSeries'
import type { Transaction } from '../services/families'

interface Props {
  transactions: readonly Transaction[]
  /** 線を伸ばす先（「いま」）。台帳を読んだ時刻を渡す。 */
  asOf: Date
}

const HEIGHT = 200
const MARGIN = { top: 14, right: 14, bottom: 26, left: 46 }
/** 印を打つのは記録がこの数までのとき（多いと線が点で埋まる）。 */
const MAX_MARKERS = 40

function withSign(amount: number): string {
  return amount > 0 ? `+${amount}` : String(amount)
}

/** 描く場所の幅を追う。測れない環境（試験の jsdom 等）では既定の幅で描く。 */
function useWidth(fallback: number) {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const element = ref.current
    if (element === null || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(Math.max(240, Math.floor(entry.contentRect.width)))
    })
    observer.observe(element)
    return () => {
      observer.disconnect()
    }
  }, [])
  return [ref, width] as const
}

export function BalanceTrend({ transactions, asOf }: Props) {
  const { t, locale } = useI18n()
  const [range, setRange] = useState<TrendRange>('all')
  const [active, setActive] = useState<number | null>(null)
  const [frameRef, width] = useWidth(640)
  const series = useMemo(() => balanceSeries(transactions), [transactions])
  // 記録の時刻が読んだ時刻より先にある（端末の時計のずれ）ときも、線は最後の記録まで描く
  const now = Math.max(asOf.getTime(), series.at(-1)?.at ?? 0)
  const view = useMemo(() => trendWindow(series, range, now), [series, range, now])

  const balances = [view.startBalance, ...view.points.map((point) => point.balance)]
  const ticks = niceTicks(Math.min(0, ...balances), Math.max(10, ...balances))
  const low = ticks[0] ?? 0
  const high = ticks.at(-1) ?? 10
  const innerWidth = width - MARGIN.left - MARGIN.right
  const innerHeight = HEIGHT - MARGIN.top - MARGIN.bottom
  const x = (at: number) =>
    MARGIN.left + ((at - view.start) / (view.end - view.start || 1)) * innerWidth
  const y = (balance: number) => MARGIN.top + ((high - balance) / (high - low || 1)) * innerHeight

  const steps = view.points.map(
    (point) => `H${x(point.at).toFixed(1)}V${y(point.balance).toFixed(1)}`,
  )
  const line = `M${x(view.start).toFixed(1)},${y(view.startBalance).toFixed(1)}${steps.join('')}H${x(view.end).toFixed(1)}`
  const baseline = y(Math.max(low, Math.min(0, high)))
  const area = `${line}V${baseline.toFixed(1)}H${x(view.start).toFixed(1)}Z`

  const date = (at: number) =>
    new Date(at).toLocaleDateString(locale, { month: 'numeric', day: 'numeric' })
  const current = series.at(-1)?.balance ?? 0
  const focused: BalancePoint | null = active === null ? null : (view.points[active] ?? null)

  const nearest = (event: PointerEvent<SVGSVGElement>) => {
    if (view.points.length === 0) return
    const bounds = event.currentTarget.getBoundingClientRect()
    const pointerX = ((event.clientX - bounds.left) / bounds.width) * width
    let best = 0
    view.points.forEach((point, index) => {
      const bestPoint = view.points[best]
      if (bestPoint && Math.abs(x(point.at) - pointerX) < Math.abs(x(bestPoint.at) - pointerX))
        best = index
    })
    setActive(best)
  }

  const step = (event: KeyboardEvent<HTMLDivElement>) => {
    const last = view.points.length - 1
    if (last < 0) return
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault()
      const delta = event.key === 'ArrowLeft' ? -1 : 1
      setActive((index) =>
        Math.min(last, Math.max(0, (index ?? (delta > 0 ? -1 : last + 1)) + delta)),
      )
    } else if (event.key === 'Escape') {
      setActive(null)
    }
  }

  return (
    <section className="card trend">
      <div className="trend-heading">
        <h2>{t('trend.title')}</h2>
        <div className="segmented" role="group" aria-label={t('trend.rangeLabel')}>
          {TREND_RANGES.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={range === option}
              onClick={() => {
                setRange(option)
                setActive(null)
              }}
            >
              {t(`trend.range.${option}`)}
            </button>
          ))}
        </div>
      </div>

      {series.length === 0 ? (
        <p className="trend-empty">{t('trend.empty')}</p>
      ) : (
        <div
          ref={frameRef}
          className="trend-frame"
          tabIndex={0}
          role="img"
          aria-label={t('trend.summary', {
            from: date(view.start),
            to: date(view.end),
            points: current,
          })}
          onKeyDown={step}
          onBlur={() => {
            setActive(null)
          }}
        >
          <svg
            width={width}
            height={HEIGHT}
            viewBox={`0 0 ${width} ${HEIGHT}`}
            onPointerMove={nearest}
            onPointerDown={nearest}
            onPointerLeave={() => {
              setActive(null)
            }}
            aria-hidden="true"
          >
            {ticks.map((tick) => (
              <g key={tick} className={tick === 0 ? 'trend-grid trend-grid-zero' : 'trend-grid'}>
                <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} />
                <text x={MARGIN.left - 8} y={y(tick)} textAnchor="end" dominantBaseline="central">
                  {tick}
                </text>
              </g>
            ))}
            <path className="trend-area" d={area} />
            <path className="trend-line" d={line} />
            {view.points.length <= MAX_MARKERS &&
              view.points.map((point) => (
                <circle
                  key={`${point.at}:${point.balance}`}
                  className="trend-marker"
                  cx={x(point.at)}
                  cy={y(point.balance)}
                  r="3"
                />
              ))}
            <text className="trend-axis" x={MARGIN.left} y={HEIGHT - 6} textAnchor="start">
              {date(view.start)}
            </text>
            <text className="trend-axis" x={width - MARGIN.right} y={HEIGHT - 6} textAnchor="end">
              {date(view.end)}
            </text>
            {focused && (
              <g className="trend-focus">
                <line
                  x1={x(focused.at)}
                  x2={x(focused.at)}
                  y1={MARGIN.top}
                  y2={HEIGHT - MARGIN.bottom}
                />
                <circle cx={x(focused.at)} cy={y(focused.balance)} r="5" />
              </g>
            )}
          </svg>
          {focused && (
            <div
              className="trend-tooltip"
              style={{
                left: Math.min(Math.max(x(focused.at), 90), width - 90),
                top: Math.max(y(focused.balance) - 12, 8),
              }}
            >
              <span className="trend-tooltip-date">
                {new Date(focused.at).toLocaleString(locale)}
              </span>
              <strong>{t('points.value', { points: focused.balance })}</strong>
              <span>
                {withSign(focused.change)} {focused.reason}
              </span>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
