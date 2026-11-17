/**
 * A sticker is stuck by tapping the next empty cell; no other cell reacts.
 * Peeling a sticker is only for undoing a mis-tap (task #1049): it stays folded away under
 * "Made a mistake?".
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

function renderCard(
  event: RewardEvent,
  onPeel = vi.fn<() => void>(),
  { canModify = true, onStick = vi.fn<() => void>() } = {},
) {
  renderWithProviders(
    <RewardEventCard
      event={event}
      canModify={canModify}
      pending={null}
      freshNumber={null}
      freshlyCompleted={false}
      today="2026-11-16"
      onStick={onStick}
      onChangeDeadline={() => Promise.resolve()}
      onPeel={onPeel}
      onRemove={() => undefined}
    />,
  )
  return onPeel
}

function renderCardIn(event: RewardEvent, onStick: () => void) {
  return renderWithProviders(
    <RewardEventCard
      event={event}
      canModify
      pending={null}
      freshNumber={null}
      freshlyCompleted={false}
      today="2026-11-16"
      onStick={onStick}
      onChangeDeadline={() => Promise.resolve()}
      onPeel={() => undefined}
      onRemove={() => undefined}
    />,
  )
}

describe('RewardEventCard', () => {
  it('sticks a sticker when the next empty cell is tapped', () => {
    const onStick = vi.fn<() => void>()
    renderCard(card(), undefined, { onStick })

    const next = screen.getByRole('button', { name: 'Mark “はみがき” done once' })
    expect(next.closest('li')).toHaveTextContent('2')
    fireEvent.click(next)
    expect(onStick).toHaveBeenCalledTimes(1)
  })

  it('lets no other cell react to a tap', () => {
    const onStick = vi.fn<() => void>()
    const { container } = renderCardIn(card(), onStick)

    // Only the next cell (2) is a button; the stuck cell (1) and the later ones (3-5) are not
    const cells = container.querySelectorAll('.sticker-sheet li')
    expect(cells).toHaveLength(5)
    expect(container.querySelectorAll('.sticker-sheet button')).toHaveLength(1)
    for (const index of [0, 2, 3, 4]) {
      const cell = cells[index]
      expect(cell?.querySelector('button')).toBeNull()
      if (cell) fireEvent.click(cell)
    }
    expect(onStick).not.toHaveBeenCalled()
  })

  it('has no cell to tap for someone who only views the card', () => {
    renderCard(card(), undefined, { canModify: false })

    expect(
      screen.queryByRole('button', { name: 'Mark “はみがき” done once' }),
    ).not.toBeInTheDocument()
  })

  it('has no cell to tap once the card is complete', () => {
    renderCard(
      card({
        goal_count: 1,
        completed_at: '2026-11-16T00:00:00Z',
      }),
    )
    expect(
      screen.queryByRole('button', { name: 'Mark “はみがき” done once' }),
    ).not.toBeInTheDocument()
  })

  it('has no cell to tap on a card past its deadline', () => {
    renderCard(card({ deadline: '2026-11-15', is_expired: true }))

    expect(
      screen.queryByRole('button', { name: 'Mark “はみがき” done once' }),
    ).not.toBeInTheDocument()
  })

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
