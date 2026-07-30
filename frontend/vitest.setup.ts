import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom は matchMedia を実装していない。テーマの OS 追従（theme/index.tsx）が
// これを参照するため、「ライト配色・通知なし」の既定を置く。切り替えの検証など
// 挙動そのものを見るテストは vi.stubGlobal で差し替える（theme.test.tsx）。
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

// テスト間で DOM を持ち越さない（describe をまたいだ副作用を防ぐ）
afterEach(() => {
  cleanup()
})
