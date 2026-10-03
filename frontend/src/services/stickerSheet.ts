/**
 * シール帳（ADR-0042）の並べ方と、1 枚ごとの見た目の決め方。
 *
 * どちらも純粋な計算で、サーバーには何も持たせない。同じカードの同じ番号は、
 * どの端末で開いても同じ形・同じ色・同じ傾きになる（読み直すたびにシールが
 * 貼り替わって見えないように）。
 */

/** 横に並べる数の上限。これ以上は狭い画面でマスが指より小さくなる。 */
const MAX_COLUMNS = 10

/** 横に何マス並べるか。 */
export function gridColumns(count: number): number {
  // 5 マスまでは 1 行に並べる（2 行に割ると、まばらで達成までの道のりが読みにくい）
  if (count <= 5) return Math.max(1, count)
  let best = { columns: MAX_COLUMNS, score: Number.POSITIVE_INFINITY }
  for (let columns = 3; columns <= MAX_COLUMNS; columns++) {
    const rows = Math.ceil(count / columns)
    // 余るマス（空いたままの枠）を嫌い、カードに収まる横長（およそ 8:5）に寄せる
    const empty = rows * columns - count
    const score = empty * 2 + Math.abs(columns - rows * 1.6)
    if (score < best.score) best = { columns, score }
  }
  return best.columns
}

export type StickerShape = 'star' | 'flower' | 'heart' | 'smile' | 'clover' | 'sparkle'

const SHAPES: StickerShape[] = ['star', 'flower', 'heart', 'smile', 'clover', 'sparkle']

/** シールの色。白い縁取りの上に載るので、白背景で沈まない濃さにしてある。 */
export const STICKER_COLORS = ['#ff7a2f', '#f2a900', '#16a57a', '#2f8cf0', '#8a5cf0', '#f04d8a']

export interface StickerLook {
  shape: StickerShape
  color: string
  /** 傾き（度）。手で貼ったように、1 枚ずつ少しずらす。 */
  tilt: number
}

/** カードと番号から、見た目を 1 つに決める。 */
export function stickerLook(eventId: number, number: number): StickerLook {
  const hash = Math.imul(eventId, 2654435761) ^ Math.imul(number, 40503)
  const mixed = (hash ^ (hash >>> 13)) >>> 0
  return {
    // 形は番号で巡らせる（隣どうしが同じ形にならない）。色はカードごとにずらす
    shape: SHAPES[(number - 1 + eventId) % SHAPES.length] ?? 'star',
    color: STICKER_COLORS[mixed % STICKER_COLORS.length] ?? '#ff7a2f',
    tilt: (mixed % 25) - 12,
  }
}
