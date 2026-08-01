/** ダッシュボード: 家族の子どもたちの残高一覧。システム運用の情報は出さない。 */
import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { FamilyDetail, FamilySummary, Membership } from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { DashboardPage } from './DashboardPage'

const list = vi.fn<() => Promise<FamilySummary[]>>()
const view = vi.fn<(id: number) => Promise<FamilyDetail>>()

vi.mock('../services/families', () => ({
  families: {
    list: () => list(),
    view: (id: number) => view(id),
  },
}))

function child(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 2,
    display_name: 'ハナ',
    role: 'child',
    is_linked: false,
    is_me: false,
    username: null,
    ledger_id: 20,
    balance: 70,
    independence_proposed: false,
    ...overrides,
  }
}

function family(memberships: Membership[]): FamilyDetail {
  return { id: 1, name: 'ほその家', my_membership_id: 1, my_role: 'owner', memberships }
}

function summary(): FamilySummary {
  return { id: 1, name: 'ほその家', my_membership_id: 1, my_role: 'owner', member_count: 2 }
}

describe('DashboardPage', () => {
  beforeEach(() => {
    list.mockReset()
    view.mockReset()
  })

  it('挨拶と、子どもごとの残高カードを出す', async () => {
    list.mockResolvedValue([summary()])
    view.mockResolvedValue(
      family([child(), child({ id: 3, display_name: 'タロウ', ledger_id: 30, balance: 30 })]),
    )
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'] })

    expect(await screen.findByText('70 pt')).toBeInTheDocument()
    expect(screen.getByText('30 pt')).toBeInTheDocument()
    expect(screen.getByText('Hello, manager')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /ハナ/ })).toHaveAttribute(
      'href',
      '/families/1/ledgers/20',
    )
  })

  it('台帳を持たない参加者（親）はカードに並べない', async () => {
    list.mockResolvedValue([summary()])
    view.mockResolvedValue(
      family([
        {
          ...child(),
          id: 1,
          display_name: 'おとうさん',
          role: 'owner',
          ledger_id: null,
          balance: null,
        },
        child(),
      ]),
    )
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'] })

    await screen.findByText('70 pt')
    expect(screen.queryByText('おとうさん')).not.toBeInTheDocument()
  })

  it('自分自身の台帳には目印を付ける', async () => {
    list.mockResolvedValue([summary()])
    view.mockResolvedValue(family([child({ is_me: true })]))
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'] })

    expect(await screen.findByText(/\(you\)/)).toBeInTheDocument()
  })

  it('システム運用の情報（API ドキュメント）は出さない', async () => {
    list.mockResolvedValue([summary()])
    view.mockResolvedValue(family([child()]))
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'] })
    await screen.findByText('70 pt')

    expect(screen.queryByRole('link', { name: '/docs' })).not.toBeInTheDocument()
    expect(screen.queryByText(/openapi/i)).not.toBeInTheDocument()
  })

  it('子どもがいなければ家族の画面への案内を出す', async () => {
    list.mockResolvedValue([])
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'] })

    expect(await screen.findByRole('link', { name: 'Set up your family' })).toHaveAttribute(
      'href',
      '/families',
    )
  })

  it('読み込みに失敗しても画面は壊さない', async () => {
    list.mockRejectedValue(new Error('offline'))
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'] })

    expect(
      await screen.findByText('No children yet. Add them from the Family page.'),
    ).toBeInTheDocument()
  })

  it('family:view が無ければ一覧を取得せず、空の案内も出さない（guest 等）', async () => {
    renderWithProviders(<DashboardPage />, { scopes: ['dashboard:view'] })

    expect(await screen.findByText('Hello, manager')).toBeInTheDocument()
    expect(list).not.toHaveBeenCalled()
    expect(
      screen.queryByText('No children yet. Add them from the Family page.'),
    ).not.toBeInTheDocument()
  })
})
