/**
 * Display names for roles (actor names from ADR-0018).
 *
 * Role names (such as `operator`) are alphanumeric identifiers like scopes, and on their own
 * they do not say what the person does. Built-in roles show the display name first, with the name in parentheses.
 * Roles created in the admin console have no display name, so the name is shown as-is.
 */
import { knownMessageKey, type TranslationParams } from '../i18n'

type Translate = (key: string, params?: TranslationParams) => string

export function roleLabel(t: Translate, name: string): string {
  const key = knownMessageKey(`roles.name.${name}`, '')
  return key === '' ? name : t('roles.labelWithName', { label: t(key), name })
}
