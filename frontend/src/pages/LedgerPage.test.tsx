/**
 * Ledger: append-only presentation (reversals shown as pairs) and gating of modification UI.
 * Other screens show balances too, so also check the family is reloaded after recording (ADR-0021).
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { Link } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Fetched } from '../services/api'
import type {
  Correction,
  FamilyDetail,
  Ledger,
  NewTransaction,
  Transaction,
} from '../services/families'
import { familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { LedgerPage } from './LedgerPage'

const viewLedger = vi.fn<() => Promise<Fetched<Ledger>>>()
const reasonSuggestions = vi.fn<() => Promise<string[]>>()
const record = vi.fn<() => Promise<Transaction>>()
const reverse = vi.fn<() => Promise<Transaction>>()
const correct = vi.fn<(transactionId: number, entry: NewTransaction) => Promise<Correction>>()

vi.mock('../services/families', () => ({
  // Same check as the real one. The server returns a trailing Z, so appending blindly gives `...ZZ`
  parseUtc: (value: string) =>
    new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`),
  newIdempotencyKey: () => 'test-key',
  families: {
    viewLedger: () => viewLedger(),
    reasonSuggestions: () => reasonSuggestions(),
    record: () => record(),
    reverse: () => reverse(),
    correct: (_family: number, _ledger: number, transactionId: number, entry: NewTransaction) =>
      correct(transactionId, entry),
  },
}))

function transaction(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: 1,
    amount: 100,
    reason: 'おてつだい',
    occurred_at: '2026-08-01T00:00:00',
    created_at: '2026-08-01T00:00:00',
    reversal_of_id: null,
    corrects_id: null,
    is_reversed: false,
    granted_by: 'おとうさん',
    ...overrides,
  }
}

function ledger(overrides: Partial<Ledger> = {}): Fetched<Ledger> {
  return {
    data: {
      ledger_id: 20,
      family_id: 1,
      membership_id: 2,
      display_name: 'ハナ',
      balance: 100,
      can_modify: true,
      transactions: [transaction()],
      daily_bonus: null,
      ...overrides,
    },
    fetchedAt: null,
  }
}

/** Renders with a destination matching the same route, to cover moving to another child. */
function renderPage(reloadFamily = () => Promise.resolve(), family: FamilyDetail | null = null) {
  return renderWithProviders(
    <>
      <Link to="/families/1/ledgers/21">タロウ</Link>
      <LedgerPage />
    </>,
    {
      scopes: ['point:view', 'point:manage'],
      route: '/families/1/ledgers/20',
      path: '/families/:familyId/ledgers/:ledgerId',
      family,
      reloadFamily,
    },
  )
}

/** A family with rules written (on this screen they come from the family response). */
function familyWithRules(): FamilyDetail {
  return { ...familyOf('owner', [member()]), rules: 'おかたづけ 10 pt' }
}

/** Opens the correction input (target is the first row showing "Correct"). */
function startCorrection(): void {
  fireEvent.click(screen.getAllByRole('button', { name: 'Correct' })[0] as HTMLElement)
}

/** Records one addition (the form separates addition and spending by sign). */
function addPoints(): void {
  fireEvent.change(screen.getByLabelText('Points'), { target: { value: '50' } })
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'おてつだい' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add points' }))
}

