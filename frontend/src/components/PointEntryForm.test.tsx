/**
 * 記録の入力: 未入力のまま押したときに、押した側のボタンに関わらず理由の必須が出る。
 * 消費だけが素通りして「押しても何も起きない」状態に戻らないよう、両方から確かめる。
 */
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { PointEntryForm } from './PointEntryForm'

vi.mock('../services/families', () => ({
  newIdempotencyKey: () => 'test-key',
}))

function setUp(): { onSubmit: ReturnType<typeof vi.fn> } {
  const onSubmit = vi.fn<() => Promise<void>>().mockResolvedValue()
  renderWithProviders(<PointEntryForm onSubmit={onSubmit} reasonSuggestions={[]} />)
  return { onSubmit }
}

function typeInto(label: string, value: string): void {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

function press(name: string): void {
  fireEvent.click(screen.getByRole('button', { name }))
}

function reasonField(): HTMLInputElement {
  return screen.getByLabelText('Reason')
}

describe('PointEntryForm', () => {
  it('理由が空なら加算では送らず、必須のメッセージを出す', () => {
    const { onSubmit } = setUp()

    typeInto('Points', '50')
    press('Add points')

    expect(onSubmit).not.toHaveBeenCalled()
    expect(reasonField().validationMessage).toBe('Enter a reason.')
  })

  it('理由が空なら消費でも送らない（黙って捨てない）', () => {
    const { onSubmit } = setUp()

    typeInto('Points', '50')
    press('Use points')

    expect(onSubmit).not.toHaveBeenCalled()
    expect(reasonField().validationMessage).toBe('Enter a reason.')
  })

  it('空白だけの理由も未入力として扱う', () => {
    const { onSubmit } = setUp()

    typeInto('Points', '50')
    typeInto('Reason', '   ')
    press('Add points')

    expect(onSubmit).not.toHaveBeenCalled()
    expect(reasonField().validationMessage).toBe('Enter a reason.')
  })

  it('埋まっていれば送る。符号は押したボタンで決まる', () => {
    const { onSubmit } = setUp()

    typeInto('Points', '50')
    typeInto('Reason', 'おてつだい')
    press('Use points')

    expect(onSubmit).toHaveBeenCalledWith(-50, 'おてつだい', 'test-key')
    expect(reasonField().validationMessage).toBe('')
  })
})
