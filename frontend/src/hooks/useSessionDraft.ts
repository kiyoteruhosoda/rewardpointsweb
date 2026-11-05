/**
 * 書きかけをタブの中（sessionStorage）に残す（ADR-0058）。
 *
 * SSO で入ったログインが続けられないと、画面はログイン画面へ移り、IdP と全画面で往復してから
 * 元の画面へ戻る。React の状態は往復で消えるので、**書きかけは書くたびにここへ写しておく。**
 * 戻ってきたときに同じ鍵で読み直せば、閉じていた入力の窓もそのまま開く。
 *
 * - 値が `null` になったら（保存した・閉じた）消す
 * - サインアウトしたら全部消す（{@link clearSessionDrafts}。同じタブで別の人が入ることがある）
 * - 読めない・書けないブラウザでは、ふつうの状態としてだけ振る舞う
 */
import { useCallback, useState } from 'react'

const PREFIX = 'draft:'

function read<T>(key: string, initial: T | null): T | null {
  try {
    const raw = window.sessionStorage.getItem(PREFIX + key)
    return raw === null ? initial : (JSON.parse(raw) as T)
  } catch {
    return initial
  }
}

function write(key: string, value: unknown): void {
  try {
    if (value === null) window.sessionStorage.removeItem(PREFIX + key)
    else window.sessionStorage.setItem(PREFIX + key, JSON.stringify(value))
  } catch {
    // 残せなくても書きかけは画面に残っている
  }
}

export function useSessionDraft<T>(key: string, initial: T | null = null) {
  const [value, setValue] = useState<T | null>(() => read<T>(key, initial))
  const update = useCallback(
    (next: T | null | ((current: T | null) => T | null)) => {
      setValue((current) => {
        const resolved =
          typeof next === 'function' ? (next as (current: T | null) => T | null)(current) : next
        write(key, resolved)
        return resolved
      })
    },
    [key],
  )
  return [value, update] as const
}

/**
 * 入力欄 1 つ分の書きかけ（{@link useSessionDraft} の、空にならない版）。
 *
 * このアプリの入力の窓は欄ごとに状態を持つので、欄ごとにこれで持つ。読めなければ `initial`。
 * ⚠ **パスワードには使わない**（sessionStorage に平文で残る）。
 */
export function useSessionValue<T>(key: string, initial: T) {
  const [value, setValue] = useSessionDraft<T>(key)
  const update = useCallback(
    (next: T | ((current: T) => T)) => {
      setValue((current) => {
        const base = current ?? initial
        return typeof next === 'function' ? (next as (current: T) => T)(base) : next
      })
    },
    // `initial` は空の値（'' や []）。描くたびに作り直されても結果は同じなので見ない
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setValue],
  )
  return [value ?? initial, update] as const
}

/** 書きかけを全部消す（サインアウトしたとき）。 */
export function clearSessionDrafts(): void {
  try {
    for (const key of Object.keys(window.sessionStorage)) {
      if (key.startsWith(PREFIX)) window.sessionStorage.removeItem(key)
    }
  } catch {
    // 消せなくても、次に保存すれば上書きされる
  }
}
