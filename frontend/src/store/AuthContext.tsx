/** 認証状態（ログイン中ユーザーと scope）。認可判定は hasScope で行う。 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import {
  ApiError,
  api,
  clearOfflineViewCache,
  clearTokens,
  hasTokens,
  setTokens,
} from '../services/api'
import { exchangeSsoTicket } from '../services/sso'
import { assertPasskey, type PasskeyChallenge } from '../services/webauthn'

export interface Me {
  user_id: number
  /** ログイン識別子。メールアドレスは任意項目（ADR-0011）。 */
  username: string
  display_name: string
  email: string | null
  scopes: string[]
  /** 一時パスワードでのログイン中。変更を終えるまで他の操作は通らない。 */
  must_change_password: boolean
  /**
   * パスワードという入り口を持っているか（ADR-0034）。
   * 偽 = SSO でしか入れない利用者。画面はパスワード変更の導線を出さない。
   */
  has_password: boolean
  /** 表示端末（サイネージ）のセッションか（ADR-0047）。真なら表示の画面だけを出す。 */
  display_device: boolean
}

interface TokenPair {
  access_token: string
  refresh_token: string
}

export interface AuthValue {
  user: Me | null
  loading: boolean
  /**
   * サーバーに届かない（5xx・通信の失敗）。新しい版を配っている最中など。
   * ⚠ **このとき user を null にせず、トークン（とオフライン閲覧のキャッシュ）も消さない**——ログアウトしたのではないので、ログイン画面へ
   * 送ると、戻ってきたあとも IdP の入口の無い画面に取り残される。つながるまで自動で聞き直す。
   */
  unreachable: boolean
  /** 二要素認証が有効なアカウントでは totpCode が必要（未指定なら totp_required）。 */
  login: (username: string, password: string, totpCode?: string) => Promise<void>
  loginWithPasskey: () => Promise<void>
  /** IdP からの戻りに付く引き換え券でログインする。返すのは戻り先の経路。 */
  loginWithSsoTicket: (ticket: string) => Promise<string>
  logout: () => void
  refreshMe: () => Promise<void>
  hasScope: (...codes: string[]) => boolean
}

/** テストが scope を差し替えて描画できるよう公開する（本番の生成は AuthProvider）。 */
export const AuthContext = createContext<AuthValue | null>(null)

const SERVER_ERROR = 500
/** サーバーに届かないとき、聞き直す間隔 */
export const RECONNECT_INTERVAL_MS = 5000

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [unreachable, setUnreachable] = useState(false)

  const refreshMe = useCallback(async () => {
    if (!hasTokens()) {
      setUser(null)
      return
    }
    try {
      setUser(await api.get<Me>('/api/auth/me'))
      setUnreachable(false)
    } catch (e) {
      // 4xx（401 など）はサーバーが「ログインしていない」と答えたもの。それ以外は届いていない
      if (e instanceof ApiError && e.status < SERVER_ERROR) {
        clearTokens()
        setUser(null)
        setUnreachable(false)
      } else {
        setUnreachable(true)
      }
    }
  }, [])

  useEffect(() => {
    if (!unreachable) return
    const timer = window.setInterval(() => {
      void refreshMe()
    }, RECONNECT_INTERVAL_MS)
    return () => {
      window.clearInterval(timer)
    }
  }, [unreachable, refreshMe])

  useEffect(() => {
    void refreshMe().finally(() => {
      setLoading(false)
    })
  }, [refreshMe])

  const login = async (username: string, password: string, totpCode?: string) => {
    const pair = await api.post<TokenPair>('/api/auth/login', {
      username,
      password,
      totp_code: totpCode || null,
    })
    // ログアウトを経ずに別のアカウントで入り直しても、前のユーザーの
    // オフライン閲覧キャッシュを持ち越さない（ADR-0015）
    await clearOfflineViewCache()
    setTokens(pair.access_token, pair.refresh_token)
    await refreshMe()
  }

  const loginWithPasskey = async () => {
    const challenge = await api.post<PasskeyChallenge>('/api/auth/passkey/challenge')
    const credential = await assertPasskey(challenge.public_key)
    const pair = await api.post<TokenPair>('/api/auth/passkey/login', {
      challenge_id: challenge.challenge_id,
      credential,
    })
    // login と同じく、別アカウントでの入り直しに備えて消す（ADR-0015）
    await clearOfflineViewCache()
    setTokens(pair.access_token, pair.refresh_token)
    await refreshMe()
  }

  const loginWithSsoTicket = async (ticket: string) => {
    const session = await exchangeSsoTicket(ticket)
    // login と同じく、別アカウントでの入り直しに備えて消す（ADR-0015）
    await clearOfflineViewCache()
    setTokens(session.access_token, session.refresh_token)
    await refreshMe()
    return session.redirect_to
  }

  const logout = () => {
    void api.post('/api/auth/logout').catch(() => undefined)
    clearTokens()
    setUser(null)
  }

  const hasScope = (...codes: string[]) =>
    user !== null && codes.every((code) => user.scopes.includes(code))

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        unreachable,
        login,
        loginWithPasskey,
        loginWithSsoTicket,
        logout,
        refreshMe,
        hasScope,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used within AuthProvider')
  return value
}
