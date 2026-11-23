/**
 * The pet panel on the ledger screen (ADR-0061): how far to the next stage, choosing the kind,
 * a celebration once per screen when the stage has gone up, and caring for a hatched pet
 * (task #1128).
 */
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type * as PetModule from '../services/pet'
import type { Pet, PetCareKind, PetSpecies } from '../services/pet'
import { pet } from '../test-support/familyFixtures'
import { renderWithProviders } from '../test-support/renderWithProviders'
import { PetPanel } from './PetPanel'

const choose = vi.fn<(species: PetSpecies) => Promise<Pet>>()
const care = vi.fn<(kind: PetCareKind) => Promise<Pet>>()

vi.mock('../services/pet', async (importOriginal) => ({
  ...(await importOriginal<typeof PetModule>()),
  petApi: {
    choose: (_family: number, _ledger: number, species: PetSpecies) => choose(species),
    care: (_family: number, _ledger: number, kind: PetCareKind) => care(kind),
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
    localStorage.removeItem('pet-seen-care:20')
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

  it('celebrates a hatching when the pet came out of the egg since the last look', () => {
    localStorage.setItem('pet-seen-stage:20', '0')

    renderPanel(pet({ stage: 1 }))

    expect(screen.getByRole('dialog', { name: 'It hatched!' })).toHaveTextContent(
      'Now: Just hatched',
    )
  })

  it('a hatched pet shows its mood and friendship, and the four cares when allowed', () => {
    renderPanel(
      pet({
        can_care: true,
        care: {
          mood: 75,
          mood_level: 'happy',
          days_cared: 4,
          last_kind: null,
          last_cared_at: null,
        },
      }),
    )

    expect(screen.getByText('Mood: Happy')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Mood' })).toHaveAttribute('aria-valuenow', '75')
    expect(screen.getByText('Friendship: 4 days')).toBeInTheDocument()
    for (const name of ['Food', 'Pat', 'Play', 'Bath']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
    expect(
      screen.getByText("Caring costs no points, and it doesn't change how it grows."),
    ).toBeInTheDocument()
  })

  it('a care plays and then says in words what happened and how the pet feels', async () => {
    const before = pet({ can_care: true })
    care.mockResolvedValue({
      ...before,
      care: {
        mood: 75,
        mood_level: 'happy',
        days_cared: 4,
        last_kind: 'feed',
        last_cared_at: '2026-11-23T02:00:00Z',
      },
    })
    renderWithProviders(<WithState initial={before} />)

    fireEvent.click(screen.getByRole('button', { name: 'Food' }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(
        'You gave it food. Munch munch! Mood: Happy',
      )
    })
    expect(care).toHaveBeenCalledWith('feed')
    // Growth stays as it was
    expect(screen.getByText('60 pt to the next stage')).toBeInTheDocument()
  })

  it('someone who may not care for it sees the mood but no buttons', () => {
    renderPanel(pet({ can_care: false }))

    expect(screen.getByText('Mood: Okay')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Food' })).not.toBeInTheDocument()
  })

  it('a lonely pet says so and that caring cheers it up', () => {
    renderPanel(
      pet({
        can_care: true,
        care: {
          mood: 10,
          mood_level: 'lonely',
          days_cared: 2,
          last_kind: 'pat',
          last_cared_at: null,
        },
      }),
    )

    expect(screen.getByText('Mood: Lonely')).toBeInTheDocument()
    expect(
      screen.getByText(
        'It has been a while without care, so it looks lonely. Caring for it cheers it up.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Just hatched')).toBeInTheDocument()
  })

  it('an egg has no care buttons, and a chosen egg says caring starts once it hatches', () => {
    const { unmount } = renderPanel(
      pet({ species: null, stage: 0, earned: 0, care: null, can_care: false }),
    )
    expect(screen.queryByRole('button', { name: 'Food' })).not.toBeInTheDocument()
    unmount()

    renderPanel(pet({ species: 'cat', stage: 0, earned: 20, care: null, can_care: false }))
    expect(screen.getByText('You can care for it once it hatches.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Food' })).not.toBeInTheDocument()
  })
})
