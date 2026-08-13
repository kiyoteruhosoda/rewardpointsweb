/**
 * 毎日のボーナス（ADR-0024）を家族設定に並べる（ADR-0027）。
 *
 * 見たいのは「子の数だけ欄が並ぶこと」と「決めた相手の台帳にだけ効くこと」。
 * 量は子ごとに違ってよいので、送り先の台帳を取り違えないことが要になる。
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { DailyBonus } from '../services/families'
import { dailyBonus, familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { DailyBonusPanel } from './DailyBonusPanel'

const setDailyBonus =
  vi.fn<
    (familyId: number, ledgerId: number, amount: number, reason: string) => Promise<DailyBonus>
  >()
const stopDailyBonus = vi.fn<(familyId: number, ledgerId: number) => Promise<undefined>>()

vi.mock('../services/families', () => ({
  families: {
    setDailyBonus: (familyId: number, ledgerId: number, amount: number, reason: string) =>
      setDailyBonus(familyId, ledgerId, amount, reason),
    stopDailyBonus: (familyId: number, ledgerId: number) => stopDailyBonus(familyId, ledgerId),
  },
}))

/** 子 2 人（ハナ＝台帳 20・タロウ＝台帳 21）。ボーナスはハナにだけ決めてある。 */
function twoChildren() {
  return familyOf('owner', [
    member({ daily_bonus: dailyBonus({ amount: 25 }) }),
    member({
      id: 3,
      display_name: 'タロウ',
      ledger_id: 21,
      balance: 10,
      username: 'taro',
    }),
  ])
}

function renderPanel(family = twoChildren(), onChanged = () => Promise.resolve()) {
  return renderWithProviders(<DailyBonusPanel family={family} onChanged={onChanged} />)
}

describe('DailyBonusPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('子の数だけ欄を並べ、決めてある子には今の量と「やめる」を出す', () => {
    renderPanel()

    expect(screen.getByLabelText('Points per day for ハナ')).toHaveValue(25)
    expect(screen.getByText('25 pt are added every day.')).toBeInTheDocument()
    // まだ決めていない子は空欄で、やめる先も無い
    expect(screen.getByLabelText('Points per day for タロウ')).toHaveValue(null)
    expect(screen.getByText('Not set up yet.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Stop' })).toHaveLength(1)
  })

  it('決めた量はその子の台帳へ送り、家族を読み直す', async () => {
    setDailyBonus.mockResolvedValue(dailyBonus({ ledger_id: 21, amount: 30 }))
    const onChanged = vi.fn<() => Promise<void>>().mockResolvedValue(undefined)
    renderPanel(twoChildren(), onChanged)

    fireEvent.change(screen.getByLabelText('Points per day for タロウ'), {
      target: { value: '30' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Start the daily bonus' }))

    await waitFor(() => {
      expect(setDailyBonus).toHaveBeenCalledWith(1, 21, 30, 'Daily bonus')
    })
    expect(onChanged).toHaveBeenCalled()
  })

  it('やめるのも台帳ごと（押した子の設定だけを消す）', async () => {
    stopDailyBonus.mockResolvedValue(undefined)
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

    await waitFor(() => {
      expect(stopDailyBonus).toHaveBeenCalledWith(1, 20)
    })
  })

  it('台帳の見えない参加者（親・兄弟）には欄を出さない', () => {
    renderPanel(
      familyOf('owner', [
        member({
          id: 1,
          display_name: 'おとうさん',
          role: 'owner',
          ledger_id: null,
          balance: null,
        }),
        member({ id: 4, display_name: 'ジロウ', ledger_id: null, balance: null }),
      ]),
    )

    expect(
      screen.getByText('Add a child first, then you can set up a daily bonus for them.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start the daily bonus' })).not.toBeInTheDocument()
  })
})
