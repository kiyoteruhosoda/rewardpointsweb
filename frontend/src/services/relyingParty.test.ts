/** RP ID と、いま開いている URL の噛み合わせ（ブラウザが見る規則と同じもの）。 */
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
  it('同じドメイン・上位ドメインなら使える', () => {
    expect(isRelyingPartyIdUsable('example.com', 'example.com')).toBe(true)
    expect(isRelyingPartyIdUsable('example.com', 'app.example.com')).toBe(true)
    expect(isRelyingPartyIdUsable('localhost', 'localhost')).toBe(true)
  })

  it('別のドメイン・下位ドメインは使えない', () => {
    expect(isRelyingPartyIdUsable('localhost', 'app.example.com')).toBe(false)
    expect(isRelyingPartyIdUsable('app.example.com', 'example.com')).toBe(false)
    expect(isRelyingPartyIdUsable('example.org', 'example.com')).toBe(false)
    // 名前の途中で切れているだけの一致は上位ドメインではない
    expect(isRelyingPartyIdUsable('example.com', 'notexample.com')).toBe(false)
  })

  it('1 ラベルだけの上位ドメイン（公開サフィックス）は使えない', () => {
    // ブラウザは `com` のような登録できないドメインを RP ID として拒む
    expect(isRelyingPartyIdUsable('com', 'example.com')).toBe(false)
  })

  it('空白・大文字・末尾のドットは揃えてから比べる', () => {
    expect(isRelyingPartyIdUsable(' Example.COM ', 'app.example.com.')).toBe(true)
  })

  it('値が空なら使えない（未設定は設定の誤り）', () => {
    expect(isRelyingPartyIdUsable('', 'example.com')).toBe(false)
  })
})

describe('isDomainName', () => {
  it('ドメイン名は真、IP アドレスは偽（RP ID には使えない）', () => {
    expect(isDomainName('app.example.com')).toBe(true)
    expect(isDomainName('localhost')).toBe(true)
    expect(isDomainName('192.168.1.5')).toBe(false)
    expect(isDomainName('[::1]')).toBe(false)
    expect(isDomainName('example.com:8443')).toBe(false)
    expect(isDomainName('')).toBe(false)
  })
})

describe('supportsPasskeys', () => {
  it('https のドメイン・localhost なら使える', () => {
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

  it('IP アドレス・localhost 以外の http では使えない', () => {
    expect(
      supportsPasskeys({
        hostname: '192.168.1.5',
        origin: 'http://192.168.1.5',
        protocol: 'http:',
      }),
    ).toBe(false)
    // 安全な文脈でなければ、設定を直してもブラウザが動かさない
    expect(
      supportsPasskeys({ hostname: 'nas.local', origin: 'http://nas.local', protocol: 'http:' }),
    ).toBe(false)
  })
})

describe('relyingPartyForLocation', () => {
  it('開いている URL からそのまま使える設定を作る', () => {
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

  it('RP ID とオリジンの両方が噛み合っていれば真', () => {
    expect(
      matchesLocation({ rpId: 'example.com', origin: 'https://app.example.com' }, location),
    ).toBe(true)
  })

  it('オリジンだけ違えば偽（ブラウザが送るオリジンと一致しない）', () => {
    // ポートが違えば別のオリジン
    expect(
      matchesLocation({ rpId: 'example.com', origin: 'https://app.example.com:8443' }, location),
    ).toBe(false)
  })

  it('既定ポート・末尾のドットは書き方の違いにすぎない（サーバーも落とす）', () => {
    expect(
      matchesLocation({ rpId: 'example.com', origin: 'https://app.example.com:443' }, location),
    ).toBe(true)
    expect(
      matchesLocation({ rpId: 'example.com', origin: 'https://app.example.com./' }, location),
    ).toBe(true)
  })

  it('RP ID だけ違えば偽', () => {
    expect(
      matchesLocation({ rpId: 'localhost', origin: 'https://app.example.com' }, location),
    ).toBe(false)
  })
})

describe('relyingPartyIdOf', () => {
  it('登録のオプションは rp.id から取る', () => {
    expect(relyingPartyIdOf({ rp: { id: 'example.com', name: 'rewardpointsweb' } })).toBe(
      'example.com',
    )
  })

  it('認証のオプションは rpId から取る', () => {
    expect(relyingPartyIdOf({ rpId: 'example.com' })).toBe('example.com')
  })

  it('入っていなければ空（ブラウザが開いているドメインを使う）', () => {
    expect(relyingPartyIdOf({})).toBe('')
    expect(relyingPartyIdOf({ rp: { name: 'rewardpointsweb' } })).toBe('')
    expect(relyingPartyIdOf({ rp: null })).toBe('')
  })
})
