/**
 * Counts the time left until an event's deadline (ADR-0043).
 *
 * The deadline arrives as a date only (`YYYY-MM-DD`). `new Date('2026-10-03')` is read as 00:00 UTC,
 * which is 9:00 the previous day in Japan, so split year, month and day and count on **the device's calendar**.
 * The server decides whether it has expired (`is_expired`). This only computes "days left".
 */

/** Date on the device's calendar (`YYYY-MM-DD`). Same form as an `<input type="date">` value. */
export function localDate(moment: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${moment.getFullYear()}-${pad(moment.getMonth() + 1)}-${pad(moment.getDate())}`
}

function dayNumber(value: string): number {
  const [year = 0, month = 1, day = 1] = value.split('-').map(Number)
  return Date.UTC(year, month - 1, day) / 86_400_000
}

/** Days from *today* to *deadline* (0 on the deadline day, negative once past). */
export function daysUntil(deadline: string, today: string): number {
  return Math.round(dayNumber(deadline) - dayNumber(today))
}

/** Days left at which the deadline counts as near (the color changes at or below this). */
export const DEADLINE_SOON_DAYS = 2
