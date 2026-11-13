/**
 * Shared state of the user's family: what triggers fetching, and what to keep on failure.
 *
 * Screens can render with a replaced `FamilyContext` (`test-support`), so this tests
 * `FamilyProvider` itself, which builds the state.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Link, MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyDetail, FamilySummary } from '../services/families'
import { AuthContext, type AuthValue } from './AuthContext'
import { FamilyProvider, useFamily } from './FamilyContext'

const list = vi.fn<() => Promise<FamilySummary[]>>()
const view = vi.fn<() => Promise<FamilyDetail>>()

vi.mock('../services/families', () => ({
  families: {
    list: () => list(),
    view: () => view(),
  },
}))

const SUMMARY: FamilySummary = {
  id: 1,
  name: 'ほその家',
  my_membership_id: 1,
  my_role: 'owner',
  member_count: 2,
}

const DETAIL: FamilyDetail = {
  id: 1,
  name: 'ほその家',
  rules: null,
  my_membership_id: 1,
  my_role: 'owner',
  memberships: [],
}

function authValueOf(scopes: string[]): AuthValue {
  return {
    user: {
      user_id: 1,
      username: 'manager',
      display_name: 'manager',
      email: null,
      scopes,
      must_change_password: false,
      has_password: true,
      display_device: false,
    },
    loading: false,
    unreachable: false,
    login: () => Promise.resolve(),
    loginWithPasskey: () => Promise.resolve(),
    loginWithSsoTicket: () => Promise.resolve('/'),
    logout: () => undefined,
    refreshMe: () => Promise.resolve(),
    hasScope: (...codes: string[]) => codes.every((code) => scopes.includes(code)),
  }
}

/** A promise resolvable from outside, for arranging the order responses arrive in. */
interface Deferred {
  promise: Promise<FamilyDetail>
  arrive: (family: FamilyDetail) => void
}

function deferred(): Deferred {
  let resolve: (family: FamilyDetail) => void = () => {
    throw new Error('The Promise executor has not run yet')
  }
  const promise = new Promise<FamilyDetail>((settle) => {
    resolve = settle
  })
  return {
    promise,
    arrive: (family) => {
      resolve(family)
    },
  }
}

/** Flush everything, including applying the arrived responses. */
async function flush(arrival: () => void): Promise<void> {
  await act(() => {
    arrival()
    return Promise.resolve()
  })
}

/** Print the state as text (how it is rendered is each screen's job, so not checked here). */
function Probe() {
  const { family, failed, loading } = useFamily()
  if (loading) return <p>loading</p>
  return <p>{failed ? 'failed' : (family?.name ?? 'none')}</p>
}

/** Renders with a link to a destination, to cover moving between screens. */
function renderProvider(scopes = ['family:view']) {
  return render(
    <AuthContext.Provider value={authValueOf(scopes)}>
      <MemoryRouter initialEntries={['/']}>
        <FamilyProvider>
          <Link to="/families">家族設定へ</Link>
          <Probe />
        </FamilyProvider>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('FamilyProvider', () => {
  beforeEach(() => {
    list.mockReset()
    view.mockReset()
  })

  it('loads the family the user belongs to', async () => {
    list.mockResolvedValue([SUMMARY])
    view.mockResolvedValue(DETAIL)
    renderProvider()

    expect(await screen.findByText('ほその家')).toBeInTheDocument()
  })

  it('does not fetch for people without family:view', async () => {
    renderProvider([])

    expect(await screen.findByText('none')).toBeInTheDocument()
    expect(list).not.toHaveBeenCalled()
  })

  it('reports a load failure when the first fetch fails (not "not a member")', async () => {
    list.mockRejectedValue(new Error('offline'))
    renderProvider()

    expect(await screen.findByText('failed')).toBeInTheDocument()
  })

  it('reloads on return', async () => {
    list.mockResolvedValue([SUMMARY])
    view.mockResolvedValueOnce(DETAIL).mockResolvedValue({ ...DETAIL, name: 'ほその家（改名）' })
    renderProvider()

    await screen.findByText('ほその家')
    fireEvent(document, new Event('visibilitychange'))

    expect(await screen.findByText('ほその家（改名）')).toBeInTheDocument()
  })

  it('reloads on every screen change (fetching once misses points added elsewhere)', async () => {
    list.mockResolvedValue([SUMMARY])
    view.mockResolvedValueOnce(DETAIL).mockResolvedValue({ ...DETAIL, name: 'ほその家（改名）' })
    renderProvider()

    await screen.findByText('ほその家')
    fireEvent.click(screen.getByRole('link', { name: '家族設定へ' }))

    expect(await screen.findByText('ほその家（改名）')).toBeInTheDocument()
  })

  it('does not overwrite newer content with an overtaken response', async () => {
    const late = deferred()
    list.mockResolvedValue([SUMMARY])
    view
      .mockReturnValueOnce(late.promise)
      .mockResolvedValue({ ...DETAIL, name: 'ほその家（改名）' })
    renderProvider()

    // Start a second fetch before the first arrives, and the second arrives first
    fireEvent.click(screen.getByRole('link', { name: '家族設定へ' }))
    await screen.findByText('ほその家（改名）')

    await flush(() => {
      late.arrive(DETAIL)
    })

    expect(screen.getByText('ほその家（改名）')).toBeInTheDocument()
  })

  it('does not end loading even if an overtaken fetch finishes first', async () => {
    const first = deferred()
    const second = deferred()
    list.mockResolvedValue([SUMMARY])
    view.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    renderProvider()

    await waitFor(() => {
      expect(view).toHaveBeenCalledTimes(1)
    })
    fireEvent.click(screen.getByRole('link', { name: '家族設定へ' }))
    await waitFor(() => {
      expect(view).toHaveBeenCalledTimes(2)
    })

    // Ending loading with a discarded result would show the still-empty state
    // as "no family / no children" on screen
    await flush(() => {
      first.arrive(DETAIL)
    })
    expect(screen.getByText('loading')).toBeInTheDocument()

    await flush(() => {
      second.arrive({ ...DETAIL, name: 'ほその家（改名）' })
    })
    expect(screen.getByText('ほその家（改名）')).toBeInTheDocument()
  })

  it('keeps the loaded family even when a reload fails', async () => {
    list.mockResolvedValueOnce([SUMMARY]).mockRejectedValue(new Error('offline'))
    view.mockResolvedValue(DETAIL)
    renderProvider()

    await screen.findByText('ほその家')
    fireEvent(document, new Event('visibilitychange'))

    await waitFor(() => {
      expect(list).toHaveBeenCalledTimes(2)
    })
    // Balances and child entries are built from this family. Clearing it would look like
    // being removed from the family
    expect(screen.getByText('ほその家')).toBeInTheDocument()
  })
})
