/**
 * Display device screen (ADR-0047): pairing -> receive -> display; back to pairing if removed.
 */
import { screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type * as ApiModule from '../services/api'
import type { DisplaySessionOutcome, Fetched } from '../services/api'
import type { ClaimOutcome, StartedPairing } from '../services/display'
import type { FamilyDetail, FamilySummary, Ledger } from '../services/families'
import { familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { DisplayPage } from './DisplayPage'

const startPairing = vi.fn<(origin: string) => Promise<StartedPairing>>()
const claimPairing = vi.fn<(deviceCode: string) => Promise<ClaimOutcome>>()
const openDisplaySession = vi.fn<() => Promise<DisplaySessionOutcome>>()
const list = vi.fn<() => Promise<FamilySummary[]>>()
const view = vi.fn<() => Promise<FamilyDetail>>()
const viewLedger = vi.fn<() => Promise<Fetched<Ledger>>>()

vi.mock('../services/display', () => ({
  startPairing: (origin: string) => startPairing(origin),
  claimPairing: (deviceCode: string) => claimPairing(deviceCode),
}))

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal<typeof ApiModule>()),
  openDisplaySession: () => openDisplaySession(),
}))

vi.mock('../services/families', () => ({
  parseUtc: (value: string) =>
    new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`),
  families: {
    list: () => list(),
    view: () => view(),
    viewLedger: () => viewLedger(),
  },
}))

const STARTED: StartedPairing = {
  user_code: 'KQ7M-3XPA',
  device_code: 'device-secret',
  expires_in: 600,
  // Poll without waiting in tests
  interval: 0.01,
  qr_code: 'data:image/svg+xml;base64,AAAA',
}

function ledgerOf(balance: number): Fetched<Ledger> {
  return {
    data: {
      ledger_id: 20,
      family_id: 1,
      membership_id: 2,
      display_name: 'ハナ',
      balance,
      can_modify: false,
      transactions: [
        {
          id: 1,
          amount: 30,
          reason: 'おてつだい',
          occurred_at: '2026-10-05T00:00:00Z',
          created_at: '2026-10-05T00:00:00Z',
          reversal_of_id: null,
          corrects_id: null,
          is_reversed: false,
          granted_by: 'おとうさん',
        },
      ],
      daily_bonus: null,
    },
    fetchedAt: null,
  }
}

describe('DisplayPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    list.mockResolvedValue([
      { id: 1, name: 'ほその家', my_membership_id: 9, my_role: 'display', member_count: 2 },
    ])
    view.mockResolvedValue(
      familyOf('display', [member({ display_name: 'ハナ', can_reset_password: false })]),
    )
    viewLedger.mockResolvedValue(ledgerOf(70))
    openDisplaySession.mockResolvedValue('opened')
  })

  it('shows a code and QR without credentials, then switches to display on approval', async () => {
    startPairing.mockResolvedValue(STARTED)
    claimPairing.mockResolvedValueOnce({ kind: 'pending' }).mockResolvedValue({
      kind: 'claimed',
      credential: 'device-credential',
    })

    renderWithProviders(<DisplayPage />)

    expect(await screen.findByTestId('pairing-code')).toHaveTextContent('KQ7M-3XPA')
    expect(
      screen.getByRole('img', { name: 'QR code that opens the approval page' }),
    ).toBeInTheDocument()
    expect(startPairing).toHaveBeenCalledWith(window.location.origin)

    expect(await screen.findByRole('heading', { name: 'ほその家' })).toBeInTheDocument()
    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getByText('おてつだい')).toBeInTheDocument()
    expect(localStorage.getItem('display_credential')).toBe('device-credential')
    // No entry points to actions
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('starts over with a new code when it expires', async () => {
    startPairing
      .mockResolvedValueOnce(STARTED)
      .mockResolvedValue({ ...STARTED, user_code: 'ABCD-EFGH', interval: 60 })
    claimPairing.mockResolvedValue({ kind: 'expired' })

    renderWithProviders(<DisplayPage />)

    await waitFor(() => {
      expect(screen.getByTestId('pairing-code')).toHaveTextContent('ABCD-EFGH')
    })
  })

  it('displays without any input when credentials exist', async () => {
    localStorage.setItem('display_credential', 'device-credential')

    renderWithProviders(<DisplayPage />)

    expect(await screen.findByRole('heading', { name: 'ほその家' })).toBeInTheDocument()
    expect(startPairing).not.toHaveBeenCalled()
  })

  it('returns to the pairing screen when removed (session is removed)', async () => {
    localStorage.setItem('display_credential', 'device-credential')
    openDisplaySession.mockResolvedValue('removed')
    startPairing.mockResolvedValue({ ...STARTED, interval: 60 })

    renderWithProviders(<DisplayPage />)

    expect(await screen.findByTestId('pairing-code')).toHaveTextContent('KQ7M-3XPA')
  })

  it('keeps credentials and shows "Reconnecting…" when unreachable', async () => {
    localStorage.setItem('display_credential', 'device-credential')
    openDisplaySession.mockResolvedValue('unreachable')

    renderWithProviders(<DisplayPage />)

    expect(await screen.findByText('Reconnecting…')).toBeInTheDocument()
    expect(localStorage.getItem('display_credential')).toBe('device-credential')
    expect(startPairing).not.toHaveBeenCalled()
  })

  describe('version display (task #498)', () => {
    afterEach(() => {
      vi.unstubAllGlobals()
    })

    it('shows the running version in a corner of the screen', async () => {
      localStorage.setItem('display_credential', 'device-credential')
      vi.stubGlobal(
        'fetch',
        vi.fn(() =>
          Promise.resolve(
            new Response(JSON.stringify({ version: 'd5f51cc', git_sha: 'd5f51cc' }), {
              status: 200,
            }),
          ),
        ),
      )

      renderWithProviders(<DisplayPage />)

      await waitFor(() => {
        expect(screen.getByTestId('display-version')).toHaveTextContent('d5f51cc')
      })
    })
  })
})
