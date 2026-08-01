/**
 * 家族まわりのテストデータ。
 *
 * ナビゲーション・ダッシュボード・家族設定はどれも同じ `FamilyDetail` を見るので、
 * 組み立ても 1 か所に置く。既定は「アカウントのある子が 1 人いる家族を owner が
 * 見ている」状態で、検証したい違いだけを上書きする。
 */
import type { FamilyDetail, FamilyRole, Membership } from '../services/families'

export function member(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 2,
    display_name: 'ハナ',
    role: 'child',
    is_linked: true,
    is_me: false,
    username: 'hana',
    ledger_id: 20,
    balance: 70,
    independence_proposed: false,
    can_reset_password: true,
    can_graduate: true,
    can_remove: false,
    ...overrides,
  }
}

export function familyOf(myRole: FamilyRole, memberships: Membership[]): FamilyDetail {
  return { id: 1, name: 'ほその家', my_membership_id: 1, my_role: myRole, memberships }
}
