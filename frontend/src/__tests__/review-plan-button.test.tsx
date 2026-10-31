import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { InputsPanel } from '../components/InputsPanel'
import { dictionaries } from '../i18n'
import type { Inputs, Settings } from '../types'

vi.mock('../components/ArtDirection', () => ({ ArtDirection: () => null }))
afterEach(cleanup)

const inputs: Inputs = { source: null, refs: [null, null, null, null, null], refVideo: null, music: null, voice: null }
const view = (busy = false, onReviewPlan = vi.fn()) => {
  render(<InputsPanel mode="text" inputs={inputs} settings={{ prompt: '', audio: 'new', dialogue: '' } as Settings} busy={busy} onUpload={vi.fn()} onClear={vi.fn()} onSettings={vi.fn()} onReviewPlan={onReviewPlan} />)
  return onReviewPlan
}

test('a Review plan button under the options makes the plan only', () => {
  const onReviewPlan = view()
  const button = screen.getByRole('button', { name: 'Review plan' })
  expect(button.getAttribute('title')).toBe(dictionaries.en.tip.reviewPlan)
  fireEvent.click(button)
  expect(onReviewPlan).toHaveBeenCalledTimes(1)
})

test('it waits while a generation or an upload is going on', () => {
  view(true)
  expect((screen.getByRole('button', { name: 'Review plan' }) as HTMLButtonElement).disabled).toBe(true)
})

test('the plan is not an option any more: Generate alone goes on by itself', () => {
  view()
  expect(screen.queryByText('Approve the plan first')).toBeNull()
})
