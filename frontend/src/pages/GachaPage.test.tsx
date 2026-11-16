/**
 * Gacha screen (ADR-0060): the draw button follows the balance, a press shows the prize big,
 * a retried press reuses its key, and only parents get the setup and "handed over" controls.
 */
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type * as GachaModule from '../services/gacha'
import type {
  Gacha,
  GachaBoard,
  GachaBundleResult,
  GachaDraw,
  GachaDrawResult,
  GachaTrial,
} from '../services/gacha'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { GachaPage } from './GachaPage'

const board = vi.fn<() => Promise<GachaBoard>>()
const draw = vi.fn<(gachaId: number, key: string) => Promise<GachaDrawResult>>()
const handOver = vi.fn<(drawId: number) => Promise<GachaDraw>>()
const trial = vi.fn<(gachaId: number) => Promise<GachaTrial>>()
const bundle = vi.fn<(gachaId: number, key: string) => Promise<GachaBundleResult>>()
const create = vi.fn<() => Promise<Gacha>>()

let keys = 0

vi.mock('../services/families', () => ({
  newIdempotencyKey: () => `key-${++keys}`,
  parseUtc: (value: string) => new Date(value),
}))

/** Resolves the wait for the handle to turn. Immediate unless a test holds it. */
let turned: Promise<void> = Promise.resolve()

vi.mock('../services/gachaShow', () => ({
  waitForTurn: () => turned,
}))

vi.mock('../services/gacha', async (importOriginal) => {
  const actual = await importOriginal<typeof GachaModule>()
  return {
    ...actual,
    gacha: {
      board: () => board(),
      draw: (_family: number, _ledger: number, gachaId: number, key: string) => draw(gachaId, key),
      handOver: (_family: number, _ledger: number, drawId: number) => handOver(drawId),
      trial: (_family: number, _ledger: number, gachaId: number) => trial(gachaId),
      bundle: (_family: number, _ledger: number, gachaId: number, key: string) =>
        bundle(gachaId, key),
      takeBackHandOver: () => Promise.reject(new Error('not used')),
      create: () => create(),
      update: () => Promise.reject(new Error('not used')),
      remove: () => Promise.reject(new Error('not used')),
    },
  }
})

function machine(overrides: Partial<Gacha> = {}): Gacha {
  return {
    id: 7,
    ledger_id: 20,
    name: 'おかしガチャ',
    price: 30,
    prizes: [
      { name: 'チョコ', weight: 1, is_miss: false },
      { name: 'グミ', weight: 2, is_miss: false },
      { name: 'はずれ', weight: 1, is_miss: true },
    ],
    created_at: '2026-11-15T00:00:00Z',
    ...overrides,
  }
}

function won(overrides: Partial<GachaDraw> = {}): GachaDraw {
  return {
    id: 100,
    gacha_id: 7,
    gacha_name: 'おかしガチャ',
    prize_name: 'グミ',
    is_miss: false,
    price: 30,
    drawn_at: '2026-11-15T01:00:00Z',
    handed_over_at: null,
    is_bonus: false,
    ...overrides,
  }
}

function boardOf(overrides: Partial<GachaBoard> = {}): GachaBoard {
  return {
    ledger_id: 20,
    display_name: 'ハナ',
    balance: 100,
    can_modify: true,
    can_draw: true,
    gachas: [machine()],
    draws: [],
    ...overrides,
  }
}

function renderPage() {
  return renderWithProviders(<GachaPage />, {
    route: '/families/1/ledgers/20/gacha',
    path: '/families/:familyId/ledgers/:ledgerId/gacha',
  })
}

const drawButton = () => screen.findByRole('button', { name: 'Draw おかしガチャ for 30 pt' })

