/**
 * Test data for families.
 *
 * Navigation, the dashboard and family settings all read the same `FamilyDetail`,
 * so it is built in one place. The default is "an owner viewing a family with one child
 * who has an account"; override only the difference under test.
 */
import type { DailyBonus, FamilyDetail, FamilyRole, Membership } from '../services/families'

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
    daily_bonus: null,
    independence_proposed: false,
    can_reset_password: true,
    can_propose_independence: true,
    can_remove: false,
    ...overrides,
  }
}

export function familyOf(myRole: FamilyRole, memberships: Membership[]): FamilyDetail {
  return { id: 1, name: 'ほその家', rules: null, my_membership_id: 1, my_role: myRole, memberships }
}

export function dailyBonus(overrides: Partial<DailyBonus> = {}): DailyBonus {
  return {
    ledger_id: 20,
    amount: 10,
    reason: 'まいにちのボーナス',
    starts_on: '2026-08-01',
    granted_through: '2026-08-01',
    ...overrides,
  }
}
