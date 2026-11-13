/** User management: the payload sent on creation matches the API schema. */
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

/** A list with one account that has exactly one role. */
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
              entrances: { password: true, totp: false, passkeys: 0, identity_providers: [] },
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

  it('sends login ID and display name separately (missing display_name is a 422)', async () => {
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })
    await screen.findByRole('option', { name: 'Parent (member)' })

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

  it('email is optional and sends null when empty (ADR-0011)', async () => {
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })
    await screen.findByRole('option', { name: 'Parent (member)' })

    fillForm()
    fireEvent.click(screen.getByRole('button', { name: 'Add user' }))

    await waitFor(() => {
      expect(post.mock.calls[0]?.[1]).toMatchObject({ email: null })
    })
  })

  it('can list accounts without an email', async () => {
    respondWith({ roles: ['member'], permissions: ['item:view'] })
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    expect(await screen.findByText('こども')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('adding a role sends the whole resulting set', async () => {
    respondWith({ roles: ['member'], permissions: ['item:view'] })
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    fireEvent.click(await screen.findByLabelText('kid: admin'))

    await waitFor(() => {
      expect(put).toHaveBeenCalledWith('/api/admin/users/2', { roles: ['member', 'admin'] })
    })
  })

  it('removing a role sends the whole set without that role', async () => {
    respondWith({ roles: ['admin', 'member'], permissions: ['user:manage'] })
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    fireEvent.click(await screen.findByLabelText('kid: admin'))

    await waitFor(() => {
      expect(put).toHaveBeenCalledWith('/api/admin/users/2', { roles: ['member'] })
    })
  })

  it('shows effective permissions as computed by the server, read-only', async () => {
    respondWith({ roles: ['member'], permissions: ['item:view', 'point:manage'] })
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    expect(await screen.findByText('point:manage')).toBeInTheDocument()
    expect(screen.queryByLabelText('kid: point:manage')).not.toBeInTheDocument()
  })

  it('shows current roles as text when the role list is unavailable', async () => {
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
              entrances: { password: true, totp: false, passkeys: 0, identity_providers: [] },
              roles: ['member'],
              permissions: ['item:view'],
            },
          ]),
    )
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    expect(await screen.findByText('Parent (member)')).toBeInTheDocument()
    expect(screen.queryByLabelText('kid: member')).not.toBeInTheDocument()
  })

  it('lists the ways in (so it is readable that there are two auth systems)', async () => {
    // ⚠ IdP-side multi-factor does not show here. Only the ways this app knows about can be shown,
    //   which is precisely what "two authentication systems" means (ADR-0035).
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
                roles: ['member'],
                permissions: ['item:view'],
                entrances: {
                  password: false,
                  totp: false,
                  passkeys: 2,
                  identity_providers: ['https://idp.example'],
                },
              },
            ],
      ),
    )
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    expect(await screen.findByText('Passkey ×2')).toBeInTheDocument()
    expect(screen.getByText('SSO')).toBeInTheDocument()
  })

  it('shows built-in roles as label plus name, and admin-created roles by name', async () => {
    get.mockImplementation((path: string) =>
      Promise.resolve(
        path === '/api/admin/roles'
          ? [
              { id: 5, name: 'operator' },
              { id: 9, name: 'auditor' },
            ]
          : [],
      ),
    )
    renderWithProviders(<UsersPage />, { scopes: ['user:manage'] })

    expect(
      await screen.findByRole('option', { name: 'Display approver (operator)' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'auditor' })).toBeInTheDocument()
  })
})
