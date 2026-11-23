/**
 * Artwork for the pet (ADR-0061): an egg, then a creature that gets bigger and gains features
 * with each stage. Drawn in SVG and shipped with the app (no image service).
 *
 * Colours are bright and fixed per species (no orange), with a dark outline so the shape reads
 * on both light and dark backgrounds. Decoration only: the screen says the stage, the mood and
 * what a care did in text.
 *
 * Motion (task #1128) is CSS only, keyed off class names on the parts: the eyes blink and the
 * tail wags while idle, each care plays its own move (munching, hearts, a hop, bubbles), and an
 * egg cracks open when it hatches. All of it stops under prefers-reduced-motion.
 */
import type { ReactElement } from 'react'

import type { PetCareKind, PetMoodLevel, PetSpecies } from '../services/pet'

interface Palette {
  body: string
  belly: string
  accent: string
}

const PALETTES: Record<PetSpecies, Palette> = {
  cat: { body: '#a98bff', belly: '#ece4ff', accent: '#ff8fc3' },
  rabbit: { body: '#ffb3d4', belly: '#fff3f8', accent: '#ff6fa8' },
  bird: { body: '#ffd84d', belly: '#fff6c9', accent: '#ff6fa8' },
  dragon: { body: '#5fd39a', belly: '#dcf8e8', accent: '#9b6bff' },
}

const OUTLINE = '#2b2540'
const NEUTRAL_EGG = '#f3efe6'

/** Size of the creature per stage (0 is the egg, drawn separately). */
const SCALE = [0, 0.5, 0.66, 0.8, 0.92, 1] as const

const stroke = { stroke: OUTLINE, strokeWidth: 4, strokeLinejoin: 'round' as const }

function Egg({ palette }: { palette: Palette | null }) {
  const spot = palette?.body ?? '#c9c2b3'
  return (
    <g className="pet-art-egg">
      <path
        d="M 0 -78 C 46 -78 66 -6 62 28 C 58 64 32 84 0 84 C -32 84 -58 64 -62 28 C -66 -6 -46 -78 0 -78 Z"
        fill={NEUTRAL_EGG}
        {...stroke}
      />
      <ellipse cx="-24" cy="-14" rx="12" ry="9" fill={spot} />
      <ellipse cx="22" cy="20" rx="15" ry="11" fill={spot} />
      <ellipse cx="-10" cy="48" rx="9" ry="7" fill={spot} />
      <ellipse cx="-26" cy="-44" rx="9" ry="16" fill="#ffffff" opacity="0.7" />
    </g>
  )
}

function Ears({
  species,
  palette,
}: {
  species: PetSpecies
  palette: Palette
}): ReactElement | null {
  switch (species) {
    case 'cat':
      return (
        <g>
          <path d="M -50 -34 L -40 -84 L -10 -52 Z" fill={palette.body} {...stroke} />
          <path d="M 50 -34 L 40 -84 L 10 -52 Z" fill={palette.body} {...stroke} />
          <path d="M -40 -46 L -38 -70 L -22 -54 Z" fill={palette.accent} />
          <path d="M 40 -46 L 38 -70 L 22 -54 Z" fill={palette.accent} />
        </g>
      )
    case 'rabbit':
      return (
        <g>
          <ellipse cx="-22" cy="-82" rx="14" ry="38" fill={palette.body} {...stroke} />
          <ellipse cx="22" cy="-82" rx="14" ry="38" fill={palette.body} {...stroke} />
          <ellipse cx="-22" cy="-80" rx="6" ry="26" fill={palette.accent} opacity="0.7" />
          <ellipse cx="22" cy="-80" rx="6" ry="26" fill={palette.accent} opacity="0.7" />
        </g>
      )
    case 'bird':
      return (
        <g fill={palette.body} {...stroke}>
          <ellipse cx="-8" cy="-60" rx="7" ry="16" transform="rotate(-20 -8 -60)" />
          <ellipse cx="6" cy="-62" rx="7" ry="18" transform="rotate(15 6 -62)" />
        </g>
      )
    case 'dragon':
      return (
        <g fill={palette.accent} {...stroke}>
          <path d="M -34 -46 Q -46 -78 -24 -84 Q -26 -64 -16 -52 Z" />
          <path d="M 34 -46 Q 46 -78 24 -84 Q 26 -64 16 -52 Z" />
        </g>
      )
  }
}

