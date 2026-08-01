/** ユーザー管理: 作成時に送る中身が API のスキーマと一致していること。 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { UsersPage } from './UsersPage'

const get = vi.fn<(path: string) => Promise<unknown>>()
const post = vi.fn<(path: string, body?: unknown) => Promise<unknown>>()

vi.mock('../services/api', () => ({
  errorMessageKey: () => 'error.unknown_error',
  api: {
    get: (path: string) => get(path),
    post: (path: string, body?: unknown) => post(path, body),
    put: () => Promise.resolve(),
    delete: () => Promise.resolve(),
  },
}))

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
    get.mockImplementation((path: string) =>
      Promise.resolve(path === '/api/admin/roles' ? [{ id: 1, name: 'member' }] : []),
    )
    post.mockResolvedValue({})
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
    get.mockImplementation((path: string) =>
      Promise.resolve(
        path === '/api/admin/roles'
          ? [{ id: 1, name: 'member' }]
          : [
              {
                id: 2,
                username: 'kid',
                display_name: 'こども',
                email: null,
                is_active: true,
                roles: ['member'],
              },
            ],
      ),
    )
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    expect(await screen.findByText('こども')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
  })
})
