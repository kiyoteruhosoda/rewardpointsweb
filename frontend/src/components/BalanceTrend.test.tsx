/**
 * The balance trend is drawn at the width of its frame (task #1044).
 *
 * An empty ledger shows a note instead of the frame, so the frame appears only with the first
 * record. It must be measured then too: drawn at the fallback width, it was wider than a phone
 * and the whole page shrank on iPhone.
 */
import { fireEvent, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Transaction } from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { BalanceTrend } from './BalanceTrend'

const FRAME_WIDTH = 333

/** Reports every observed element as FRAME_WIDTH wide, right away. */
class FixedWidthObserver {
  constructor(private readonly callback: ResizeObserverCallback) {}

  observe(target: Element) {
    this.callback(
      [{ target, contentRect: { width: FRAME_WIDTH } } as unknown as ResizeObserverEntry],
      this,
    )
  }

  disconnect() {}

  unobserve() {}
}

const firstRecord: Transaction = {
  id: 1,
  amount: 100,
  reason: 'おてつだい',
  occurred_at: '2026-11-16T00:00:00Z',
  created_at: '2026-11-16T00:00:00Z',
  reversal_of_id: null,
  corrects_id: null,
  is_reversed: false,
  granted_by: 'おとうさん',
}

/** Starts empty, like a new child's ledger; the button adds the first record. */
function EmptyThenRecorded() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  return (
    <>
      <button
        type="button"
        onClick={() => {
          setTransactions([firstRecord])
        }}
      >
        record
      </button>
      <BalanceTrend transactions={transactions} asOf={new Date('2026-11-16T01:00:00Z')} />
    </>
  )
}

describe('BalanceTrend', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', FixedWidthObserver)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('is drawn at the frame width once the first record arrives on an empty ledger', () => {
    const { container } = renderWithProviders(<EmptyThenRecorded />)
    expect(container.querySelector('.trend-frame')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'record' }))

    expect(container.querySelector('.trend-frame svg')).toHaveAttribute(
      'width',
      String(FRAME_WIDTH),
    )
  })
})
