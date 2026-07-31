/** パスワード入力欄: 伏せ字の切り替えと、見出し・入力欄の結び付き。 */
import { fireEvent, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { PasswordField } from './PasswordField'

const SHOW_LABEL = 'Show password'
const HIDE_LABEL = 'Hide password'

/** 見出し付きの入力欄は `getByLabelText` で取れる（type が変わっても同じ）。 */
function field(): HTMLInputElement {
  return screen.getByLabelText('Password')
}

/** 値を親が持つ実際の使われ方。「clear」は送信に成功した画面の後始末に当たる。 */
function Controlled({ initial }: { initial: string }) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <PasswordField label="Password" value={value} onChange={setValue} />
      <button
        type="button"
        onClick={() => {
          setValue('')
        }}
      >
        clear
      </button>
    </>
  )
}

describe('PasswordField', () => {
  it('はじめは伏せ字にする', () => {
    renderWithProviders(<PasswordField label="Password" value="s3cret" onChange={vi.fn()} />)

    expect(field()).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: SHOW_LABEL })).toBeInTheDocument()
  })

  it('押すと中身を見せ、もう一度押すと伏せ字へ戻す', () => {
    renderWithProviders(<PasswordField label="Password" value="s3cret" onChange={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(field()).toHaveAttribute('type', 'text')

    fireEvent.click(screen.getByRole('button', { name: HIDE_LABEL }))
    expect(field()).toHaveAttribute('type', 'password')
  })

  it('切り替えボタンはフォームを送信しない（type=button）', () => {
    const onSubmit = vi.fn()
    renderWithProviders(
      <form onSubmit={onSubmit}>
        <PasswordField label="Password" value="" onChange={vi.fn()} />
      </form>,
    )

    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('入力した文字を親へ渡す', () => {
    const onChange = vi.fn()
    renderWithProviders(<PasswordField label="Password" value="" onChange={onChange} />)

    fireEvent.change(field(), { target: { value: 'typed' } })
    expect(onChange).toHaveBeenCalledWith('typed')
  })

  it('見出しの代わりに placeholder でも読み取れる（横並びのフォーム）', () => {
    renderWithProviders(<PasswordField placeholder="Password" value="" onChange={vi.fn()} />)

    expect(screen.getByPlaceholderText('Password')).toHaveAttribute('type', 'password')
  })

  it('入力欄ごとに id を分ける（同じ画面に 2 つ並べても見出しが混ざらない）', () => {
    renderWithProviders(
      <>
        <PasswordField label="Current password" value="" onChange={vi.fn()} />
        <PasswordField label="New password" value="" onChange={vi.fn()} />
      </>,
    )

    const current = screen.getByLabelText('Current password')
    const next = screen.getByLabelText('New password')
    expect(current.id).not.toBe(next.id)
  })

  it('隣の欄を見せても自分の欄は伏せたままにする', () => {
    renderWithProviders(
      <>
        <PasswordField label="Current password" value="" onChange={vi.fn()} />
        <PasswordField label="New password" value="" onChange={vi.fn()} />
      </>,
    )

    const [first] = screen.getAllByRole('button', { name: SHOW_LABEL })
    fireEvent.click(first as HTMLElement)

    expect(screen.getByLabelText('Current password')).toHaveAttribute('type', 'text')
    expect(screen.getByLabelText('New password')).toHaveAttribute('type', 'password')
  })

  it('親が値を空へ戻したら伏せ字へ戻す（送信後に次の入力が見えたままにならない）', () => {
    renderWithProviders(<Controlled initial="s3cret" />)
    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(field()).toHaveAttribute('type', 'text')

    // 送信に成功した画面のふるまい。部品は置かれたまま値だけが空へ戻る。
    fireEvent.click(screen.getByRole('button', { name: 'clear' }))
    expect(field()).toHaveAttribute('type', 'password')

    // 続けて打った文字も伏せ字のまま
    fireEvent.change(field(), { target: { value: 'next' } })
    expect(field()).toHaveAttribute('type', 'password')
  })

  it('何も打っていない欄でも先に表示へ切り替えられる', () => {
    renderWithProviders(<Controlled initial="" />)

    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(field()).toHaveAttribute('type', 'text')

    // 打ち始めても表示のまま（空だからと伏せ字へ戻さない）
    fireEvent.change(field(), { target: { value: 's' } })
    expect(field()).toHaveAttribute('type', 'text')
  })

  it('画面を作り直すと伏せ字へ戻す（表示は持ち越さない）', () => {
    function Toggleable() {
      const [mounted, setMounted] = useState(true)
      return (
        <>
          <button
            type="button"
            onClick={() => {
              setMounted((prev) => !prev)
            }}
          >
            remount
          </button>
          {mounted && <PasswordField label="Password" value="" onChange={vi.fn()} />}
        </>
      )
    }

    renderWithProviders(<Toggleable />)
    fireEvent.click(screen.getByRole('button', { name: SHOW_LABEL }))
    expect(field()).toHaveAttribute('type', 'text')

    fireEvent.click(screen.getByRole('button', { name: 'remount' }))
    fireEvent.click(screen.getByRole('button', { name: 'remount' }))
    expect(field()).toHaveAttribute('type', 'password')
  })
})
