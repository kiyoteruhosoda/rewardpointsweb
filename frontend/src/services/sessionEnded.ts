/**
 * Notification that the login could not be continued (ADR-0058).
 *
 * The API layer (`api.ts`) emits it when the login cannot be continued after a 401, and the auth state
 * (`AuthContext`) listens and drops the user. The screen moves to the login screen (destination in `redirect_to`,
 * unsaved input kept by `useSessionDraft`).
 */
type Listener = () => void

const listeners = new Set<Listener>()

/** Listen for the notification. Call the return value to stop listening. */
export function subscribeSessionEnded(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function reportSessionEnded(): void {
  for (const listener of listeners) listener()
}
