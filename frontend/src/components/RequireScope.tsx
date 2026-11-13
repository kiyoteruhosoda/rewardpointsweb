/**
 * Sends people without the scope back to the entry (route wrapper).
 *
 * Merely hiding it from the menu would show the screen frame and action buttons to people who open the
 * URL directly, and pressing would give 403. Display-device screens are for operators only (ADR-0047).
 */
import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../store/AuthContext'

export function RequireScope({ scopes }: { scopes: string[] }) {
  const { hasScope } = useAuth()
  if (!hasScope(...scopes)) return <Navigate to="/" replace />
  return <Outlet />
}
