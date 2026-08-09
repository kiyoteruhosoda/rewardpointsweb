/** ユーザー管理: 作成時に送る中身が API のスキーマと一致していること。 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { UsersPage } from './UsersPage'

const get = vi.fn<(path: string) => Promise<unknown>>()
const post = vi.fn<(path: string, body?: unknown) => Promise<unknown>>()
const put = vi.fn<(path: string, body?: unknown) => Promise<unknown>>()

vi.mock('../services/api', () => ({
  errorMessageKey: () => 'error.unknown_error',
  api: {
    get: (path: string) => get(path),
    post: (path: string, body?: unknown) => post(path, body),
    put: (path: string, body?: unknown) => put(path, body),
    delete: () => Promise.resolve(),
  },
}))

const ROLES = [
  { id: 1, name: 'admin' },
  { id: 3, name: 'member' },
]

/** ロールを 1 つだけ持つアカウント 1 件を返す一覧。 */
function respondWith(user: { roles: string[]; permissions: string[] }) {
  get.mockImplementation((path: string) =>
    Promise.resolve(
      path === '/api/admin/roles'
        ? ROLES
        : [
            {
              id: 2,
              username: 'kid',
              display_name: 'こども',
              email: null,
              is_active: true,
              ...user,
            },
          ],
    ),
  )
}

function fillForm(overrides: { email?: string } = {}) {
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'kid' } })
  fireEvent.change(screen.getByLabelText('Display name'), { target: { value: 'こども' } })
  fireEvent.change(screen.getByLabelText('Email (optional)'), {
    target: { value: overrides.email ?? '' },
  })
  fireEvent.change(screen.getByPlaceholderText('Password'), { target: { value: 'kid-pass-123' } })
}

describe('UsersPage', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    put.mockReset()
    get.mockImplementation((path: string) =>
      Promise.resolve(path === '/api/admin/roles' ? [{ id: 1, name: 'member' }] : []),
    )
    post.mockResolvedValue({})
    put.mockResolvedValue({})
  })

  it('ログイン ID と表示名を別々に送る（display_name 欠落は 422 になる）', async () => {
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })
    await screen.findByRole('option', { name: 'member' })

    fillForm({ email: 'kid@example.com' })
    fireEvent.click(screen.getByRole('button', { name: 'Add user' }))

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith('/api/admin/users', {
        username: 'kid',
        display_name: 'こども',
        email: 'kid@example.com',
        password: 'kid-pass-123',
        roles: ['member'],
      })
    })
  })

  it('メールアドレスは任意で、空なら null を送る（ADR-0011）', async () => {
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })
    await screen.findByRole('option', { name: 'member' })

    fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Add user' }))

    await waitFor(() => {
      expect(post.mock.calls[0]?.[1]).toMatchObject({ email: null })
    })
  })

  it('メールアドレスを持たないアカウントも一覧に出せる', async () => {
    respondWith({ roles: ['member'], permissions: ['item:view'] })
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    expect(await screen.findByText('こども')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('ロールを付けると、変更後の全体を送る', async () => {
    respondWith({ roles: ['member'], permissions: ['item:view'] })
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    fireEvent.click(await screen.findByLabelText('kid: admin'))

    await waitFor(() => {
      expect(put).toHaveBeenCalledWith('/api/admin/users/2', { roles: ['member', 'admin'] })
    })
  })

  it('ロールを外すと、そのロールだけを除いた全体を送る', async () => {
    respondWith({ roles: ['admin', 'member'], permissions: ['user:manage'] })
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    fireEvent.click(await screen.findByLabelText('kid: admin'))

    await waitFor(() => {
      expect(put).toHaveBeenCalledWith('/api/admin/users/2', { roles: ['member'] })
    })
  })

  it('実際に効く権限はサーバーの計算結果を出すだけで、変更させない', async () => {
    respondWith({ roles: ['member'], permissions: ['item:view', 'point:manage'] })
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    expect(await screen.findByText('point:manage')).toBeInTheDocument()
    expect(screen.queryByLabelText('kid: point:manage')).not.toBeInTheDocument()
  })

  it('ロール一覧を取れないときは、今のロールを文字で示す', async () => {
    get.mockImplementation((path: string) =>
      path === '/api/admin/roles'
        ? Promise.reject(new Error('forbidden'))
        : Promise.resolve([
            {
              id: 2,
              username: 'kid',
              display_name: 'こども',
              email: null,
              is_active: true,
              roles: ['member'],
              permissions: ['item:view'],
            },
          ]),
    )
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    expect(await screen.findByText('member')).toBeInTheDocument()
    expect(screen.queryByLabelText('kid: member')).not.toBeInTheDocument()
  })
})