/** A small tail for the young ones (stages 1 and 2). */
function BabyTail({ species, palette }: { species: PetSpecies; palette: Palette }) {
  switch (species) {
    case 'cat':
      return (
        <path
          className="pet-art-tail"
          d="M 50 44 Q 76 40 70 18"
          fill="none"
          {...stroke}
          strokeWidth={10}
          stroke={palette.body}
          strokeLinecap="round"
        />
      )
    case 'rabbit':
      return (
        <circle className="pet-art-tail" cx="54" cy="46" r="11" fill={palette.belly} {...stroke} />
      )
    case 'bird':
      return (
        <path
          className="pet-art-tail"
          d="M 50 30 L 74 20 L 72 44 Z"
          fill={palette.body}
          {...stroke}
        />
      )
    case 'dragon':
      return (
        <path
          className="pet-art-tail"
          d="M 48 40 Q 74 48 76 26 L 66 30"
          fill={palette.body}
          {...stroke}
        />
      )
  }
}

/** Wings, tails and such that come with growing up (stage 3 and later). */
function Extras({
  species,
  palette,
  stage,
}: {
  species: PetSpecies
  palette: Palette
  stage: number
}) {
  if (stage < 3) return <BabyTail species={species} palette={palette} />
  switch (species) {
    case 'cat':
      return (
        <path
          className="pet-art-tail"
          d="M 52 40 Q 96 30 84 -10 Q 80 -24 70 -18"
          fill="none"
          {...stroke}
          strokeWidth={14}
          stroke={palette.body}
        />
      )
    case 'rabbit':
      return (
        <circle className="pet-art-tail" cx="56" cy="44" r="16" fill={palette.belly} {...stroke} />
      )
    case 'bird':
      return (
        <g className="pet-art-wings" fill={palette.body} {...stroke}>
          <path d="M -54 0 Q -96 10 -78 46 Q -64 30 -50 30 Z" />
          <path d="M 54 0 Q 96 10 78 46 Q 64 30 50 30 Z" />
        </g>
      )
    case 'dragon':
      return stage >= 4 ? (
        <g className="pet-art-wings" fill={palette.accent} opacity="0.9" {...stroke}>
          <path d="M -46 -10 L -100 -40 L -88 -6 L -104 6 L -84 18 L -54 22 Z" />
          <path d="M 46 -10 L 100 -40 L 88 -6 L 104 6 L 84 18 L 54 22 Z" />
        </g>
      ) : (
        <path
          className="pet-art-tail"
          d="M 50 40 Q 90 50 92 20 L 80 26"
          fill={palette.body}
          {...stroke}
        />
      )
  }
}

const TEAR = '#5ab8ff'

function Eyes({ mood }: { mood: PetMoodLevel }) {
  if (mood === 'happy') {
    // Smiling eyes: upturned arcs
    return (
      <g
        className="pet-art-eyes"
        fill="none"
        stroke={OUTLINE}
        strokeWidth={4}
        strokeLinecap="round"
      >
        <path d="M -28 -6 Q -20 -18 -12 -6" />
        <path d="M 12 -6 Q 20 -18 28 -6" />
      </g>
    )
  }
  const look = mood === 'lonely' ? 3 : 0
  return (
    <g className="pet-art-eyes">
      <ellipse cx="-20" cy={-8 + look} rx="7" ry={mood === 'lonely' ? 7 : 9} fill={OUTLINE} />
      <ellipse cx="20" cy={-8 + look} rx="7" ry={mood === 'lonely' ? 7 : 9} fill={OUTLINE} />
      <circle cx="-17" cy={-12 + look} r="2.6" fill="#ffffff" />
      <circle cx="23" cy={-12 + look} r="2.6" fill="#ffffff" />
    </g>
  )
}

function Mouth({
  species,
  palette,
  mood,
}: {
  species: PetSpecies
  palette: Palette
  mood: PetMoodLevel
}) {
  if (species === 'bird') {
    return (
      <g className="pet-art-mouth">
        <path d="M -9 6 L 9 6 L 0 18 Z" fill={palette.accent} {...stroke} strokeWidth={3} />
      </g>
    )
  }
  const line = { fill: 'none', stroke: OUTLINE, strokeWidth: 3.5, strokeLinecap: 'round' as const }
  return (
    <g className="pet-art-mouth">
      {mood === 'happy' && <path d="M -11 7 Q 0 24 11 7 Z" {...line} fill={OUTLINE} />}
      {mood === 'calm' && <path d="M -9 8 Q -4 14 0 9 Q 4 14 9 8" {...line} />}
      {mood === 'lonely' && <path d="M -8 15 Q 0 8 8 15" {...line} />}
    </g>
  )
}

