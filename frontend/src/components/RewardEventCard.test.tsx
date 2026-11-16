/**
 * Peeling a sticker is only for undoing a mis-tap (task #1049): it stays folded away under
 * "Made a mistake?" so it is not pressed by accident next to "achieved".
 */
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { RewardEvent } from '../services/rewardEvents'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { RewardEventCard } from './RewardEventCard'

function card(overrides: Partial<RewardEvent> = {}): RewardEvent {
  return {
    id: 1,
    ledger_id: 20,
    title: 'はみがき',
    reward_points: 50,
    goal_count: 5,
    stickers: [{ number: 1, stuck_at: '2026-11-16T00:00:00Z' }],
    completed_at: null,
    created_at: '2026-11-15T00:00:00Z',
    deadline: null,
    is_expired: false,
    ...overrides,
  }
}

function renderCard(event: RewardEvent, onPeel = vi.fn<() => void>()) {
  renderWithProviders(
    <RewardEventCard
      event={event}
      canModify
      pending={null}
      freshNumber={null}
      freshlyCompleted={false}
      today="2026-11-16"
      onStick={() => undefined}
      onChangeDeadline={() => Promise.resolve()}
      onPeel={onPeel}
      onRemove={() => undefined}
    />,
  )
  return onPeel
}

describe('RewardEventCard', () => {
  it('keeps peeling folded away under "Made a mistake?"', () => {
    const onPeel = renderCard(card())

    const peel = screen.getByRole('button', { name: 'Peel off the last sticker', hidden: true })
    const fold = peel.closest('details')
    expect(fold).not.toBeNull()
    expect(fold).not.toHaveAttribute('open')

    fireEvent.click(screen.getByText('Made a mistake?'))
    fireEvent.click(peel)
    expect(onPeel).toHaveBeenCalledTimes(1)
  })

  it('shows no peeling while there is no sticker yet', () => {
    renderCard(card({ stickers: [] }))

    expect(screen.queryByText('Made a mistake?')).not.toBeInTheDocument()
  })
})
