/**
 * 空白だけの入力を「未入力」としてブラウザの必須チェックに乗せる。
 *
 * `required` は 1 文字でも入っていれば通るので、空白だけの理由は素通りする。
 * 通した先で `trim()` して弾くと、画面には何も出ないまま操作が終わる（押しても
 * 何も起きない）。判定を入力欄そのものへ移し、ブラウザに必須エラーを出させる。
 *
 * 文言は `setCustomValidity()` で渡す。ブラウザ既定の未入力メッセージは閲覧者の
 * ブラウザの言語で出るため、画面で選んでいる言語と揃わない。
 */
import { useEffect, useRef } from 'react'

export function useRequiredText(value: string, message: string) {
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    ref.current?.setCustomValidity(value.trim() === '' ? message : '')
  }, [value, message])

  return ref
}
