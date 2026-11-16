/**
 * Artwork for the gacha (ADR-0060): the capsule machine and one capsule.
 *
 * Drawn in SVG and shipped with the app (no image service). The machine body takes the theme's
 * accent colour, so it reads in both light and dark themes; capsules use a fixed set of bright
 * colours that stay vivid on either background. Both are decoration and are not read aloud
 * (the screen says the same thing in text).
 */

/** Capsule colours, picked by prize position. Bright and pop, with no orange. */
export const CAPSULE_COLORS = [
  '#ff5fa2', // pink
  '#3db8ff', // sky
  '#7bd94a', // lime
  '#ffd23f', // yellow
  '#9b6bff', // violet
  '#2fd6b5', // mint
] as const

export function capsuleColor(index: number): string {
  return CAPSULE_COLORS[index % CAPSULE_COLORS.length] ?? CAPSULE_COLORS[0]
}

/** Capsules resting in the dome: [cx, cy, colour index]. */
const DOME_CAPSULES: readonly (readonly [number, number, number])[] = [
  [40, 70, 0],
  [62, 74, 1],
  [83, 68, 2],
  [50, 52, 3],
  [74, 50, 4],
  [60, 32, 5],
  [32, 50, 2],
  [88, 46, 0],
]

interface MachineProps {
  /** Turning the handle and shaking while the draw is on its way. */
  spinning: boolean
}

export function GachaMachineArt({ spinning }: MachineProps) {
  return (
    <svg
      className={spinning ? 'gacha-machine-art is-spinning' : 'gacha-machine-art'}
      viewBox="0 0 120 156"
      aria-hidden="true"
      focusable="false"
    >
      {/* Lid */}
      <rect x="38" y="6" width="44" height="10" rx="5" className="gacha-art-body" />
      {/* Glass dome with capsules */}
      <circle cx="60" cy="56" r="44" className="gacha-art-glass" />
      <g className="gacha-art-dome-capsules">
        {DOME_CAPSULES.map(([cx, cy, color]) => (
          <g key={`${cx}-${cy}`} transform={`translate(${cx} ${cy})`}>
            <circle r="11" fill={capsuleColor(color)} />
            <path d="M -11 0 A 11 11 0 0 0 11 0 Z" fill="#ffffff" opacity="0.85" />
            <circle r="11" fill="none" stroke="rgb(0 0 0 / 18%)" strokeWidth="1.5" />
          </g>
        ))}
      </g>
      <circle cx="60" cy="56" r="44" className="gacha-art-glass-rim" />
      {/* Gloss on the glass */}
      <path d="M 30 34 Q 38 20 54 16" className="gacha-art-gloss" />
      {/* Body */}
      <rect x="16" y="94" width="88" height="56" rx="12" className="gacha-art-body" />
      <rect x="16" y="94" width="88" height="10" rx="5" className="gacha-art-body-band" />
      {/* Handle */}
      <g className="gacha-art-handle">
        <circle cx="44" cy="124" r="14" className="gacha-art-handle-base" />
        <rect x="31" y="121" width="26" height="6" rx="3" className="gacha-art-handle-bar" />
      </g>
      {/* Chute */}
      <rect x="70" y="116" width="24" height="20" rx="6" className="gacha-art-chute" />
    </svg>
  )
}

interface CapsuleProps {
  color: string
  /** Pops the two halves apart (the result screen). */
  opening: boolean
}

export function CapsuleArt({ color, opening }: CapsuleProps) {
  return (
    <svg
      className={opening ? 'gacha-capsule-art is-opening' : 'gacha-capsule-art'}
      viewBox="-60 -60 120 120"
      aria-hidden="true"
      focusable="false"
    >
      <g className="gacha-capsule-bottom">
        <path d="M -44 0 A 44 44 0 0 0 44 0 Z" fill="#ffffff" />
        <path
          d="M -44 0 A 44 44 0 0 0 44 0 Z"
          fill="none"
          stroke="rgb(0 0 0 / 20%)"
          strokeWidth="3"
        />
      </g>
      <g className="gacha-capsule-top">
        <path d="M -44 0 A 44 44 0 0 1 44 0 Z" fill={color} />
        <path
          d="M -44 0 A 44 44 0 0 1 44 0 Z"
          fill="none"
          stroke="rgb(0 0 0 / 20%)"
          strokeWidth="3"
        />
        <ellipse cx="-18" cy="-24" rx="10" ry="6" fill="#ffffff" opacity="0.6" />
      </g>
    </svg>
  )
}

/** Four-pointed sparkles around a won prize. They start twinkling *delay* seconds in. */
export function SparklesArt({ delay = 3 }: { delay?: number }) {
  const sparkle = 'M 0 -10 L 3 -3 L 10 0 L 3 3 L 0 10 L -3 3 L -10 0 L -3 -3 Z'
  const spots: readonly (readonly [number, number, number, string])[] = [
    [-70, -30, 1.4, '#ffd23f'],
    [70, -40, 1.1, '#ff5fa2'],
    [-60, 40, 0.9, '#3db8ff'],
    [64, 34, 1.3, '#7bd94a'],
    [0, -70, 1, '#9b6bff'],
  ]
  return (
    <svg
      className="gacha-sparkles"
      viewBox="-100 -100 200 200"
      aria-hidden="true"
      focusable="false"
    >
      {spots.map(([x, y, scale, color], index) => (
        <path
          key={`${x}-${y}`}
          d={sparkle}
          fill={color}
          transform={`translate(${x} ${y}) scale(${scale})`}
          style={{ animationDelay: `${delay + index * 0.08}s` }}
        />
      ))}
    </svg>
  )
}
