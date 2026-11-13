/**
 * Layout of the sticker sheet (ADR-0042) and how each sticker's look is chosen.
 *
 * Both are pure computations; nothing is stored on the server. The same number on the same card
 * gets the same shape, color and tilt on any device (so stickers do not look
 * re-stuck every time the page reloads).
 */

/** Maximum number of columns. Beyond this, cells get smaller than a finger on narrow screens. */
const MAX_COLUMNS = 10

/** How many cells to put in a row. */
export function gridColumns(count: number): number {
  // Up to 5 cells go on one row (splitting into 2 rows looks sparse and hides how far to go)
  if (count <= 5) return Math.max(1, count)
  let best = { columns: MAX_COLUMNS, score: Number.POSITIVE_INFINITY }
  for (let columns = 3; columns <= MAX_COLUMNS; columns++) {
    const rows = Math.ceil(count / columns)
    // Avoid leftover (empty) cells and lean toward a landscape shape (about 8:5) that fits the card
    const empty = rows * columns - count
    const score = empty * 2 + Math.abs(columns - rows * 1.6)
    if (score < best.score) best = { columns, score }
  }
  return best.columns
}

export type StickerShape = 'star' | 'flower' | 'heart' | 'smile' | 'clover' | 'sparkle'

const SHAPES: StickerShape[] = ['star', 'flower', 'heart', 'smile', 'clover', 'sparkle']

/** Sticker colors. They sit on a white outline, so they are dark enough not to fade on a white background. */
export const STICKER_COLORS = ['#ff7a2f', '#f2a900', '#16a57a', '#2f8cf0', '#8a5cf0', '#f04d8a']

export interface StickerLook {
  shape: StickerShape
  color: string
  /** Tilt (degrees). Each sticker is offset slightly, as if stuck on by hand. */
  tilt: number
}

/** Pick a single look from the card and number. */
export function stickerLook(eventId: number, number: number): StickerLook {
  const hash = Math.imul(eventId, 2654435761) ^ Math.imul(number, 40503)
  const mixed = (hash ^ (hash >>> 13)) >>> 0
  return {
    // Shapes cycle by number (neighbors never share a shape). Colors are offset per card
    shape: SHAPES[(number - 1 + eventId) % SHAPES.length] ?? 'star',
    color: STICKER_COLORS[mixed % STICKER_COLORS.length] ?? '#ff7a2f',
    tilt: (mixed % 25) - 12,
  }
}
