/**
 * シール 1 枚の絵と、達成の判子（ADR-0042）。
 *
 * シールは「型抜きした紙」に見せる。同じ形を白で太く縁取ってから色を重ね、左上に
 * 光沢を 1 つ置く。縁取りがあるので、隣のシールや枠の線に重なっても形が読める。
 *
 * どちらも飾りなので読み上げない（枚数はカードの側が文字で伝える）。
 */
import { useId, type ReactElement } from 'react'

import type { StickerShape } from '../services/stickerSheet'

/** 中心 (0,0)・半径 R の n 角星の頂点。 */
function starPoints(spikes: number, outer: number, inner: number): string {
  const points: string[] = []
  for (let i = 0; i < spikes * 2; i++) {
    const radius = i % 2 === 0 ? outer : inner
    const angle = (Math.PI * i) / spikes - Math.PI / 2
    points.push(`${(radius * Math.cos(angle)).toFixed(1)},${(radius * Math.sin(angle)).toFixed(1)}`)
  }
  return points.join(' ')
}

const STAR = starPoints(5, 44, 20)
const SPARKLE = starPoints(4, 44, 14)
const HEART =
  'M0 38 C -6 32 -42 12 -42 -10 C -42 -28 -28 -38 -16 -38 C -6 -38 0 -30 0 -24 C 0 -30 6 -38 16 -38 C 28 -38 42 -28 42 -10 C 42 12 6 32 0 38 Z'

/** 縁取りと塗りで同じ形を 2 度描くので、形だけを返す。 */
function silhouette(shape: StickerShape): ReactElement {
  switch (shape) {
    case 'star':
      return <polygon points={STAR} strokeLinejoin="round" />
    case 'sparkle':
      return <polygon points={SPARKLE} strokeLinejoin="round" />
    case 'heart':
      return <path d={HEART} />
    case 'smile':
      return <circle r="38" />
    case 'flower':
      return (
        <g>
          {[0, 72, 144, 216, 288].map((angle) => (
            <circle key={angle} r="17" cx="0" cy="-22" transform={`rotate(${angle})`} />
          ))}
          <circle r="18" />
        </g>
      )
    case 'clover':
      return (
        <g>
          {[0, 90, 180, 270].map((angle) => (
            <circle key={angle} r="19" cx="0" cy="-19" transform={`rotate(${angle})`} />
          ))}
        </g>
      )
  }
}

/** 形ごとの中の模様（顔・花芯）。 */
function detail(shape: StickerShape): ReactElement | null {
  if (shape === 'smile') {
    return (
      <g fill="none" stroke="#3a2a1e" strokeWidth="5" strokeLinecap="round">
        <circle cx="-13" cy="-8" r="1.5" fill="#3a2a1e" />
        <circle cx="13" cy="-8" r="1.5" fill="#3a2a1e" />
        <path d="M -16 8 Q 0 24 16 8" />
      </g>
    )
  }
  if (shape === 'flower') return <circle r="10" fill="#fff4c2" />
  return null
}

interface StickerProps {
  shape: StickerShape
  color: string
}

export function Sticker({ shape, color }: StickerProps) {
  const form = silhouette(shape)
  return (
    <svg className="sticker-art" viewBox="-56 -56 112 112" aria-hidden="true" focusable="false">
      {/* 型抜きの白い縁 */}
      <g fill="#fff" stroke="#fff" strokeWidth="14" strokeLinejoin="round">
        {form}
      </g>
      <g fill={color}>{form}</g>
      {detail(shape)}
      {/* 光沢 */}
      <ellipse
        cx="-14"
        cy="-20"
        rx="11"
        ry="6"
        fill="#fff"
        opacity="0.45"
        transform="rotate(-30 -14 -20)"
      />
    </svg>
  )
}

interface HankoProps {
  label: string
}

/**
 * 達成の判子。朱肉のかすれを `feTurbulence` で付け、手で押した傾きにする。
 *
 * 文字は 2 文字（「達成」）を想定した大きさ。訳語が長い言語では縮めて収める
 * （`textLength`）。
 */
export function Hanko({ label }: HankoProps) {
  // 判子は 1 画面に何枚も並ぶので、フィルタの id を 1 枚ごとに分ける
  // （useId の値は `:` を含み、url() の中で読み違えるブラウザがあるので外す）
  const filterId = `hanko-ink-${useId().replace(/:/g, '')}`
  return (
    <svg className="hanko" viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <defs>
        <filter id={filterId} x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.9"
            numOctaves="2"
            seed="7"
            result="noise"
          />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="2.5" result="rough" />
          <feColorMatrix
            in="noise"
            type="matrix"
            values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.4 1.6"
            result="speckle"
          />
          <feComposite in="rough" in2="speckle" operator="in" />
        </filter>
      </defs>
      <g filter={`url(#${filterId})`} fill="none" stroke="currentColor">
        <circle cx="60" cy="60" r="54" strokeWidth="6" />
        <circle cx="60" cy="60" r="45" strokeWidth="2" />
        <text
          x="60"
          y="60"
          className="hanko-label"
          fill="currentColor"
          stroke="none"
          textAnchor="middle"
          dominantBaseline="central"
          {...(label.length > 2 ? { textLength: 78, lengthAdjust: 'spacingAndGlyphs' } : {})}
        >
          {label}
        </text>
      </g>
    </svg>
  )
}
