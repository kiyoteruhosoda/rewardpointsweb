/**
 * The pet panel on the ledger screen (ADR-0061): how far to the next stage, choosing the kind,
 * and a celebration once per screen when the stage has gone up.
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type * as PetModule from '../services/pet'
import type { Pet, PetSpecies } from '../services/pet'
import { pet } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { PetPanel } from './PetPanel'

const choose = vi.fn<(species: PetSpecies) => Promise<Pet>>()

vi.mock('../services/pet', async (importOriginal) => ({
  ...(await importOriginal<typeof PetModule>()),
  petApi: {
    choose: (_family: number, _ledger: number, species: PetSpecies) => choose(species),
  },
}))

/** Holds the pet like the ledger screen does, so a choice comes back as the new prop. */
function WithState({ initial }: { initial: Pet }) {
  const [value, setValue] = useState(initial)
  return <PetPanel familyId={1} ledgerId={20} pet={value} onChanged={setValue} />
}

function renderPanel(value: Pet, onChanged: (pet: Pet) => void = () => undefined) {
  return renderWithProviders(
    <PetPanel familyId={1} ledgerId={20} pet={value} onChanged={onChanged} />,
  )
}

describe('PetPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.removeItem('pet-seen-stage:20')
    vi.spyOn(window, 'confirm').mockReturnValue(true)
  })

  it('shows the stage and how many points the next one needs', () => {
    renderPanel(pet({ stage: 1, earned: 40, next_threshold: 100 }))

    expect(screen.getByText('Just hatched')).toBeInTheDocument()
    expect(
      screen.getByText('Points earned since the egg arrived (not counting the daily bonus): 40 pt'),
    ).toBeInTheDocument()
    expect(screen.getByText('60 pt to the next stage')).toBeInTheDocument()
    expect(screen.getByText('Spending points never makes it smaller.')).toBeInTheDocument()
  })

  it('at the final stage says it is fully grown', () => {
    renderPanel(pet({ stage: 5, earned: 2000, current_threshold: 1500, next_threshold: null }))

    expect(screen.getByText('Fully grown!')).toBeInTheDocument()
  })

  it('an egg without a kind asks which one it will be, and sends the choice', async () => {
    const chosen = pet({
      species: 'rabbit',
      stage: 0,
      earned: 0,
      current_threshold: 0,
      next_threshold: 30,
    })
    choose.mockResolvedValue(chosen)
    const onChanged = vi.fn<(pet: Pet) => void>()
    renderPanel(
      pet({
        species: null,
        stage: 0,
        earned: 0,
        current_threshold: 0,
        next_threshold: 30,
        can_choose: true,
      }),
      onChanged,
    )

    expect(screen.getByText('Which one will it be?')).toBeInTheDocument()
    expect(
      screen.getByText(
        'It grows with the points earned from the day you choose (not the daily bonus).',
      ),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Bunny' }))

    await waitFor(() => {
      expect(choose).toHaveBeenCalledWith('rabbit')
    })
    expect(onChanged).toHaveBeenCalledWith(chosen)
  })

  it('an egg without a kind is called an egg and does not celebrate when chosen', async () => {
    const egg = pet({
      species: null,
      stage: 0,
      earned: 0,
      current_threshold: 0,
      next_threshold: 100,
      can_choose: true,
    })
    choose.mockResolvedValue({ ...egg, species: 'dragon', can_choose: false })
    renderWithProviders(<WithState initial={egg} />)
    expect(screen.getByText('Egg')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Dragon' }))

    await waitFor(() => {
      expect(choose).toHaveBeenCalledWith('dragon')
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('a growing pet offers no way to change its kind', () => {
    renderPanel(pet({ species: 'cat', stage: 2, can_choose: false }))

    expect(screen.queryByRole('button', { name: 'Bunny' })).not.toBeInTheDocument()
  })

  it('asks before choosing, since the kind cannot change later', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderPanel(pet({ species: null, stage: 0, earned: 0, can_choose: true }))

    fireEvent.click(screen.getByRole('button', { name: 'Bunny' }))

    await waitFor(() => {
      expect(confirm).toHaveBeenCalledWith("Choose Bunny? It can't be changed while it grows.")
    })
    expect(choose).not.toHaveBeenCalled()
  })

  it('a fully grown pet offers the next one, and the raised ones are listed', () => {
    renderPanel(
      pet({
        species: 'cat',
        stage: 5,
        earned: 12000,
        current_threshold: 10000,
        next_threshold: null,
        can_choose: true,
        raised: ['rabbit'],
      }),
    )

    expect(screen.getByText('Fully grown! Raise the next one?')).toBeInTheDocument()
    expect(screen.getByText('The next one starts again from an egg at 0 pt.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Birdie' })).toBeInTheDocument()
    expect(screen.getByText('Raised so far: 1')).toBeInTheDocument()
  })

  it('someone who cannot choose sees no picker', () => {
    renderPanel(pet({ species: null, can_choose: false }))

    expect(screen.getByText("The kind isn't chosen yet.")).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Bunny' })).not.toBeInTheDocument()
  })

  it('celebrates when the stage went up since this screen last showed it, once', () => {
    localStorage.setItem('pet-seen-stage:20', '1')
    const { unmount } = renderPanel(pet({ stage: 2 }))

    expect(screen.getByRole('dialog', { name: 'It grew!' })).toHaveTextContent('Now: Baby')
    fireEvent.click(screen.getByRole('button', { name: 'Yay!' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    unmount()

    renderPanel(pet({ stage: 2 }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('the first time a screen sees the pet it only remembers the stage', () => {
    renderPanel(pet({ stage: 3 }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(localStorage.getItem('pet-seen-stage:20')).toBe('3')
  })
})
