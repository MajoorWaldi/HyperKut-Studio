import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import * as api from '../api'
import { AICandidatePanel } from '../components/AICandidatePanel'
import { ShotPanel } from '../components/ShotPanel'
import { dictionaries, I18n } from '../i18n'
import type { AICandidate, JobState, Shot, Take } from '../types'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
const shot: Shot = { id: 'SHOT_001', start: 0, duration: 1, prompt: 'editable correction', generation_prompt: 'exact generation',
  version: 1, locked: false, thumb: null, done: true, takes: 1, render_source: 'generated' }
const take: Take = { id: 'take_001', active: true, url: '/old.mp4', generation_prompt: 'exact generation' }
const job: JobState = { id: 'test', mode: 'remix', status: 'succeeded', stage: 'done', progress: 1, node: null,
  step: null, steps: null, shots: [shot], output_url: '/old-export.mp4', error: null, project_id: 'p_0123456789ab',
  style: {}, preview: 0, title: '', created_at: 1, pinned: false }
const candidate: AICandidate = { id: 'a'.repeat(24), shot_id: shot.id, operation: 'extend_after', status: 'ready',
  take: take.id, prompt: 'continuation', seed: 17, duration: 1.5, generated_seconds: 124 / 24, error: null, revision_id: null, url: '/candidate.mp4' }

test('default-off capability renders no experimental controls', async () => {
  const list = vi.spyOn(api, 'aiCandidates').mockResolvedValue({ enabled: false, candidates: [] })
  const { container } = render(<AICandidatePanel job={job} shot={shot} take={take} prompt="shared prompt" onState={vi.fn()} />)
  await waitFor(() => expect(list).toHaveBeenCalled())
  expect(container.textContent).toBe('')
})

