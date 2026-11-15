/**
 * Artwork for the pet (ADR-0061): an egg, then a creature that gets bigger and gains features
 * with each stage. Drawn in SVG and shipped with the app (no image service).
 *
 * Colours are bright and fixed per species (no orange), with a dark outline so the shape reads
 * on both light and dark backgrounds. Decoration only: the screen says the stage in text.
 */
import type { ReactElement } from 'react'

import type { PetSpecies } from '../services/pet'

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
  if (stage < 3) return null
  switch (species) {
    case 'cat':
      return (
        <path
          d="M 52 40 Q 96 30 84 -10 Q 80 -24 70 -18"
          fill="none"
          {...stroke}
          strokeWidth={14}
          stroke={palette.body}
        />
      )
    case 'rabbit':
      return <circle cx="56" cy="44" r="16" fill={palette.belly} {...stroke} />
    case 'bird':
      return (
        <g fill={palette.body} {...stroke}>
          <path d="M -54 0 Q -96 10 -78 46 Q -64 30 -50 30 Z" />
          <path d="M 54 0 Q 96 10 78 46 Q 64 30 50 30 Z" />
        </g>
      )
    case 'dragon':
      return stage >= 4 ? (
        <g fill={palette.accent} opacity="0.9" {...stroke}>
          <path d="M -46 -10 L -100 -40 L -88 -6 L -104 6 L -84 18 L -54 22 Z" />
          <path d="M 46 -10 L 100 -40 L 88 -6 L 104 6 L 84 18 L 54 22 Z" />
        </g>
      ) : (
        <path d="M 50 40 Q 90 50 92 20 L 80 26" fill={palette.body} {...stroke} />
      )
  }
}

function Face({ species, palette }: { species: PetSpecies; palette: Palette }) {
  return (
    <g>
      <ellipse cx="-20" cy="-8" rx="7" ry="9" fill={OUTLINE} />
      <ellipse cx="20" cy="-8" rx="7" ry="9" fill={OUTLINE} />
      <circle cx="-17" cy="-12" r="2.6" fill="#ffffff" />
      <circle cx="23" cy="-12" r="2.6" fill="#ffffff" />
      <ellipse cx="-36" cy="10" rx="9" ry="6" fill={palette.accent} opacity="0.55" />
      <ellipse cx="36" cy="10" rx="9" ry="6" fill={palette.accent} opacity="0.55" />
      {species === 'bird' ? (
        <path d="M -9 6 L 9 6 L 0 18 Z" fill={palette.accent} {...stroke} strokeWidth={3} />
      ) : (
        <path
          d="M -9 8 Q -4 14 0 9 Q 4 14 9 8"
          fill="none"
          stroke={OUTLINE}
          strokeWidth={3.5}
          strokeLinecap="round"
        />
      )}
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

function Creature({ species, stage }: { species: PetSpecies; stage: number }) {
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
      <Face species={species} palette={palette} />
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

interface Props {
  species: PetSpecies | null
  stage: number
  /** Shown bigger and bouncing on the celebration. */
  className?: string
}

export function PetArt({ species, stage, className }: Props) {
  const scale = SCALE[Math.min(stage, SCALE.length - 1)] ?? 1
  // Until a species is chosen, the pet stays drawn as an egg (it still grows underneath)
  const hatched = species !== null && stage > 0
  return (
    <svg
      className={className === undefined ? 'pet-art' : `pet-art ${className}`}
      viewBox="-110 -130 220 230"
      aria-hidden="true"
      focusable="false"
    >
      <ellipse cx="0" cy="92" rx="70" ry="8" className="pet-art-shadow" />
      {hatched ? (
        <>
          <g transform={`translate(0 ${stage === 1 ? -8 : 88 - 68 * scale}) scale(${scale})`}>
            <Creature species={species} stage={stage} />
            {stage === SCALE.length - 1 && <Crown />}
          </g>
          {stage === 1 && <Shell />}
        </>
      ) : (
        <Egg palette={species === null ? null : PALETTES[species]} />
      )}
    </svg>
  )
}
