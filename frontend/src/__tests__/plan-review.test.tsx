import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as api from '../api'
import { PlanReview } from '../components/PlanReview'
import type { JobState } from '../types'

vi.mock('../api')
beforeEach(() => {
  vi.mocked(api.timeline).mockResolvedValue({ bpm: null, beat_times: [1, 2], shots: [{ id: 'SHOT_001', cuts: [1.5], effects: ['zoom', 'transition:flash'], text: 'HELLO' }, { id: 'SHOT_002', cuts: [], effects: [] }] })
})
afterEach(cleanup)

const job = {
  id: 'j1', status: 'review', generation_budget: { seconds: 20, with_retries: 40, final_seconds: 8 },
  shots: [
    { id: 'SHOT_001', start: 0, duration: 4, prompt: 'one', render_source: 'generated' },
    { id: 'SHOT_002', start: 4, duration: 4, prompt: 'two', render_source: 'graphic' },
  ],
} as unknown as JobState
const view = (props = {}) => render(<PlanReview job={job} busy={false} onApprove={vi.fn()} onRefuse={vi.fn()} onClose={vi.fn()} {...props} />)

test('is a window with the shots on a timeline and the GPU time they will cost', () => {
  view()
  expect(screen.getByRole('dialog', { name: 'Plan to approve' })).toBeTruthy()
  expect(screen.getByText(/2 shots \(1 not generated\)/)).toBeTruthy()
  expect(screen.getByText(/GPU ≈ 20s \(40s with retries\)/)).toBeTruthy()
  expect(screen.getByRole('button', { name: /#001/ })).toBeTruthy()
  expect(screen.getByRole('button', { name: /#002/ })).toBeTruthy()
})

test('shows the cuts, the effects and the text the plan gives the chosen shot', async () => {
  view()
  await waitFor(() => expect(screen.getByText('2 cuts')).toBeTruthy())
  expect(screen.getByText('zoom')).toBeTruthy()
  expect(screen.getByText('→ flash')).toBeTruthy()
  expect(screen.getByText('“HELLO”')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: /#002/ }))
  expect((screen.getByLabelText('Prompt of shot SHOT_002') as HTMLTextAreaElement).disabled).toBe(true)
  expect(screen.queryByText('2 cuts')).toBeNull()
})

test('approving sends only the prompts that were changed', () => {
  const onApprove = vi.fn()
  view({ onApprove })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 1 shot(s)' }))
  expect(onApprove).toHaveBeenLastCalledWith({})
  fireEvent.change(screen.getByLabelText('Prompt of shot SHOT_001'), { target: { value: 'one, closer' } })
  fireEvent.click(screen.getByRole('button', { name: 'Generate 1 shot(s)' }))
  expect(onApprove).toHaveBeenLastCalledWith({ SHOT_001: 'one, closer' })
})

test('the plan can be refused, or the window closed to decide later; nothing can be pressed while busy', () => {
  const onRefuse = vi.fn(), onClose = vi.fn()
  const { rerender } = view({ onRefuse, onClose })
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  fireEvent.click(screen.getByRole('button', { name: 'Close, decide later' }))
  expect(onRefuse).toHaveBeenCalledTimes(1)
  expect(onClose).toHaveBeenCalledTimes(1)
  rerender(<PlanReview job={job} busy onApprove={vi.fn()} onRefuse={onRefuse} onClose={onClose} />)
  expect((screen.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled).toBe(true)
})
