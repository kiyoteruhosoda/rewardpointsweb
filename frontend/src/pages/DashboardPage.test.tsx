/** ダッシュボード: 家族の子どもたちの残高一覧。立場で見た目を変えない。 */
import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { familyOf, member } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { DashboardPage } from './DashboardPage'

describe('DashboardPage', () => {
  it('挨拶と、子どもごとの残高カードを出す', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('owner', [
        member(),
        member({ id: 3, display_name: 'タロウ', ledger_id: 30, balance: 30 }),
      ]),
    })

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getByText('30 pt')).toBeInTheDocument()
    expect(screen.getByText('Hello, manager')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /ハナ/ })).toHaveAttribute(
      'href',
      '/families/1/ledgers/20',
    )
  })

  it('サーバーが返した順にそのまま並べる（家族が決めた並び順）', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('owner', [
        member({ id: 3, display_name: 'タロウ', ledger_id: 30, balance: 30 }),
        member(),
      ]),
    })

    // 頭文字の印を除いた見出しの並び（カードは 頭文字 + 名前 + 残高 でできている）
    const names = screen
      .getAllByRole('link')
      .map((link) => link.querySelector('.member-card-name')?.textContent)
    expect(names).toEqual(['タロウ', 'ハナ'])
  })

  it('owner でなくても同じダッシュボードを出す（招待で加わった親）', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('parent', [
        member(),
        member({ id: 3, display_name: 'タロウ', ledger_id: 30, balance: 30 }),
      ]),
    })

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.getByText('30 pt')).toBeInTheDocument()
  })

  it('台帳を持たない参加者（親）はカードに並べない', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('owner', [
        member({
          id: 1,
          display_name: 'おとうさん',
          role: 'owner',
          ledger_id: null,
          balance: null,
        }),
        member(),
      ]),
    })

    expect(screen.getByText('70 pt')).toBeInTheDocument()
    expect(screen.queryByText('おとうさん')).not.toBeInTheDocument()
  })

  it('自分自身の台帳には目印を付ける', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('child', [member({ is_me: true })]),
    })

    expect(screen.getByText(/\(you\)/)).toBeInTheDocument()
  })

  it('システム運用の情報（API ドキュメント）は出さない', () => {
    renderWithProviders(<DashboardPage />, {
      scopes: ['family:view'],
      family: familyOf('owner', [member()]),
    })

    expect(screen.queryByRole('link', { name: '/docs' })).not.toBeInTheDocument()
    expect(screen.queryByText(/openapi/i)).not.toBeInTheDocument()
  })

  it('子どもがいなければ家族の画面への案内を出す', () => {
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'] })

    expect(screen.getByRole('link', { name: 'Set up your family' })).toHaveAttribute(
      'href',
      '/families',
    )
  })

  it('読み込めなかったときは「子どもがいない」と案内しない', () => {
    renderWithProviders(<DashboardPage />, { scopes: ['family:view'], familyFailed: true })

    expect(screen.getByText('This family could not be loaded.')).toBeInTheDocument()
    expect(
      screen.queryByText('No children yet. Add them from Family settings.'),
    ).not.toBeInTheDocument()
  })

  it('family:view が無ければ空の案内も出さない（行き先が無い）', () => {
    renderWithProviders(<DashboardPage />, { scopes: ['dashboard:view'] })

    expect(screen.getByText('Hello, manager')).toBeInTheDocument()
    expect(
      screen.queryByText('No children yet. Add them from Family settings.'),
    ).not.toBeInTheDocument()
  })
})