describe('LedgerPage', () => {
  beforeEach(() => {
    viewLedger.mockReset()
    reasonSuggestions.mockReset()
    record.mockReset()
    reverse.mockReset()
    correct.mockReset()
    reasonSuggestions.mockResolvedValue([])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  describe('family rules (ADR-0027)', () => {
    it('shows them below the record input when written (cannot be edited here)', async () => {
      viewLedger.mockResolvedValue(ledger())
      renderPage(() => Promise.resolve(), familyWithRules())

      expect(await screen.findByText('おかたづけ 10 pt')).toBeInTheDocument()
      // They are edited in family settings. No input on this screen
      expect(screen.queryByRole('textbox', { name: 'Family rules' })).not.toBeInTheDocument()
    })

    it('shows the same text to someone who cannot modify (the child)', async () => {
      viewLedger.mockResolvedValue(ledger({ can_modify: false }))
      renderPage(() => Promise.resolve(), familyWithRules())

      expect(await screen.findByText('おかたづけ 10 pt')).toBeInTheDocument()
    })

    it('shows nothing when none are written', async () => {
      viewLedger.mockResolvedValue(ledger())
      renderPage(() => Promise.resolve(), familyOf('owner', [member()]))

      await screen.findByText('100 pt')
      expect(screen.queryByText('Family rules')).not.toBeInTheDocument()
    })
  })

  it('shows balance, history and who recorded', async () => {
    viewLedger.mockResolvedValue(ledger())
    renderPage()

    expect(await screen.findByText('100 pt')).toBeInTheDocument()
    expect(screen.getByText('+100 pt')).toBeInTheDocument()
    expect(screen.getByText('おとうさん')).toBeInTheDocument()
  })

  it('hides modification UI when can_modify is false', async () => {
    viewLedger.mockResolvedValue(ledger({ can_modify: false }))
    renderPage()

    await screen.findByText('100 pt')
    expect(screen.queryByRole('button', { name: 'Add points' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument()
    expect(
      screen.getByText('You can see these points, but only your parents can change them.'),
    ).toBeInTheDocument()
  })

  it('shows reversed and reversal rows as a pair, neither reversible', async () => {
    viewLedger.mockResolvedValue(
      ledger({
        balance: 0,
        transactions: [
          transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
          transaction({ id: 1, is_reversed: true }),
        ],
      }),
    )
    renderPage()

    await screen.findByText('0 pt')
    // The original row stays, and both are listed
    expect(screen.getByText(/\(undone\)/)).toBeInTheDocument()
    expect(screen.getByText(/\(undo\)/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument()
  })

  it('shows reverse only on rows not yet reversed', async () => {
    viewLedger.mockResolvedValue(ledger())
    renderPage()

    expect(await screen.findByRole('button', { name: 'Undo' })).toBeInTheDocument()
  })

  it('shows points needed to reach 0 on a negative balance', async () => {
    viewLedger.mockResolvedValue(ledger({ balance: -30 }))
    renderPage()

    expect(await screen.findByText('-30 pt')).toBeInTheDocument()
    expect(screen.getByText('30 pt short of zero.')).toBeInTheDocument()
  })

  it('offers frequently used reasons as input suggestions', async () => {
    viewLedger.mockResolvedValue(ledger())
    reasonSuggestions.mockResolvedValue(['おてつだい', 'そうじ'])
    renderPage()

    await screen.findByText('100 pt')
    const options = document.querySelectorAll('datalist option')
    expect([...options].map((option) => option.getAttribute('value'))).toEqual([
      'おてつだい',
      'そうじ',
    ])
  })

  it('can record without suggestions (free input)', async () => {
    viewLedger.mockResolvedValue(ledger())
    reasonSuggestions.mockRejectedValue(new Error('offline'))
    renderPage()

    expect(await screen.findByRole('button', { name: 'Add points' })).toBeInTheDocument()
    expect(document.querySelectorAll('datalist option')).toHaveLength(0)
  })

  it('says so when there is no history', async () => {
    viewLedger.mockResolvedValue(ledger({ balance: 0, transactions: [] }))
    renderPage()

    expect(await screen.findByText('Nothing recorded yet.')).toBeInTheDocument()
  })

  it('shows the last fetch time (offline may show stale cache)', async () => {
    viewLedger.mockResolvedValue({
      ...ledger(),
      fetchedAt: new Date('2026-08-01T10:00:00Z'),
    })
    renderPage()

    await screen.findByText('100 pt')
    expect(screen.getByText(/As of /)).toBeInTheDocument()
  })

  it('hides the time row when the response time is unreadable', async () => {
    viewLedger.mockResolvedValue(ledger())
    renderPage()

    await screen.findByText('100 pt')
    expect(screen.queryByText(/As of /)).not.toBeInTheDocument()
  })

  it('reloads both ledger and family after recording (no stale balances elsewhere)', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockResolvedValue(ledger({ balance: 150 }))
    record.mockResolvedValue(transaction({ id: 2, amount: 50 }))
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(reloadFamily)

    await screen.findByText('100 pt')
    addPoints()

    expect(await screen.findByText('150 pt')).toBeInTheDocument()
    expect(reloadFamily).toHaveBeenCalled()
  })

  it('reloads the family after a reversal too (balances drop on every screen)', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockResolvedValue(ledger({ balance: 0 }))
    reverse.mockResolvedValue(transaction({ id: 2, amount: -100, reversal_of_id: 1 }))
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(reloadFamily)

    await screen.findByText('100 pt')
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))

    expect(await screen.findByText('0 pt')).toBeInTheDocument()
    expect(reloadFamily).toHaveBeenCalled()
  })

  it('does not reload when recording fails (no phantom record)', async () => {
    viewLedger.mockResolvedValue(ledger())
    record.mockRejectedValue(new Error('offline'))
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(reloadFamily)

    await screen.findByText('100 pt')
    addPoints()

    await waitFor(() => {
      expect(record).toHaveBeenCalled()
    })
    expect(reloadFamily).not.toHaveBeenCalled()
    expect(viewLedger).toHaveBeenCalledTimes(1)
  })

  it('reloads on return (shows points added on another device)', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockResolvedValue(ledger({ balance: 150 }))
    renderPage()

    await screen.findByText('100 pt')
    fireEvent(document, new Event('visibilitychange'))

    expect(await screen.findByText('150 pt')).toBeInTheDocument()
  })

  it('keeps the shown balance when reloading fails', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockRejectedValue(new Error('offline'))
    renderPage()

    await screen.findByText('100 pt')
    fireEvent(document, new Event('visibilitychange'))

    await waitFor(() => {
      expect(viewLedger).toHaveBeenCalledTimes(2)
    })
    expect(screen.getByText('100 pt')).toBeInTheDocument()
    expect(screen.queryByText('These points could not be loaded.')).not.toBeInTheDocument()
  })

  it('refetches suggestions after a correction (no picking the fixed typo again)', async () => {
    viewLedger.mockResolvedValue(ledger())
    reasonSuggestions.mockResolvedValueOnce(['おてつだいい']).mockResolvedValue(['おてつだい'])
    correct.mockResolvedValue({
      reversal: transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
      correction: transaction({ id: 3, corrects_id: 1 }),
    })
    renderPage()

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(reasonSuggestions).toHaveBeenCalledTimes(2)
    })
    const options = document.querySelectorAll('datalist option')
    expect([...options].map((option) => option.getAttribute('value'))).toEqual(['おてつだい'])
  })

  it('choosing correct swaps in an input prefilled with the original', async () => {
    viewLedger.mockResolvedValue(
      ledger({ transactions: [transaction({ amount: -60, reason: 'おかし' })] }),
    )
    renderPage()

    await screen.findByText('-60 pt')
    startCorrection()

    // The sign is a radio, so the input holds the absolute value; the kind follows the original
    expect(await screen.findByLabelText('Points')).toHaveValue(60)
    expect(screen.getByRole('radio', { name: 'Used points' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Added points' })).not.toBeChecked()
    expect(screen.getByLabelText('Reason')).toHaveValue('おかし')
    // It replaces the record input (no confusion about which one you are typing into)
    expect(screen.queryByRole('button', { name: 'Add points' })).not.toBeInTheDocument()
  })

  it('sends the correction targeting that record with the fixed content and sign', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockResolvedValue(ledger({ balance: 50 }))
    correct.mockResolvedValue({
      reversal: transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
      correction: transaction({ id: 3, amount: 50, corrects_id: 1 }),
    })
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(reloadFamily)

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.change(screen.getByLabelText('Points'), { target: { value: '50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    expect(await screen.findByText('50 pt')).toBeInTheDocument()
    expect(correct).toHaveBeenCalledWith(1, {
      amount: 50,
      reason: 'おてつだい',
      idempotencyKey: 'test-key',
    })
    // Balances are the same on every screen, so the family is reloaded too (ADR-0021)
    expect(reloadFamily).toHaveBeenCalled()
    // Once it succeeds, the input returns to recording
    expect(await screen.findByRole('button', { name: 'Add points' })).toBeInTheDocument()
  })

  it('fixing a spending record sends it as spending', async () => {
    viewLedger.mockResolvedValue(ledger({ transactions: [transaction({ amount: -60 })] }))
    correct.mockResolvedValue({
      reversal: transaction({ id: 2, amount: 60, reversal_of_id: 1 }),
      correction: transaction({ id: 3, amount: -40, corrects_id: 1 }),
    })
    renderPage()

    await screen.findByText('-60 pt')
    startCorrection()
    fireEvent.change(screen.getByLabelText('Points'), { target: { value: '40' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(correct).toHaveBeenCalledWith(1, expect.objectContaining({ amount: -40 }))
    })
  })

  it('a wrong sign can be re-saved as spending', async () => {
    viewLedger.mockResolvedValue(ledger())
    correct.mockResolvedValue({
      reversal: transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
      correction: transaction({ id: 3, amount: -100, corrects_id: 1 }),
    })
    renderPage()

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.click(screen.getByRole('radio', { name: 'Used points' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(correct).toHaveBeenCalledWith(1, expect.objectContaining({ amount: -100 }))
    })
  })

  it('keeps the input open when a correction fails (no retyping the fix)', async () => {
    viewLedger.mockResolvedValue(ledger())
    correct.mockRejectedValue(new Error('offline'))
    renderPage()

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.change(screen.getByLabelText('Points'), { target: { value: '50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      expect(correct).toHaveBeenCalled()
    })
    expect(screen.getByLabelText('Points')).toHaveValue(50)
    expect(viewLedger).toHaveBeenCalledTimes(1)
  })

  it('cancel returns to the record input', async () => {
    viewLedger.mockResolvedValue(ledger())
    renderPage()

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(await screen.findByRole('button', { name: 'Add points' })).toBeInTheDocument()
    expect(correct).not.toHaveBeenCalled()
  })

  it('marks reversal and correction rows recognisably', async () => {
    viewLedger.mockResolvedValue(
      ledger({
        balance: 50,
        transactions: [
          transaction({ id: 3, amount: 50, corrects_id: 1 }),
          transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
          transaction({ id: 1, is_reversed: true }),
        ],
      }),
    )
    renderPage()

    await screen.findByText('50 pt')
    expect(screen.getByText(/\(correction\)/)).toBeInTheDocument()
    expect(screen.getByText(/\(undo\)/)).toBeInTheDocument()
    // Only rows that are neither reversals nor reversed can be fixed (here the one corrected row)
    expect(screen.getAllByRole('button', { name: 'Correct' })).toHaveLength(1)
  })

  it('keeps the input when recording fails (can resend with the same key)', async () => {
    viewLedger.mockResolvedValue(ledger())
    record.mockRejectedValue(new Error('offline'))
    renderPage()

    await screen.findByText('100 pt')
    addPoints()

    await waitFor(() => {
      expect(record).toHaveBeenCalled()
    })
    expect(screen.getByLabelText('Points')).toHaveValue(50)
    expect(screen.getByLabelText('Reason')).toHaveValue('おてつだい')
  })

  it('does not keep showing the previous balance while moving to another child', async () => {
    viewLedger
      .mockResolvedValueOnce(ledger())
      .mockReturnValue(new Promise<Fetched<Ledger>>(() => undefined))
    renderPage()

    await screen.findByText('100 pt')
    fireEvent.click(screen.getByRole('link', { name: 'タロウ' }))

    expect(screen.queryByText('100 pt')).not.toBeInTheDocument()
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })
})