function Face({
  species,
  palette,
  mood,
}: {
  species: PetSpecies
  palette: Palette
  mood: PetMoodLevel
}) {
  return (
    <g>
      <Eyes mood={mood} />
      {mood === 'lonely' ? (
        <g>
          {/* Brows tilted up in the middle, and a tear: lonely, nothing worse */}
          <g stroke={OUTLINE} strokeWidth={3} strokeLinecap="round">
            <line x1="-28" y1="-24" x2="-12" y2="-28" />
            <line x1="28" y1="-24" x2="12" y2="-28" />
          </g>
          <path className="pet-art-tear" d="M 27 4 Q 31 12 27 15 Q 23 12 27 4 Z" fill={TEAR} />
        </g>
      ) : (
        <g>
          <ellipse
            cx="-36"
            cy="10"
            rx="9"
            ry="6"
            fill={palette.accent}
            opacity={mood === 'happy' ? 0.85 : 0.55}
          />
          <ellipse
            cx="36"
            cy="10"
            rx="9"
            ry="6"
            fill={palette.accent}
            opacity={mood === 'happy' ? 0.85 : 0.55}
          />
        </g>
      )}
      <Mouth species={species} palette={palette} mood={mood} />
      {species === 'cat' && (
        <g stroke={OUTLINE} strokeWidth={2.5} strokeLinecap="round">
          <line x1="-30" y1="2" x2="-54" y2="-2" />
          <line x1="-30" y1="8" x2="-54" y2="10" />
          <line x1="30" y1="2" x2="54" y2="-2" />
          <line x1="30" y1="8" x2="54" y2="10" />
        </g>
      )}
    </g>
  )
}

function Creature({
  species,
  stage,
  mood,
}: {
  species: PetSpecies
  stage: number
  mood: PetMoodLevel
}) {
  const palette = PALETTES[species]
  // Babies are rounder (a big head), grown-ups a little taller
  const height = stage >= 3 ? 62 : 56
  return (
    <g>
      <Extras species={species} palette={palette} stage={stage} />
      <Ears species={species} palette={palette} />
      {stage >= 2 && (
        <g fill={palette.body} {...stroke}>
          <ellipse cx="-24" cy="58" rx="16" ry="10" />
          <ellipse cx="24" cy="58" rx="16" ry="10" />
        </g>
      )}
      <ellipse cx="0" cy="4" rx="60" ry={height} fill={palette.body} {...stroke} />
      <ellipse cx="0" cy="28" rx="34" ry={height - 30} fill={palette.belly} />
      {species === 'dragon' && stage >= 2 && (
        <g fill={palette.accent}>
          <circle cx="-8" cy="40" r="4" />
          <circle cx="8" cy="48" r="4" />
        </g>
      )}
      <Face species={species} palette={palette} mood={mood} />
    </g>
  )
}

function Crown() {
  return (
    <g transform="translate(0 -66)">
      <path
        d="M -30 10 L -34 -18 L -16 -2 L 0 -24 L 16 -2 L 34 -18 L 30 10 Z"
        fill="#ffd23f"
        {...stroke}
        strokeWidth={3}
      />
      <circle cx="0" cy="-2" r="5" fill="#ff5fa2" />
    </g>
  )
}

function Shell() {
  return (
    <path
      d="M -60 20 L -44 6 L -28 22 L -12 6 L 4 22 L 20 6 L 36 22 L 50 8 L 62 22 C 58 64 32 84 0 84 C -32 84 -58 64 -60 20 Z"
      fill={NEUTRAL_EGG}
      {...stroke}
    />
  )
}

const HEART =
  'M 0 6 C -10 -2 -12 -12 -5 -14 C -2 -15 0 -12 0 -10 C 0 -12 2 -15 5 -14 C 12 -12 10 -2 0 6 Z'

