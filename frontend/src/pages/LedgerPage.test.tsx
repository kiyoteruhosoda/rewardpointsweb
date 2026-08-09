/**
 * 台帳: 追記型の見え方（打ち消しの対表示）と、変更 UI の出し分け。
 * 残高を出す画面は他にもあるので、記録の後に家族まで読み直すかも見る（ADR-0021）。
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { Link } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Fetched } from '../services/api'
import type {
  Correction,
  DailyBonus,
  Ledger,
  NewTransaction,
  Transaction,
} from '../services/families'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { LedgerPage } from './LedgerPage'

const viewLedger = vi.fn<() => Promise<Fetched<Ledger>>>()
const reasonSuggestions = vi.fn<() => Promise<string[]>>()
const record = vi.fn<() => Promise<Transaction>>()
const reverse = vi.fn<() => Promise<Transaction>>()
const correct = vi.fn<(transactionId: number, entry: NewTransaction) => Promise<Correction>>()
const setDailyBonus = vi.fn<(amount: number, reason: string) => Promise<DailyBonus>>()
const stopDailyBonus = vi.fn<() => Promise<undefined>>()

vi.mock('../services/families', () => ({
  parseUtc: (value: string) => new Date(`${value}Z`),
  newIdempotencyKey: () => 'test-key',
  families: {
    viewLedger: () => viewLedger(),
    reasonSuggestions: () => reasonSuggestions(),
    record: () => record(),
    reverse: () => reverse(),
    correct: (_family: number, _ledger: number, transactionId: number, entry: NewTransaction) =>
      correct(transactionId, entry),
    setDailyBonus: (_family: number, _ledger: number, amount: number, reason: string) =>
      setDailyBonus(amount, reason),
    stopDailyBonus: () => stopDailyBonus(),
  },
}))

function transaction(overrides: Partial<Transaction> = {}): Transaction {
  return {
    id: 1,
    amount: 100,
    reason: 'おてつだい',
    occurred_at: '2026-08-01T00:00:00',
    created_at: '2026-08-01T00:00:00',
    reversal_of_id: null,
    corrects_id: null,
    is_reversed: false,
    granted_by: 'おとうさん',
    ...overrides,
  }
}

function dailyBonus(overrides: Partial<DailyBonus> = {}): DailyBonus {
  return {
    ledger_id: 20,
    amount: 10,
    reason: 'まいにちのボーナス',
    starts_on: '2026-08-01',
    granted_through: '2026-08-01',
    ...overrides,
  }
}

function ledger(overrides: Partial<Ledger> = {}): Fetched<Ledger> {
  return {
    data: {
      ledger_id: 20,
      family_id: 1,
      membership_id: 2,
      display_name: 'ハナ',
      balance: 100,
      can_modify: true,
      transactions: [transaction()],
      daily_bonus: null,
      ...overrides,
    },
    fetchedAt: null,
  }
}

/** 別の子へ移るところまで見たいので、同じ経路に一致する行き先を添えて描く。 */
function renderPage(reloadFamily = () => Promise.resolve()) {
  return renderWithProviders(
    <>
      <Link to="/families/1/ledgers/21">タロウ</Link>
      <LedgerPage />
    </>,
    {
      scopes: ['point:view', 'point:manage'],
      route: '/families/1/ledgers/20',
      path: '/families/:familyId/ledgers/:ledgerId',
      reloadFamily,
    },
  )
}

/** 訂正の入力を開く（対象は最初の「訂正する」を出している行）。 */
function startCorrection(): void {
  fireEvent.click(screen.getAllByRole('button', { name: 'Correct' })[0] as HTMLElement)
}

/** 加算を 1 件記録する（フォームは加算・消費を符号で分ける）。 */
function addPoints(): void {
  fireEvent.change(screen.getByLabelText('Points'), { target: { value: '50' } })
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'おてつだい' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add points' }))
}

