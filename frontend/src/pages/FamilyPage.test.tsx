/** 家族の詳細: 立場による出し分けと、兄弟の残高の隠し方。 */
import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyDetail, FamilyRole, Membership } from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { FamilyPage } from './FamilyPage'

const view = vi.fn<(id: number) => Promise<FamilyDetail>>()
const listInvitations = vi.fn<() => Promise<never[]>>()

vi.mock('../services/families', () => ({
  parseUtc: (value: string) => new Date(`${value}Z`),
  families: {
    view: (id: number) => view(id),
    listInvitations: () => listInvitations(),
  },
}))

function member(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 2,
    display_name: 'ハナ',
    role: 'child',
    is_linked: true,
    is_me: false,
    username: 'hana',
    ledger_id: 20,
    balance: 70,
    ...overrides,
  }
}

function detail(myRole: FamilyRole, memberships: Membership[]): FamilyDetail {
  return { id: 1, name: 'ほその家', my_membership_id: 1, my_role: myRole, memberships }
}

function renderPage() {
  return renderWithProviders(<FamilyPage />, {
    scopes: ['family:view'],
    route: '/families/1',
    path: '/families/:familyId',
  })
}

describe('FamilyPage', () => {
  beforeEach(() => {
    view.mockReset()
    listInvitations.mockReset()
    listInvitations.mockResolvedValue([])
  })

  it('参加者と、見える範囲の残高を出す', async () => {
    view.mockResolvedValue(detail('owner', [member()]))
    renderPage()

    expect(await screen.findByText('70 pt')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute(
      'href',
      '/families/1/ledgers/20',
    )
  })

  it('見えない台帳は残高も入り口も出さない（兄弟の残高）', async () => {
    view.mockResolvedValue(
      detail('child', [
        member({ is_me: true }),
        member({ id: 3, display_name: 'タロウ', ledger_id: null, balance: null }),
      ]),
    )
    renderPage()

    await screen.findByText('70 pt')
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'History' })).toHaveLength(1)
  })

  it('子には子の追加・招待・一時パスワードを出さない', async () => {
    view.mockResolvedValue(detail('child', [member({ is_me: true })]))
    renderPage()

    await screen.findByText('70 pt')
    expect(screen.queryByRole('button', { name: 'Add a child' })).not.toBeInTheDocument()
    expect(screen.queryByText('Invitations')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Issue a temporary password' }),
    ).not.toBeInTheDocument()
  })

  it('親には子の追加と招待を出す', async () => {
    view.mockResolvedValue(detail('parent', [member()]))
    renderPage()

    expect(await screen.findByRole('button', { name: 'Add a child' })).toBeInTheDocument()
    expect(screen.getByText('Invitations')).toBeInTheDocument()
  })

  it('除名は owner だけに出す（parent には出さない）', async () => {
    view.mockResolvedValue(detail('parent', [member()]))
    renderPage()

    await screen.findByText('70 pt')
    expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument()
  })

  it('アカウント未設定の子には一時パスワードを出さない', async () => {
    view.mockResolvedValue(detail('owner', [member({ is_linked: false, username: null })]))
    renderPage()

    await screen.findByText('70 pt')
    expect(screen.getByText(/no sign-in yet/)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Issue a temporary password' }),
    ).not.toBeInTheDocument()
  })
})