test('extension reuses the shared shot prompt without duplicate prompt or regeneration controls', async () => {
  vi.spyOn(api, 'aiCandidates').mockResolvedValue({ enabled: true, candidates: [] })
  const launch = vi.spyOn(api, 'startAICandidate').mockResolvedValue({ job: { ...job, status: 'running' }, candidate })
  const accept = vi.spyOn(api, 'decideAICandidate')
  const state = vi.fn()
  render(<AICandidatePanel job={job} shot={shot} take={take} prompt="shared edited prompt" onState={state} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Extend take' }))
  await waitFor(() => expect(launch).toHaveBeenCalledWith(job.id, shot.id,
    { operation: 'extend_after', take: 'take_001', prompt: 'shared edited prompt', seconds: 3, seed: 42 }))
  expect(screen.queryByRole('textbox')).toBeNull()
  expect(screen.queryByRole('combobox')).toBeNull()
  expect(screen.queryByRole('button', { name: /regenerate/i })).toBeNull()
  expect(accept).not.toHaveBeenCalled()
  expect(state).toHaveBeenCalledWith(expect.objectContaining({ status: 'running' }))
})

test('extension requires an explicit accept confirmation and leaves the existing export untouched', async () => {
  vi.spyOn(api, 'aiCandidates').mockResolvedValue({ enabled: true, candidates: [candidate] })
  const decide = vi.spyOn(api, 'decideAICandidate').mockResolvedValue(job)
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  const state = vi.fn()
  const { container } = render(<AICandidatePanel job={job} shot={shot} take={take} prompt="shared prompt" onState={state} />)
  const button = await screen.findByRole('button', { name: 'Accept this raw take' })
  expect(container.querySelector('video')?.getAttribute('src')).toBe('/candidate.mp4')
  expect(container.querySelectorAll('video')).toHaveLength(1)
  fireEvent.click(button)
  expect(confirm).toHaveBeenCalledWith(expect.stringContaining('not one timeline occurrence'))
  expect(decide).not.toHaveBeenCalled()
  confirm.mockReturnValue(true)
  fireEvent.click(button)
  await waitFor(() => expect(decide).toHaveBeenCalledWith(job.id, candidate.id, 'accept'))
  expect(state).toHaveBeenCalledWith(expect.objectContaining({ output_url: '/old-export.mp4' }))
})

test('inactive takes and locked shots cannot launch experiments; ready candidates can be rejected', async () => {
  vi.spyOn(api, 'aiCandidates').mockResolvedValue({ enabled: true, candidates: [candidate] })
  const decide = vi.spyOn(api, 'decideAICandidate').mockResolvedValue(job)
  const { rerender } = render(<AICandidatePanel job={job} shot={shot} take={{ ...take, active: false }} prompt="shared prompt" onState={vi.fn()} />)
  expect((await screen.findByRole('button', { name: 'Extend take' }) as HTMLButtonElement).disabled).toBe(true)
  rerender(<AICandidatePanel job={job} shot={{ ...shot, locked: true }} take={take} prompt="shared prompt" onState={vi.fn()} />)
  expect((screen.getByRole('button', { name: 'Reject candidate' }) as HTMLButtonElement).disabled).toBe(true)
  rerender(<AICandidatePanel job={job} shot={shot} take={take} prompt="shared prompt" onState={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Reject candidate' }))
  await waitFor(() => expect(decide).toHaveBeenCalledWith(job.id, candidate.id, 'reject'))
})

test('French extension controls submit a new duration and surface failures', async () => {
  vi.spyOn(api, 'aiCandidates').mockResolvedValue({ enabled: true, candidates: [] })
  const launch = vi.spyOn(api, 'startAICandidate').mockRejectedValue(new Error('GPU unavailable'))
  render(<I18n.Provider value={{ lang: 'fr', t: dictionaries.fr, setLang: vi.fn() }}>
    <AICandidatePanel job={job} shot={shot} take={take} prompt="shared prompt" onState={vi.fn()} />
  </I18n.Provider>)
  fireEvent.click(await screen.findByRole('button', { name: 'Étendre avant' }))
  fireEvent.change(screen.getByRole('spinbutton', { name: 'Secondes supplémentaires' }), { target: { value: '2' } })
  fireEvent.click(screen.getByRole('button', { name: 'Étendre la prise' }))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'GPU unavailable')
  expect(launch).toHaveBeenCalledWith(job.id, shot.id, expect.objectContaining({ operation: 'extend_before', seconds: 2 }))
})

test('running candidates offer cancellation and failed candidates never offer acceptance', async () => {
  vi.spyOn(api, 'aiCandidates').mockResolvedValue({ enabled: true, candidates: [{ ...candidate, status: 'running', url: null }] })
  const cancel = vi.spyOn(api, 'cancelJob').mockResolvedValue({ ...job, status: 'cancelled' })
  const state = vi.fn()
  render(<AICandidatePanel job={{ ...job, status: 'running' }} shot={shot} take={take} prompt="shared prompt" onState={state} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel candidate' }))
  await waitFor(() => expect(cancel).toHaveBeenCalledWith(job.id))
  expect(screen.queryByRole('button', { name: 'Accept this raw take' })).toBeNull()
  expect(state).toHaveBeenCalledWith(expect.objectContaining({ status: 'cancelled' }))
})

test('extension direction survives loading and always submits the latest shared prompt', async () => {
  vi.spyOn(api, 'aiCandidates').mockResolvedValue({ enabled: true, candidates: [] })
  const launch = vi.spyOn(api, 'startAICandidate').mockResolvedValue({ job: { ...job, status: 'running' }, candidate })
  const state = vi.fn()
  const { rerender } = render(<AICandidatePanel job={job} shot={shot} take={take} prompt="original" onState={state} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Extend before' }))
  rerender(<AICandidatePanel job={{ ...job, status: 'running' }} shot={shot} take={null} prompt="original" onState={state} />)
  rerender(<AICandidatePanel job={job} shot={shot} take={take} prompt="my continuation" onState={state} />)
  expect(screen.getByRole('button', { name: 'Extend before' }).getAttribute('aria-pressed')).toBe('true')
  fireEvent.click(screen.getByRole('button', { name: 'Extend take' }))
  await waitFor(() => expect(launch).toHaveBeenCalledWith(job.id, shot.id,
    expect.objectContaining({ operation: 'extend_before', prompt: 'my continuation' })))
})

test.each(['text', 'remix'] as const)('ShotPanel %s shares its edited prompt and keeps one existing regenerate action', async mode => {
  vi.spyOn(api, 'takes').mockResolvedValue([take])
  vi.spyOn(api, 'aiCandidates').mockResolvedValue({ enabled: true, candidates: [] })
  const launch = vi.spyOn(api, 'startAICandidate').mockResolvedValue({ job: { ...job, status: 'running' }, candidate })
  const regenerate = vi.fn()
  render(<ShotPanel job={{ ...job, mode }} primary={0} selection={[]} edits={{ [shot.id]: 'continue walking' }}
    quality="standard" onEdit={vi.fn()} onStep={vi.fn()} onRegenerate={regenerate} onLock={vi.fn()}
    onChooseTake={vi.fn()} onTrimTake={vi.fn()} onAIState={vi.fn()} />)
  const extend = await screen.findByRole('button', { name: 'Extend take' })
  await waitFor(() => expect((extend as HTMLButtonElement).disabled).toBe(false))
  expect(screen.getAllByRole('textbox')).toHaveLength(mode === 'remix' ? 2 : 1)
  expect(screen.getAllByRole('button', { name: /^Regenerate/ })).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: /^Regenerate/ }))
  expect(regenerate).toHaveBeenCalledWith([shot.id], true)
  fireEvent.click(screen.getByRole('button', { name: 'Extend before' }))
  fireEvent.click(extend)
  await waitFor(() => expect(launch).toHaveBeenCalledWith(job.id, shot.id, expect.objectContaining({
    operation: 'extend_before',
    prompt: mode === 'remix' ? 'exact generation\n\nRequested changes: continue walking' : 'continue walking',
  })))
})
