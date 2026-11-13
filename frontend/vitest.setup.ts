import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom does not implement matchMedia. Following the OS theme (theme/index.tsx)
// reads it, so provide a default of "light scheme, no notifications". Tests that check
// the behavior itself, such as switching, replace it with vi.stubGlobal (theme.test.tsx).
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList,
})

// Do not carry the DOM over between tests (prevents side effects across describe blocks)
afterEach(() => {
  cleanup()
})
