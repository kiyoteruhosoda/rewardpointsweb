/**
 * Lists the daily bonus (ADR-0024) in family settings (ADR-0027).
 *
 * What we want to see: "one input per child" and "it only affects the chosen child's ledger".
 * The amount may differ per child, so not mixing up the target ledger is the key point.
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

/** Two children (ハナ = ledger 20, タロウ = ledger 21). Only ハナ has a bonus set. */
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

  it('lists one input per child, and shows the current amount and "stop" for children with a bonus', () => {
    renderPanel()

    expect(screen.getByLabelText('Points per day for ハナ')).toHaveValue(25)
    expect(screen.getByText('25 pt are added every day.')).toBeInTheDocument()
    // A child without a bonus has an empty input and nothing to stop
    expect(screen.getByLabelText('Points per day for タロウ')).toHaveValue(null)
    expect(screen.getByText('Not set up yet.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Stop' })).toHaveLength(1)
  })

  it("sends the amount to that child's ledger and reloads the family", async () => {
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

  it("stopping is per ledger too (removes only the pressed child's setting)", async () => {
    stopDailyBonus.mockResolvedValue(undefined)
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

    await waitFor(() => {
      expect(stopDailyBonus).toHaveBeenCalledWith(1, 20)
    })
  })

  it('shows no input for participants whose ledger is not visible (parents, siblings)', () => {
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
