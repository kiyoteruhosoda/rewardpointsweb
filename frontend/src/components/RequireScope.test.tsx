/**
 * scope の無い人は URL を直接開いても画面に入れず、入口へ戻る（ADR-0047）。
 */
import { screen } from '@testing-library/react'
import { Route } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { RequireScope } from './RequireScope'

function renderAt(scopes: string[]) {
  return renderWithProviders(<p>unused</p>, {
    route: '/admin/displays',
    path: '/unused',
    scopes,
    extraRoutes: (
      <>
        <Route path="/" element={<p>home</p>} />
        <Route element={<RequireScope scopes={['display:approve']} />}>
          <Route path="/admin/displays" element={<p>displays</p>} />
        </Route>
      </>
    ),
  })
}

describe('RequireScope', () => {
  it('scope を持つ人には画面を出す', () => {
    renderAt(['display:approve'])
    expect(screen.getByText('displays')).toBeInTheDocument()
  })

  it('scope の無い人は入口へ戻す', () => {
    renderAt(['user:manage', 'family:manage'])
    expect(screen.getByText('home')).toBeInTheDocument()
    expect(screen.queryByText('displays')).not.toBeInTheDocument()
  })
})
