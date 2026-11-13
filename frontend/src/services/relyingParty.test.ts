/** Matching the RP ID with the currently open URL (the same rules the browser applies). */
import { describe, expect, it } from 'vitest'

import {
  isDomainName,
  isRelyingPartyIdUsable,
  matchesLocation,
  relyingPartyForLocation,
  relyingPartyIdOf,
  supportsPasskeys,
} from './relyingParty'

describe('isRelyingPartyIdUsable', () => {
  it('allows the same domain or a parent domain', () => {
    expect(isRelyingPartyIdUsable('example.com', 'example.com')).toBe(true)
    expect(isRelyingPartyIdUsable('example.com', 'app.example.com')).toBe(true)
    expect(isRelyingPartyIdUsable('localhost', 'localhost')).toBe(true)
  })

  it('rejects another domain or a subdomain', () => {
    expect(isRelyingPartyIdUsable('localhost', 'app.example.com')).toBe(false)
    expect(isRelyingPartyIdUsable('app.example.com', 'example.com')).toBe(false)
    expect(isRelyingPartyIdUsable('example.org', 'example.com')).toBe(false)
    // A match that merely cuts a name in the middle is not a parent domain
    expect(isRelyingPartyIdUsable('example.com', 'notexample.com')).toBe(false)
  })

  it('rejects a single-label parent domain (public suffix)', () => {
    // Browsers reject unregistrable domains such as `com` as an RP ID
    expect(isRelyingPartyIdUsable('com', 'example.com')).toBe(false)
  })

  it('normalises whitespace, case and a trailing dot before comparing', () => {
    expect(isRelyingPartyIdUsable(' Example.COM ', 'app.example.com.')).toBe(true)
  })

  it('rejects an empty value (unset is a misconfiguration)', () => {
    expect(isRelyingPartyIdUsable('', 'example.com')).toBe(false)
  })
})

describe('isDomainName', () => {
  it('is true for domain names and false for IP addresses (not usable as RP ID)', () => {
    expect(isDomainName('app.example.com')).toBe(true)
    expect(isDomainName('localhost')).toBe(true)
    expect(isDomainName('192.168.1.5')).toBe(false)
    expect(isDomainName('[::1]')).toBe(false)
    expect(isDomainName('example.com:8443')).toBe(false)
    expect(isDomainName('')).toBe(false)
  })
})

describe('supportsPasskeys', () => {
  it('allows https domains and localhost', () => {
    expect(
      supportsPasskeys({
        hostname: 'app.example.com',
        origin: 'https://app.example.com',
        protocol: 'https:',
      }),
    ).toBe(true)
    expect(
      supportsPasskeys({
        hostname: 'localhost',
        origin: 'http://localhost:5173',
        protocol: 'http:',
      }),
    ).toBe(true)
  })

  it('rejects IP addresses and http other than localhost', () => {
    expect(
      supportsPasskeys({
        hostname: '192.168.1.5',
        origin: 'http://192.168.1.5',
        protocol: 'http:',
      }),
    ).toBe(false)
    // Outside a secure context, the browser will not run it even if the config is fixed
    expect(
      supportsPasskeys({ hostname: 'nas.local', origin: 'http://nas.local', protocol: 'http:' }),
    ).toBe(false)
  })
})

describe('relyingPartyForLocation', () => {
  it('builds a working config from the open URL', () => {
    expect(
      relyingPartyForLocation({
        hostname: 'App.Example.com',
        origin: 'https://App.Example.com/',
        protocol: 'https:',
      }),
    ).toEqual({ rpId: 'app.example.com', origin: 'https://app.example.com' })
  })
})

describe('matchesLocation', () => {
  const location = {
    hostname: 'app.example.com',
    origin: 'https://app.example.com',
    protocol: 'https:',
  }

  it('is true when both RP ID and origin match', () => {
    expect(
      matchesLocation({ rpId: 'example.com', origin: 'https://app.example.com' }, location),
    ).toBe(true)
  })

  it('is false when only the origin differs (does not match the origin the browser sends)', () => {
    // A different port is a different origin
    expect(
      matchesLocation({ rpId: 'example.com', origin: 'https://app.example.com:8443' }, location),
    ).toBe(false)
  })

  it('treats default port and trailing dot as mere notation (the server drops them too)', () => {
    expect(
      matchesLocation({ rpId: 'example.com', origin: 'https://app.example.com:443' }, location),
    ).toBe(true)
    expect(
      matchesLocation({ rpId: 'example.com', origin: 'https://app.example.com./' }, location),
    ).toBe(true)
  })

  it('is false when only the RP ID differs', () => {
    expect(
      matchesLocation({ rpId: 'localhost', origin: 'https://app.example.com' }, location),
    ).toBe(false)
  })
})

describe('relyingPartyIdOf', () => {
  it('takes registration options from rp.id', () => {
    expect(relyingPartyIdOf({ rp: { id: 'example.com', name: 'rewardpointsweb' } })).toBe(
      'example.com',
    )
  })

  it('takes authentication options from rpId', () => {
    expect(relyingPartyIdOf({ rpId: 'example.com' })).toBe('example.com')
  })

  it('is empty when absent (the browser uses the open domain)', () => {
    expect(relyingPartyIdOf({})).toBe('')
    expect(relyingPartyIdOf({ rp: { name: 'rewardpointsweb' } })).toBe('')
    expect(relyingPartyIdOf({ rp: null })).toBe('')
  })
})
