/**
 * API for display devices (signage) (ADR-0047).
 *
 * Device side (no auth): start and receive pairing. Re-obtaining an access token from the credential
 * is `openDisplaySession` in `api.ts` (kept at the same entry point as the 401 re-fetch).
 *
 * Operator admin side (`display:approve`): approve, choose the family to show, list, remove.
 */
import { ApiError, api } from './api'

export interface StartedPairing {
  /** Confirmation code shown on screen (`KQ7M-3XPA`) */
  user_code: string
  /** Secret known only to the device. Never shown on screen */
  device_code: string
  expires_in: number
  /** Interval for polling the pickup (seconds) */
  interval: number
  /** QR code pointing to the approval screen (SVG data URI). */
  qr_code: string | null
}

export interface DisplayDevice {
  account_id: number
  family_id: number
  family_name: string
  name: string
  created_at: string
  /** null until picked up */
  last_used_at: string | null
}

export interface DisplayableFamily {
  id: number
  name: string
}

/** Result of polling the pickup. */
export type ClaimOutcome =
  | { kind: 'claimed'; credential: string }
  | { kind: 'pending' }
  /** Expired or already picked up. Pair again */
  | { kind: 'expired' }

/** Path of the approval screen. The QR code points here too (the confirmation code goes after `#`). */
export const APPROVE_PATH = '/admin/displays/approve'

export function startPairing(origin: string): Promise<StartedPairing> {
  return api.post<StartedPairing>('/api/display/pairings', { origin })
}

export async function claimPairing(deviceCode: string): Promise<ClaimOutcome> {
  try {
    const claimed = await api.post<{ device_credential: string }>('/api/display/pairings/claim', {
      device_code: deviceCode,
    })
    return { kind: 'claimed', credential: claimed.device_credential }
  } catch (error) {
    if (error instanceof ApiError && error.code === 'authorization_pending')
      return { kind: 'pending' }
    if (error instanceof ApiError && error.code === 'expired_token') return { kind: 'expired' }
    throw error
  }
}

export function approvePairing(body: {
  user_code: string
  family_id: number
  name: string
}): Promise<DisplayDevice> {
  return api.post<DisplayDevice>('/api/display/pairings/approve', body)
}

export function listDisplayableFamilies(): Promise<DisplayableFamily[]> {
  return api.get<DisplayableFamily[]>('/api/display/families')
}

export function listDisplayDevices(): Promise<DisplayDevice[]> {
  return api.get<DisplayDevice[]>('/api/display/devices')
}

export function removeDisplayDevice(accountId: number): Promise<undefined> {
  return api.delete<undefined>(`/api/display/devices/${accountId}`)
}

/** Where the confirmation code for returning to the approval screen is kept during the login round trip (same tab only). */
const PENDING_APPROVAL_KEY = 'pendingDisplayApproval'

/**
 * When the approval screen (QR code) is opened while not logged in, keep the confirmation code.
 *
 * SSO goes through the IdP's screen, so the `#` part is lost. As with invitation codes, it is kept in
 * `sessionStorage` instead of moved into the query (same reason as `invitationLink.ts`).
 */
export function rememberPendingApproval(hash: string): void {
  sessionStorage.setItem(PENDING_APPROVAL_KEY, hash)
}

/** Take out the stored approval destination (only once). null if none. */
export function takePendingApproval(): string | null {
  const hash = sessionStorage.getItem(PENDING_APPROVAL_KEY)
  if (hash === null) return null
  sessionStorage.removeItem(PENDING_APPROVAL_KEY)
  return `${APPROVE_PATH}${hash}`
}

/** Read the confirmation code passed via QR code or link (`#KQ7M-3XPA`). Empty string if none. */
export function userCodeFromHash(hash: string): string {
  return decodeURIComponent(hash.replace(/^#/, '')).trim()
}
