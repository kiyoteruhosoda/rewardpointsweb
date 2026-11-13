/** Query the IdP in a hidden frame and read the result from the frame's destination (ADR-0058). */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RENEWAL_RESULT_PATH, renewInFrame } from './silentRenewal'

function frameNow(): HTMLIFrameElement {
  const frame = document.querySelector('iframe')
  if (!frame) throw new Error('no frame')
  return frame
}

/** Pretend the frame navigated to `href` and finished loading. */
function land(frame: HTMLIFrameElement, href: string | (() => never)): void {
  const location =
    typeof href === 'string'
      ? new URL(href, 'https://app.example.test')
      : {
          get href(): string {
            return href()
          },
        }
  Object.defineProperty(frame, 'contentWindow', { configurable: true, value: { location } })
  frame.dispatchEvent(new Event('load'))
}

describe('renewInFrame', () => {
  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('starts the continuation round trip in a hidden frame', () => {
    void renewInFrame()
    const frame = frameNow()
    expect(frame.getAttribute('src')).toBe('/api/auth/sso/renew')
    expect(frame.hidden).toBe(true)
  })

  it('returns the exchange ticket when continued, and cleans up the frame', async () => {
    const pending = renewInFrame()
    land(frameNow(), `${RENEWAL_RESULT_PATH}?result=renewed&ticket=t1`)
    await expect(pending).resolves.toEqual({ result: 'renewed', ticket: 't1' })
    expect(document.querySelector('iframe')).toBeNull()
  })

  it('is declined when refused', async () => {
    const pending = renewInFrame()
    land(frameNow(), `${RENEWAL_RESULT_PATH}?result=declined`)
    await expect(pending).resolves.toEqual({ result: 'declined' })
  })

  it('unknown results and renewed without a ticket are failed', async () => {
    const pending = renewInFrame()
    land(frameNow(), `${RENEWAL_RESULT_PATH}?result=ok`)
    await expect(pending).resolves.toEqual({ result: 'failed' })
    const bare = renewInFrame()
    land(frameNow(), `${RENEWAL_RESULT_PATH}?result=renewed`)
    await expect(bare).resolves.toEqual({ result: 'failed' })
  })

  it('is failed when stuck on an unreadable origin (an IdP page)', async () => {
    const pending = renewInFrame()
    land(frameNow(), () => {
      throw new DOMException('Blocked a frame', 'SecurityError')
    })
    await expect(pending).resolves.toEqual({ result: 'failed' })
  })

  it('is failed when it lands on another page', async () => {
    const pending = renewInFrame()
    land(frameNow(), '/login?sso_error=x')
    await expect(pending).resolves.toEqual({ result: 'failed' })
  })

  it('waits through about:blank before it starts', async () => {
    const pending = renewInFrame()
    const frame = frameNow()
    Object.defineProperty(frame, 'contentWindow', {
      configurable: true,
      value: { location: { href: 'about:blank' } },
    })
    frame.dispatchEvent(new Event('load'))
    land(frame, `${RENEWAL_RESULT_PATH}?result=renewed&ticket=t2`)
    await expect(pending).resolves.toEqual({ result: 'renewed', ticket: 't2' })
  })

  it('is failed on timeout', async () => {
    vi.useFakeTimers()
    const pending = renewInFrame(1000)
    vi.advanceTimersByTime(1000)
    await expect(pending).resolves.toEqual({ result: 'failed' })
    expect(document.querySelector('iframe')).toBeNull()
  })
})