/** What a care shows next to the pet while it plays. */
function CareProps({ action }: { action: PetCareKind }) {
  switch (action) {
    case 'feed':
      return (
        // The place is on an outer group: the CSS move would replace a transform on the moving one
        <g transform="translate(66 52)">
          <g className="pet-art-food">
            <path
              d="M -26 -4 L 26 -4 Q 22 22 0 22 Q -22 22 -26 -4 Z"
              fill="#5ab8ff"
              {...stroke}
              strokeWidth={3}
            />
            <path
              d="M -20 -4 Q -18 -22 0 -22 Q 18 -22 20 -4 Z"
              fill="#ffffff"
              {...stroke}
              strokeWidth={3}
            />
          </g>
        </g>
      )
    case 'pat':
      return (
        <g className="pet-art-hearts" fill="#ff5fa2" {...stroke} strokeWidth={2.5}>
          <path d={HEART} transform="translate(-52 -70) scale(1.4)" />
          <path d={HEART} transform="translate(50 -82) scale(1.8)" />
          <path d={HEART} transform="translate(6 -108) scale(1.2)" />
        </g>
      )
    case 'play':
      return (
        <g transform="translate(-74 62)">
          <g className="pet-art-ball">
            <circle r="16" fill="#ffd23f" {...stroke} strokeWidth={3} />
            <path d="M -16 0 Q 0 -8 16 0" fill="none" stroke="#9b6bff" strokeWidth={4} />
          </g>
        </g>
      )
    case 'bath':
      return (
        <g className="pet-art-bubbles" fill="#d9f1ff" stroke="#5ab8ff" strokeWidth={3}>
          <circle cx="-56" cy="10" r="12" />
          <circle cx="58" cy="-6" r="15" />
          <circle cx="-30" cy="-70" r="9" />
          <circle cx="36" cy="-80" r="11" />
          <circle cx="0" cy="40" r="8" />
        </g>
      )
  }
}

/** The egg splitting open: it wobbles, a crack runs across, and the shell falls away. */
function HatchingEgg({ palette }: { palette: Palette }) {
  return (
    <g className="pet-art-hatch-egg">
      <Egg palette={palette} />
      <path
        className="pet-art-crack"
        d="M -62 10 L -40 -6 L -24 12 L -6 -8 L 10 10 L 28 -6 L 44 10 L 62 -4"
        fill="none"
        stroke={OUTLINE}
        strokeWidth={4}
        strokeLinejoin="round"
        strokeLinecap="round"
        pathLength={1}
      />
    </g>
  )
}

interface Props {
  species: PetSpecies | null
  stage: number
  /** Shown bigger and bouncing on the celebration. */
  className?: string
  /** The face. Calm when not given (eggs, the picker, raised pets). */
  mood?: PetMoodLevel
  /** A care playing right now. Remount (change the key) to play it again. */
  action?: PetCareKind | null
  /** Blink and wag while nothing else happens. */
  idle?: boolean
  /** It has just hatched: show the egg cracking open first. */
  hatching?: boolean
}

function classNames(props: Props): string {
  const names = ['pet-art', `is-mood-${props.mood ?? 'calm'}`]
  if (props.idle === true) names.push('is-idle')
  if (props.action !== undefined && props.action !== null) names.push(`is-care-${props.action}`)
  if (props.hatching === true) names.push('is-hatching')
  if (props.className !== undefined) names.push(props.className)
  return names.join(' ')
}

export function PetArt(props: Props) {
  const { species, stage, mood = 'calm', action = null, hatching = false } = props
  const scale = SCALE[Math.min(stage, SCALE.length - 1)] ?? 1
  // Until a species is chosen, the pet stays drawn as an egg (it still grows underneath)
  const hatched = species !== null && stage > 0
  return (
    <svg
      className={classNames(props)}
      viewBox="-110 -130 220 230"
      aria-hidden="true"
      focusable="false"
    >
      <ellipse cx="0" cy="92" rx="70" ry="8" className="pet-art-shadow" />
      {hatched ? (
        <>
          <g className={hatching ? 'pet-art-hatchling' : undefined}>
            <g transform={`translate(0 ${stage === 1 ? -8 : 88 - 68 * scale}) scale(${scale})`}>
              <g className="pet-art-body">
                <Creature species={species} stage={stage} mood={mood} />
                {stage === SCALE.length - 1 && <Crown />}
              </g>
            </g>
            {stage === 1 && <Shell />}
          </g>
          {action !== null && <CareProps action={action} />}
          {hatching && <HatchingEgg palette={PALETTES[species]} />}
        </>
      ) : (
        <Egg palette={species === null ? null : PALETTES[species]} />
      )}
    </svg>
  )
}
