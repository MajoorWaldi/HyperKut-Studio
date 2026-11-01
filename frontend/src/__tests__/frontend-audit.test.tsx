import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import * as api from '../api'
import { PlanReview } from '../components/PlanReview'
import { SecondsFieldForTest } from './secondsHarness'
import { beatGrid } from '../rhythm'
import { readDraft, readPreference, writeDraft, writePreference } from '../brand'
import { translatePresetSettings } from '../presets'
import { DEFAULTS } from '../settings'
import type { JobState, Preset } from '../types'

vi.mock('../api')
afterEach(() => { cleanup(); vi.restoreAllMocks() })

const job = { id: 'j1', status: 'review', shots: [
  { id: 'SHOT_001', start: 0, duration: 4, prompt: 'one' },
  { id: 'SHOT_002', start: 4, duration: 4, prompt: 'two', render_source: 'graphic' },
] } as unknown as JobState

test('a shot without render_source is generated, so its prompt stays editable and counted', () => {
  vi.mocked(api.timeline).mockResolvedValue({ bpm: null, beat_times: [], shots: [] })
  render(<PlanReview job={job} busy={false} onApprove={vi.fn()} onRefuse={vi.fn()} onClose={vi.fn()} />)
  expect((screen.getByLabelText('Prompt of shot SHOT_001') as HTMLTextAreaElement).disabled).toBe(false)
  expect(screen.getByText('Generate 1 shot(s)')).toBeTruthy()
})

test('hiding the plan keeps the edited prompts', () => {
  vi.mocked(api.timeline).mockResolvedValue({ bpm: null, beat_times: [], shots: [] })
  const { rerender } = render(<PlanReview job={job} hidden={false} busy={false} onApprove={vi.fn()} onRefuse={vi.fn()} onClose={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('Prompt of shot SHOT_001'), { target: { value: 'changed' } })
  rerender(<PlanReview job={job} hidden busy={false} onApprove={vi.fn()} onRefuse={vi.fn()} onClose={vi.fn()} />)
  rerender(<PlanReview job={job} hidden={false} busy={false} onApprove={vi.fn()} onRefuse={vi.fn()} onClose={vi.fn()} />)
  expect((screen.getByLabelText('Prompt of shot SHOT_001') as HTMLTextAreaElement).value).toBe('changed')
})

test('Escape closes the plan window', () => {
  vi.mocked(api.timeline).mockResolvedValue({ bpm: null, beat_times: [], shots: [] })
  const onClose = vi.fn()
  render(<PlanReview job={job} busy={false} onApprove={vi.fn()} onRefuse={vi.fn()} onClose={onClose} />)
  act(() => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })) })
  expect(onClose).toHaveBeenCalled()
})

test('blocked storage never breaks preferences or drafts', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  expect(readPreference('zoom')).toBeNull()
  expect(() => writePreference('zoom', '1')).not.toThrow()
  expect(readDraft('k')).toBeNull()
  expect(writeDraft('k', { a: 1 })).toBe(false)
})

test('a corrupt draft reads as no draft', () => {
  localStorage.setItem('k', '{not json')
  expect(readDraft('k')).toBeNull()
  localStorage.clear()
})

test('a language switch does not erase the approved brief when nothing was translated', () => {
  const preset = { id: 'p', name: 'p', description: '', mode: 'text', prompt: 'A', settings: {}, translations: {} } as unknown as Preset
  const current = { ...DEFAULTS, prompt: 'My own prompt', approved_brief: 'kept', approved_brief_context: 'ctx' }
  expect(translatePresetSettings(current, preset, 'fr')).toBe(current)
})

test('beatGrid finds the nearest beat on either side with a long beat list', () => {
  const ticks = Array.from({ length: 200000 }, (_, i) => i * 0.5)
  const grid = beatGrid([1.2, 3.3], 120, 100000, ticks)
  expect(grid?.medianMs).toBe(200)
})

test('typing an out-of-range duration shows the value that was kept', () => {
  const commit = vi.fn()
  render(<SecondsFieldForTest value={120} onCommit={commit} />)
  const field = screen.getByLabelText('seconds') as HTMLInputElement
  fireEvent.change(field, { target: { value: '500' } })
  fireEvent.blur(field)
  expect(commit).toHaveBeenCalledWith(120)
  expect(field.value).toBe('120')
})
