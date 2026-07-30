/**
 * 画面テスト用の描画補助。
 *
 * 画面は i18n・トースト・ルーター・認証（scope）の上でしか動かない。毎回同じ
 * 入れ子を書かずに済むよう、ここでまとめて用意する。scope は引数で差し替えられる
 * ので、「権限があるとき／ないとき」の描き分けをそのまま検証できる。
 */
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ToastProvider } from '../components/ToastNotification'
import { I18nProvider } from '../i18n'
import type { UiSettings } from '../services/uiSettings'
import { AuthContext, type AuthValue, type Me } from '../store/AuthContext'

const SETTINGS: UiSettings = {
  languages: ['en'],
  default_locale: 'en',
  default_theme: 'system',
}

const USER: Me = {
  user_id: 1,
  email: 'manager@example.com',
  username: 'manager',
  scopes: [],
}

interface Options {
  /** ログイン中ユーザーが持つ scope。 */
  scopes?: string[]
  /** 表示する URL（`useParams` を使う画面で必要）。 */
  route?: string
  /** ルート定義のパス。既定は何にでも一致する。 */
  path?: string
}

function authValueOf(scopes: string[]): AuthValue {
  return {
    user: { ...USER, scopes },
    loading: false,
    login: () => Promise.resolve(),
    loginWithPasskey: () => Promise.resolve(),
    logout: () => undefined,
    refreshMe: () => Promise.resolve(),
    hasScope: (...codes: string[]) => codes.every((code) => scopes.includes(code)),
  }
}

export function renderWithProviders(ui: ReactElement, options: Options = {}): RenderResult {
  const { scopes = [], route = '/', path = '*' } = options
  // 言語は en に固定する。利用者の選択（localStorage）が残っていると期待文言が変わる。
  localStorage.setItem('locale', 'en')

  return render(
    <I18nProvider settings={SETTINGS}>
      <AuthContext.Provider value={authValueOf(scopes)}>
        <ToastProvider>
          <MemoryRouter initialEntries={[route]}>
            <Routes>
              <Route path={path} element={ui} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </AuthContext.Provider>
    </I18nProvider>,
  )
}
