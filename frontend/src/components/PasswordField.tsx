/**
 * パスワード入力欄。伏せ字の中身を一時的に見せる切り替えを備える。
 *
 * 打ち間違えても気付けないのが伏せ字の欠点なので、入力欄の右端に目のボタンを置き、
 * 押しているあいだではなく「押すたびに」表示・非表示を入れ替える（片手で持つ端末でも
 * 押しっぱなしにしなくて済む）。表示状態はこの部品の中だけに持ち、画面を移ると必ず
 * 伏せ字へ戻る。
 *
 * 見出しは `label`（縦積みのフォーム）か `placeholder`（横並びのフォーム）のどちらかで
 * 渡す。ボタンは `<label>` の外に置く。中に入れると押した先で入力欄が反応してしまう。
 */
import { useId, useState } from 'react'

import { useI18n } from '../i18n'

interface Props {
  /** 入力欄の上に出す見出し。横並びのフォームでは `placeholder` を使う。 */
  label?: string
  /** 見出しを置けないときの代わりの文言。 */
  placeholder?: string
  value: string
  onChange: (value: string) => void
  /** ブラウザ・パスワード管理ソフトへの用途の伝達（`current-password` 等）。 */
  autoComplete?: string
  minLength?: number
  required?: boolean
}

/** 目のかたち。伏せているあいだは斜線を重ねる。 */
function EyeIcon({ crossed }: { crossed: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M1.8 12S5.6 5.8 12 5.8 22.2 12 22.2 12 18.4 18.2 12 18.2 1.8 12 1.8 12Z" />
      <circle cx="12" cy="12" r="3.1" />
      {crossed && <path d="M4 20 20 4" />}
    </svg>
  )
}

export function PasswordField({
  label,
  placeholder,
  value,
  onChange,
  autoComplete,
  minLength,
  required,
}: Props) {
  const { t } = useI18n()
  const [visible, setVisible] = useState(false)
  const [previous, setPrevious] = useState(value)
  const id = useId()

  // 送信に成功した画面は入力欄を空へ戻す（部品は置かれたまま）。表示にしたままだと
  // 次に打つパスワードが最初から見えてしまうので、値が空へ変わった時点で伏せ字へ戻す。
  // 「空になった瞬間」だけを見る。空かどうかで判定すると、何も打っていない欄で先に
  // 表示を押せなくなる。
  if (previous !== value) {
    setPrevious(value)
    if (value === '') setVisible(false)
  }

  return (
    <div className="password-field">
      {label !== undefined && <label htmlFor={id}>{label}</label>}
      <div className="password-field-control">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
          }}
          placeholder={placeholder}
          autoComplete={autoComplete}
          minLength={minLength}
          required={required}
        />
        <button
          type="button"
          className="password-field-toggle"
          /* 押した結果ではなく、押すと何が起きるかを読み上げる。 */
          aria-label={visible ? t('common.hidePassword') : t('common.showPassword')}
          aria-controls={id}
          onClick={() => {
            setVisible((prev) => !prev)
          }}
        >
          <EyeIcon crossed={visible} />
        </button>
      </div>
    </div>
  )
}