describe('LedgerPage', () => {
  beforeEach(() => {
    viewLedger.mockReset()
    reasonSuggestions.mockReset()
    record.mockReset()
    reverse.mockReset()
    correct.mockReset()
    setDailyBonus.mockReset()
    stopDailyBonus.mockReset()
    reasonSuggestions.mockResolvedValue([])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  describe('毎日のボーナス（ADR-0024）', () => {
    it('決めていなければ、始めるための入力欄を出す', async () => {
      viewLedger.mockResolvedValue(ledger())
      renderPage()

      expect(
        await screen.findByRole('button', { name: 'Start the daily bonus' }),
      ).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Stop' })).not.toBeInTheDocument()
    })

    it('決めてあれば、いまの量と「やめる」を出す', async () => {
      viewLedger.mockResolvedValue(ledger({ daily_bonus: dailyBonus({ amount: 25 }) }))
      renderPage()

      expect(await screen.findByText('25 pt are added every day.')).toBeInTheDocument()
      expect(screen.getByLabelText('Points per day')).toHaveValue(25)
      expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
    })

    it('保存したら台帳を読み直す（次に日付が変わるまで残高は動かない）', async () => {
      viewLedger
        .mockResolvedValueOnce(ledger())
        .mockResolvedValue(ledger({ daily_bonus: dailyBonus({ amount: 30 }) }))
      setDailyBonus.mockResolvedValue(dailyBonus({ amount: 30 }))
      renderPage()

      await screen.findByText('100 pt')
      fireEvent.change(screen.getByLabelText('Points per day'), { target: { value: '30' } })
      fireEvent.click(screen.getByRole('button', { name: 'Start the daily bonus' }))

      expect(await screen.findByText('30 pt are added every day.')).toBeInTheDocument()
      expect(setDailyBonus).toHaveBeenCalledWith(30, 'Daily bonus')
      // 決めただけでは足されない
      expect(screen.getByText('100 pt')).toBeInTheDocument()
    })

    it('やめたら入力欄は「始める」に戻る', async () => {
      viewLedger
        .mockResolvedValueOnce(ledger({ daily_bonus: dailyBonus() }))
        .mockResolvedValue(ledger())
      stopDailyBonus.mockResolvedValue(undefined)
      renderPage()

      await screen.findByRole('button', { name: 'Stop' })
      fireEvent.click(screen.getByRole('button', { name: 'Stop' }))

      expect(
        await screen.findByRole('button', { name: 'Start the daily bonus' }),
      ).toBeInTheDocument()
      expect(stopDailyBonus).toHaveBeenCalled()
    })

    it('can_modify が偽なら設定の入り口を出さない', async () => {
      viewLedger.mockResolvedValue(ledger({ can_modify: false, daily_bonus: dailyBonus() }))
      renderPage()

      await screen.findByText('100 pt')
      expect(screen.queryByLabelText('Points per day')).not.toBeInTheDocument()
    })
  })

  it('残高と履歴、記録した人を出す', async () => {
    viewLedger.mockResolvedValue(ledger())
    renderPage()

    expect(await screen.findByText('100 pt')).toBeInTheDocument()
    expect(screen.getByText('+100 pt')).toBeInTheDocument()
    expect(screen.getByText('おとうさん')).toBeInTheDocument()
  })

  it('can_modify が偽なら変更 UI を出さない', async () => {
    viewLedger.mockResolvedValue(ledger({ can_modify: false }))
    renderPage()

    await screen.findByText('100 pt')
    expect(screen.queryByRole('button', { name: 'Add points' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument()
    expect(
      screen.getByText('You can see these points, but only your parents can change them.'),
    ).toBeInTheDocument()
  })

  it('打ち消し済みと打ち消しの行を対で見せ、どちらも取り消せない', async () => {
    viewLedger.mockResolvedValue(
      ledger({
        balance: 0,
        transactions: [
          transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
          transaction({ id: 1, is_reversed: true }),
        ],
      }),
    )
    renderPage()

    await screen.findByText('0 pt')
    // 元の行は消えず、両方が並ぶ
    expect(screen.getByText(/\(undone\)/)).toBeInTheDocument()
    expect(screen.getByText(/\(undo\)/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument()
  })

  it('まだ取り消されていない行にだけ取り消しを出す', async () => {
    viewLedger.mockResolvedValue(ledger())
    renderPage()

    expect(await screen.findByRole('button', { name: 'Undo' })).toBeInTheDocument()
  })

  it('マイナス残高では 0 までの必要ポイントを添える', async () => {
    viewLedger.mockResolvedValue(ledger({ balance: -30 }))
    renderPage()

    expect(await screen.findByText('-30 pt')).toBeInTheDocument()
    expect(screen.getByText('30 pt short of zero.')).toBeInTheDocument()
  })

  it('よく使う理由を入力候補として出す', async () => {
    viewLedger.mockResolvedValue(ledger())
    reasonSuggestions.mockResolvedValue(['おてつだい', 'そうじ'])
    renderPage()

    await screen.findByText('100 pt')
    const options = document.querySelectorAll('datalist option')
    expect([...options].map((option) => option.getAttribute('value'))).toEqual([
      'おてつだい',
      'そうじ',
    ])
  })

  it('候補が取れなくても記録はできる（自由入力なので）', async () => {
    viewLedger.mockResolvedValue(ledger())
    reasonSuggestions.mockRejectedValue(new Error('offline'))
    renderPage()

    expect(await screen.findByRole('button', { name: 'Add points' })).toBeInTheDocument()
    expect(document.querySelectorAll('datalist option')).toHaveLength(0)
  })

  it('履歴が無ければその旨を出す', async () => {
    viewLedger.mockResolvedValue(ledger({ balance: 0, transactions: [] }))
    renderPage()

    expect(await screen.findByText('Nothing recorded yet.')).toBeInTheDocument()
  })

  it('最後に取得した時刻を出す（オフラインでは古いキャッシュが出得るため）', async () => {
    viewLedger.mockResolvedValue({
      ...ledger(),
      fetchedAt: new Date('2026-08-01T10:00:00Z'),
    })
    renderPage()

    await screen.findByText('100 pt')
    expect(screen.getByText(/As of /)).toBeInTheDocument()
  })

  it('取得時刻が読めない応答では時刻の行を出さない', async () => {
    viewLedger.mockResolvedValue(ledger())
    renderPage()

    await screen.findByText('100 pt')
    expect(screen.queryByText(/As of /)).not.toBeInTheDocument()
  })

  it('記録したら台帳と家族の両方を読み直す（他の画面の残高が古いまま残らない）', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockResolvedValue(ledger({ balance: 150 }))
    record.mockResolvedValue(transaction({ id: 2, amount: 50 }))
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(reloadFamily)

    await screen.findByText('100 pt')
    addPoints()

    expect(await screen.findByText('150 pt')).toBeInTheDocument()
    expect(reloadFamily).toHaveBeenCalled()
  })

  it('取り消しでも家族を読み直す（残高が減るのはどの画面でも同じ）', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockResolvedValue(ledger({ balance: 0 }))
    reverse.mockResolvedValue(transaction({ id: 2, amount: -100, reversal_of_id: 1 }))
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(reloadFamily)

    await screen.findByText('100 pt')
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))

    expect(await screen.findByText('0 pt')).toBeInTheDocument()
    expect(reloadFamily).toHaveBeenCalled()
  })

  it('記録に失敗したら読み直さない（無かった記録を映さない）', async () => {
    viewLedger.mockResolvedValue(ledger())
    record.mockRejectedValue(new Error('offline'))
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(reloadFamily)

    await screen.findByText('100 pt')
    addPoints()

    await waitFor(() => {
      expect(record).toHaveBeenCalled()
    })
    expect(reloadFamily).not.toHaveBeenCalled()
    expect(viewLedger).toHaveBeenCalledTimes(1)
  })

  it('手元に戻ってきたら読み直す（別の端末で足された分を映す）', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockResolvedValue(ledger({ balance: 150 }))
    renderPage()

    await screen.findByText('100 pt')
    fireEvent(document, new Event('visibilitychange'))

    expect(await screen.findByText('150 pt')).toBeInTheDocument()
  })

  it('読み直しに失敗しても、出している残高は消さない', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockRejectedValue(new Error('offline'))
    renderPage()

    await screen.findByText('100 pt')
    fireEvent(document, new Event('visibilitychange'))

    await waitFor(() => {
      expect(viewLedger).toHaveBeenCalledTimes(2)
    })
    expect(screen.getByText('100 pt')).toBeInTheDocument()
    expect(screen.queryByText('These points could not be loaded.')).not.toBeInTheDocument()
  })

  it('訂正の後は入力候補も取り直す（直した書き間違いを選び直させない）', async () => {
    viewLedger.mockResolvedValue(ledger())
    reasonSuggestions.mockResolvedValueOnce(['おてつだいい']).mockResolvedValue(['おてつだい'])
    correct.mockResolvedValue({
      reversal: transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
      correction: transaction({ id: 3, corrects_id: 1 }),
    })
    renderPage()

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.click(screen.getByRole('button', { name: 'Save as added points' }))

    await waitFor(() => {
      expect(reasonSuggestions).toHaveBeenCalledTimes(2)
    })
    const options = document.querySelectorAll('datalist option')
    expect([...options].map((option) => option.getAttribute('value'))).toEqual(['おてつだい'])
  })

  it('訂正を選ぶと、元の内容が入った入力欄に替わる', async () => {
    viewLedger.mockResolvedValue(
      ledger({ transactions: [transaction({ amount: -60, reason: 'おかし' })] }),
    )
    renderPage()

    await screen.findByText('-60 pt')
    startCorrection()

    // 符号はボタンで決めるので、入力欄には絶対値が入る
    expect(await screen.findByLabelText('Points')).toHaveValue(60)
    expect(screen.getByLabelText('Reason')).toHaveValue('おかし')
    // 記録の入力欄とは入れ替わる（どちらへ打っているのか分からなくならない）
    expect(screen.queryByRole('button', { name: 'Add points' })).not.toBeInTheDocument()
  })

  it('訂正を送ると、直した内容と符号でその記録を指して送る', async () => {
    viewLedger.mockResolvedValueOnce(ledger()).mockResolvedValue(ledger({ balance: 50 }))
    correct.mockResolvedValue({
      reversal: transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
      correction: transaction({ id: 3, amount: 50, corrects_id: 1 }),
    })
    const reloadFamily = vi.fn<() => Promise<void>>().mockResolvedValue()
    renderPage(reloadFamily)

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.change(screen.getByLabelText('Points'), { target: { value: '50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save as added points' }))

    expect(await screen.findByText('50 pt')).toBeInTheDocument()
    expect(correct).toHaveBeenCalledWith(1, {
      amount: 50,
      reason: 'おてつだい',
      idempotencyKey: 'test-key',
    })
    // 残高はどの画面でも同じなので、家族も読み直す（ADR-0021）
    expect(reloadFamily).toHaveBeenCalled()
    // 通ったら入力欄は記録用に戻る
    expect(await screen.findByRole('button', { name: 'Add points' })).toBeInTheDocument()
  })

  it('符号の付け間違いは消費として保存し直せる', async () => {
    viewLedger.mockResolvedValue(ledger())
    correct.mockResolvedValue({
      reversal: transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
      correction: transaction({ id: 3, amount: -100, corrects_id: 1 }),
    })
    renderPage()

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.click(screen.getByRole('button', { name: 'Save as used points' }))

    await waitFor(() => {
      expect(correct).toHaveBeenCalledWith(1, expect.objectContaining({ amount: -100 }))
    })
  })

  it('訂正に失敗したら入力欄を閉じない（直した内容を打ち直させない）', async () => {
    viewLedger.mockResolvedValue(ledger())
    correct.mockRejectedValue(new Error('offline'))
    renderPage()

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.change(screen.getByLabelText('Points'), { target: { value: '50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save as added points' }))

    await waitFor(() => {
      expect(correct).toHaveBeenCalled()
    })
    expect(screen.getByLabelText('Points')).toHaveValue(50)
    expect(viewLedger).toHaveBeenCalledTimes(1)
  })

  it('やめれば記録の入力欄へ戻る', async () => {
    viewLedger.mockResolvedValue(ledger())
    renderPage()

    await screen.findByText('100 pt')
    startCorrection()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(await screen.findByRole('button', { name: 'Add points' })).toBeInTheDocument()
    expect(correct).not.toHaveBeenCalled()
  })

  it('打ち消しと訂正の行には、それと分かる印を付ける', async () => {
    viewLedger.mockResolvedValue(
      ledger({
        balance: 50,
        transactions: [
          transaction({ id: 3, amount: 50, corrects_id: 1 }),
          transaction({ id: 2, amount: -100, reversal_of_id: 1 }),
          transaction({ id: 1, is_reversed: true }),
        ],
      }),
    )
    renderPage()

    await screen.findByText('50 pt')
    expect(screen.getByText(/\(correction\)/)).toBeInTheDocument()
    expect(screen.getByText(/\(undo\)/)).toBeInTheDocument()
    // 直せるのは打ち消しでも打ち消し済みでもない行だけ（ここでは訂正後の 1 行）
    expect(screen.getAllByRole('button', { name: 'Correct' })).toHaveLength(1)
  })

  it('記録に失敗したら入力を残す（同じ鍵で送り直せる）', async () => {
    viewLedger.mockResolvedValue(ledger())
    record.mockRejectedValue(new Error('offline'))
    renderPage()

    await screen.findByText('100 pt')
    addPoints()

    await waitFor(() => {
      expect(record).toHaveBeenCalled()
    })
    expect(screen.getByLabelText('Points')).toHaveValue(50)
    expect(screen.getByLabelText('Reason')).toHaveValue('おてつだい')
  })

  it('別の子へ移ったら、前の子の残高を出したまま待たない', async () => {
    viewLedger
      .mockResolvedValueOnce(ledger())
      .mockReturnValue(new Promise<Fetched<Ledger>>(() => undefined))
    renderPage()

    await screen.findByText('100 pt')
    fireEvent.click(screen.getByRole('link', { name: 'タロウ' }))

    expect(screen.queryByText('100 pt')).not.toBeInTheDocument()
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })
})