describe('GachaPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    keys = 0
    turned = Promise.resolve()
  })

  it('shows each prize with its chance', async () => {
    board.mockResolvedValue(boardOf())
    renderPage()

    const card = await screen.findByRole('article', { name: 'おかしガチャ' })
    expect(within(card).getByText('30 pt a draw')).toBeInTheDocument()
    expect(within(card).getByText('チョコ')).toBeInTheDocument()
    // チョコ and はずれ both have weight 1 of 4
    expect(within(card).getAllByText('25%')).toHaveLength(2)
    expect(within(card).getByText('50%')).toBeInTheDocument()
  })

  it('cannot draw when the balance does not cover the price, and says how much is missing', async () => {
    board.mockResolvedValue(boardOf({ balance: 20 }))
    renderPage()

    expect(await drawButton()).toBeDisabled()
    expect(screen.getByText('10 pt more to draw')).toBeInTheDocument()
  })

  it('shows the prize big after a draw and updates the balance', async () => {
    board.mockResolvedValue(boardOf())
    draw.mockResolvedValue({ draw: won(), balance: 70 })
    renderPage()

    fireEvent.click(await drawButton())

    const dialog = await screen.findByRole('dialog', { name: 'You got it!' })
    expect(within(dialog).getByText('グミ')).toBeInTheDocument()
    expect(within(dialog).getByText(/70 pt left/)).toBeInTheDocument()
    expect(draw).toHaveBeenCalledWith(7, 'key-1')
    // The new prize is in the history, waiting to be handed over
    expect(screen.getByText('Not handed over yet: 1')).toBeInTheDocument()

    fireEvent.click(within(dialog).getByRole('button', { name: 'Yay!' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('a miss says so instead of celebrating', async () => {
    board.mockResolvedValue(boardOf())
    draw.mockResolvedValue({ draw: won({ prize_name: 'はずれ', is_miss: true }), balance: 70 })
    renderPage()

    fireEvent.click(await drawButton())

    expect(
      await screen.findByRole('dialog', { name: 'A miss… better luck next time!' }),
    ).toBeInTheDocument()
  })

  it('a press that failed to arrive is retried with the same key (never drawn twice)', async () => {
    board.mockResolvedValue(boardOf())
    draw
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ draw: won(), balance: 70 })
    renderPage()

    fireEvent.click(await drawButton())
    await waitFor(() => {
      expect(draw).toHaveBeenCalledTimes(1)
    })
    fireEvent.click(await drawButton())

    await screen.findByRole('dialog')
    expect(draw.mock.calls.map(([, key]) => key)).toEqual(['key-1', 'key-1'])
  })

  it('a child can draw but sees no setup and cannot mark prizes handed over', async () => {
    board.mockResolvedValue(boardOf({ can_modify: false, draws: [won()] }))
    renderPage()

    expect(await drawButton()).toBeEnabled()
    expect(screen.queryByText('Make a gacha')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(screen.getByText('Not yet')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Mark グミ as handed over' }),
    ).not.toBeInTheDocument()
  })

  it('a parent marks a won prize handed over', async () => {
    board.mockResolvedValue(boardOf({ draws: [won()] }))
    handOver.mockResolvedValue(won({ handed_over_at: '2026-11-15T02:00:00Z' }))
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Mark グミ as handed over' }))

    await waitFor(() => {
      expect(handOver).toHaveBeenCalledWith(100)
    })
    expect(
      await screen.findByRole('button', { name: 'Undo handing over グミ' }),
    ).toBeInTheDocument()
  })

  it('a machine of only misses cannot be saved', async () => {
    board.mockResolvedValue(boardOf({ gachas: [] }))
    renderPage()

    fireEvent.click(await screen.findByLabelText('Miss'))

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Add at least one prize that is not a miss.',
    )
    expect(screen.getByRole('button', { name: 'Make' })).toBeDisabled()
  })

  it("a parent's trial draw shows the prize marked as a trial and changes nothing", async () => {
    board.mockResolvedValue(boardOf({ balance: 0 }))
    trial.mockResolvedValue({ gacha_name: 'おかしガチャ', prize_name: 'チョコ', is_miss: false })
    renderPage()

    fireEvent.click(
      await screen.findByRole('button', { name: 'Try おかしガチャ without spending points' }),
    )

    const dialog = await screen.findByRole('dialog', { name: 'You got it!' })
    expect(within(dialog).getByText('チョコ')).toBeInTheDocument()
    expect(within(dialog).getByText('Trial — just for checking')).toBeInTheDocument()
    expect(within(dialog).getByText(/No points used, nothing recorded/)).toBeInTheDocument()
    expect(trial).toHaveBeenCalledWith(7)
    expect(draw).not.toHaveBeenCalled()
    expect(screen.getByText('Nothing drawn yet.')).toBeInTheDocument()
  })

  it('a child has no trial draw', async () => {
    board.mockResolvedValue(boardOf({ can_modify: false }))
    renderPage()

    await drawButton()
    expect(
      screen.queryByRole('button', { name: /without spending points/ }),
    ).not.toBeInTheDocument()
  })

  it('keeps the handle turning until the show is due, then shows the prize', async () => {
    board.mockResolvedValue(boardOf())
    draw.mockResolvedValue({ draw: won(), balance: 70 })
    let finishTurning: () => void = () => undefined
    turned = new Promise((resolve) => {
      finishTurning = resolve
    })
    renderPage()

    fireEvent.click(await drawButton())

    expect(await screen.findByText('Rattle, rattle…')).toBeInTheDocument()
    await waitFor(() => {
      expect(draw).toHaveBeenCalled()
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    finishTurning()

    expect(await screen.findByRole('dialog', { name: 'You got it!' })).toBeInTheDocument()
    expect(screen.queryByText('Rattle, rattle…')).not.toBeInTheDocument()
  })

  it('ten at once shows each of the eleven draws in turn, then all of them', async () => {
    board.mockResolvedValue(boardOf({ balance: 400 }))
    const draws = Array.from({ length: 11 }, (_, index) =>
      won({
        id: 200 + index,
        prize_name: index === 10 ? 'えほん' : 'グミ',
        is_bonus: index === 10,
      }),
    )
    bundle.mockResolvedValue({ draws, balance: 100 })
    renderPage()

    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Draw おかしガチャ 10 times for 300 pt and get 11 prizes',
      }),
    )

    for (let index = 1; index <= 10; index++) {
      const dialog = await screen.findByRole('dialog', { name: 'You got it!' })
      expect(within(dialog).getByText(`${index} / 11`)).toBeInTheDocument()
      fireEvent.click(within(dialog).getByRole('button', { name: 'Next' }))
      await waitFor(() => {
        expect(screen.queryByText(`${index} / 11`)).not.toBeInTheDocument()
      })
    }
    const last = await screen.findByRole('dialog', { name: 'You got it!' })
    expect(within(last).getByText('11 / 11 · Bonus')).toBeInTheDocument()
    fireEvent.click(within(last).getByRole('button', { name: 'See all' }))

    const summary = await screen.findByRole('dialog', { name: 'Results: 11 prizes!' })
    expect(within(summary).getAllByRole('listitem')).toHaveLength(11)
    expect(within(summary).getByText('Bonus')).toBeInTheDocument()
    expect(bundle).toHaveBeenCalledTimes(1)
  })

  it('ten at once cannot be pressed when the balance does not cover ten draws', async () => {
    board.mockResolvedValue(boardOf({ balance: 299 }))
    renderPage()

    expect(
      await screen.findByRole('button', {
        name: 'Draw おかしガチャ 10 times for 300 pt and get 11 prizes',
      }),
    ).toBeDisabled()
  })
})
