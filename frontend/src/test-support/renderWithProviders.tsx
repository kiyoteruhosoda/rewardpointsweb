/**
 * 画面テスト用の描画補助。
 *
 * 画面は i18n・テーマ・トースト・ルーター・認証（scope）・所属する家族の上でしか
 * 動かない。毎回同じ入れ子を書かずに済むよう、ここでまとめて用意する。scope と
 * 家族は引数で差し替えられるので、「権限があるとき／ないとき」「家族があるとき／
 * ないとき」の描き分けをそのまま検証できる。
 */
import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ToastProvider } from '../components/ToastNotification'
import { I18nProvider } from '../i18n'
import type { FamilyDetail } from '../services/families'
import type { UiSettings } from '../services/uiSettings'
import { AuthContext, type AuthValue, type Me } from '../store/AuthContext'
import { FamilyContext, type FamilyValue } from '../store/FamilyContext'
import { ThemeProvider } from '../theme'

const SETTINGS: UiSettings = {
  languages: ['en'],
  default_locale: 'en',
  default_theme: 'system',
}

const USER: Me = {
  user_id: 1,
  username: 'manager',
  display_name: 'manager',
  email: 'manager@example.com',
  scopes: [],
  must_change_password: false,
}

interface Options {
  /** ログイン中ユーザーが持つ scope。 */
  scopes?: string[]
  /** 表示する URL（`useParams` を使う画面で必要）。 */
  route?: string
  /** ルート定義のパス。既定は何にでも一致する。 */
  path?: string
  /** ログアウトの観測（再ログイン誘導を検証する画面で使う）。 */
  logout?: () => void
  /** SSO の引き換え（IdP からの戻りを受ける画面で差し替える）。 */
  loginWithSsoTicket?: (ticket: string) => Promise<string>
  /** 所属する家族。既定はどこにも所属していない状態。 */
  family?: FamilyDetail | null
  /** 家族を読み込めなかった状態（所属の有無は分からない）。 */
  familyFailed?: boolean
  /** 家族の読み直しの観測（変更の後に読み直すかを検証する画面で使う）。 */
  reloadFamily?: () => Promise<void>
  /**
   * 追加の `<Route>`。画面が別の URL へ送るところまで検証したいときに、
   * 行き先の目印として置く（`path` を絞ったうえで使う）。
   */
  extraRoutes?: ReactNode
}

function authValueOf(
  scopes: string[],
  logout: () => void,
  loginWithSsoTicket: (ticket: string) => Promise<string>,
): AuthValue {
  return {
    user: { ...USER, scopes },
    loading: false,
    login: () => Promise.resolve(),
    loginWithPasskey: () => Promise.resolve(),
    loginWithSsoTicket,
    logout,
    refreshMe: () => Promise.resolve(),
    hasScope: (...codes: string[]) => codes.every((code) => scopes.includes(code)),
  }
}

function familyValueOf(
  family: FamilyDetail | null,
  failed: boolean,
  reload: () => Promise<void>,
): FamilyValue {
  return { family, failed, loading: false, reload }
}

export function renderWithProviders(ui: ReactElement, options: Options = {}): RenderResult {
  const {
    scopes = [],
    route = '/',
    path = '*',
    logout = () => undefined,
    loginWithSsoTicket = () => Promise.resolve('/'),
    family = null,
    familyFailed = false,
    reloadFamily = () => Promise.resolve(),
    extraRoutes = null,
  } = options
  // 言語は en に固定する。利用者の選択（localStorage）が残っていると期待文言が変わる。
  localStorage.setItem('locale', 'en')

  return render(
    <I18nProvider settings={SETTINGS}>
      <ThemeProvider settings={SETTINGS}>
        <AuthContext.Provider value={authValueOf(scopes, logout, loginWithSsoTicket)}>
          <FamilyContext.Provider value={familyValueOf(family, familyFailed, reloadFamily)}>
            <ToastProvider>
              <MemoryRouter initialEntries={[route]}>
                <Routes>
                  <Route path={path} element={ui} />
                  {extraRoutes}
                </Routes>
              </MemoryRouter>
            </ToastProvider>
          </FamilyContext.Provider>
        </AuthContext.Provider>
      </ThemeProvider>
    </I18nProvider>,
  )
}
