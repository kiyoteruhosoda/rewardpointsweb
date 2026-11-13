/** Settings-screen warning: whether passkeys can be used from the URL currently open. */
import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { renderWithProviders } from '../test-support/renderWithProviders'
import { PasskeyDomainNotice } from './PasskeyDomainNotice'

const LOCATION = {
  hostname: 'app.example.com',
  origin: 'https://app.example.com',
  protocol: 'https:',
}

describe('PasskeyDomainNotice', () => {
  it('shows nothing when they match', () => {
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'app.example.com', origin: 'https://app.example.com' }}
        location={LOCATION}
        onApply={vi.fn()}
      />,
    )
    expect(screen.queryByText(/Passkeys cannot be used/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows the current value and the open URL when they differ', () => {
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'localhost', origin: 'http://localhost:5173' }}
        location={LOCATION}
        onApply={vi.fn()}
      />,
    )
    const notice = screen.getByText(/Passkeys cannot be used/)
    expect(notice).toHaveTextContent('https://app.example.com')
    expect(notice).toHaveTextContent('localhost')
    expect(notice).toHaveTextContent('http://localhost:5173')
  })

  it('"match" returns the open URL\'s value (does not save)', () => {
    const onApply = vi.fn()
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'localhost', origin: 'http://localhost:5173' }}
        location={LOCATION}
        onApply={onApply}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Match the URL/ }))
    expect(onApply).toHaveBeenCalledWith({
      rpId: 'app.example.com',
      origin: 'https://app.example.com',
    })
  })

  // ⚠ **The test "don't show the button when fixed by an environment variable" was removed.**
  //   The screen value now wins (ADR-0031), so even if compose has a value, matching and saving
  //   here wins over it -- there is no longer a reason not to show it.

  it('when opened by IP address, shows how to reopen instead of the match button', () => {
    // A value matching that URL cannot be saved (RP ID only accepts domain names)
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'localhost', origin: 'http://localhost:5173' }}
        location={{ hostname: '192.168.1.5', origin: 'http://192.168.1.5', protocol: 'http:' }}
        onApply={vi.fn()}
      />,
    )
    expect(screen.getByText(/cannot be used from this URL at all/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows even when values match if passkeys do not work on that URL', () => {
    // An http domain name is not a secure context, and the server also rejects this origin.
    // Staying silent based only on the match would make the user's "add passkey" fail.
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'nas.local', origin: 'http://nas.local' }}
        location={{ hostname: 'nas.local', origin: 'http://nas.local', protocol: 'http:' }}
        onApply={vi.fn()}
      />,
    )
    expect(screen.getByText(/cannot be used from this URL at all/)).toBeInTheDocument()
  })

  it('does not treat a setting that only spells out the default port as a mismatch', () => {
    // The server drops `:443` when building the RP. This setting works.
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: 'app.example.com', origin: 'https://app.example.com:443' }}
        location={LOCATION}
        onApply={vi.fn()}
      />,
    )
    expect(screen.queryByText(/Passkeys cannot be used/)).not.toBeInTheDocument()
  })

  it('shows an unset value in a recognisable form rather than blank', () => {
    renderWithProviders(
      <PasskeyDomainNotice
        settings={{ rpId: '', origin: '' }}
        location={LOCATION}
        onApply={vi.fn()}
      />,
    )
    expect(screen.getByText(/“—”/)).toBeInTheDocument()
  })
})
