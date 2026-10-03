/**
 * イベントの期限（ADR-0043）の残りを数える。
 *
 * 期限は日付だけ（`YYYY-MM-DD`）で届く。`new Date('2026-10-03')` は UTC の 0 時として
 * 読まれ、日本では前日の 9 時になるので、年・月・日を分けて **その端末の暦** で数える。
 * 期限切れかどうかはサーバーが決める（`is_expired`）。ここは「あと何日」を出すだけ。
 */

/** 端末の暦での日付（`YYYY-MM-DD`）。`<input type="date">` の値と同じ形。 */
export function localDate(moment: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${moment.getFullYear()}-${pad(moment.getMonth() + 1)}-${pad(moment.getDate())}`
}

function dayNumber(value: string): number {
  const [year = 0, month = 1, day = 1] = value.split('-').map(Number)
  return Date.UTC(year, month - 1, day) / 86_400_000
}

/** *today* から *deadline* まで何日あるか（期限の日なら 0、過ぎていれば負）。 */
export function daysUntil(deadline: string, today: string): number {
  return Math.round(dayNumber(deadline) - dayNumber(today))
}

/** 期限が迫っているとみなす残り日数（この日数以下で色を変える）。 */
export const DEADLINE_SOON_DAYS = 2
