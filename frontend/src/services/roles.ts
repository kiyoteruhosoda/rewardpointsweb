/**
 * ロールの呼び名（ADR-0018 のアクター名）。
 *
 * ロールの名前（`operator` など）は scope と同じく英字の識別子で、それだけでは
 * 何をする人か読み取れない。決まったロールは呼び名を前に出し、名前を括弧で添える。
 * 管理画面で作ったロールは呼び名を持たないので、名前のまま出す。
 */
import { knownMessageKey, type TranslationParams } from '../i18n'

type Translate = (key: string, params?: TranslationParams) => string

export function roleLabel(t: Translate, name: string): string {
  const key = knownMessageKey(`roles.name.${name}`, '')
  return key === '' ? name : t('roles.labelWithName', { label: t(key), name })
}
