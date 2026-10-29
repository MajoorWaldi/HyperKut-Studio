import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createRef } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import * as api from '../api'
import { ManualTimeline } from '../components/ManualTimeline'
import { Preview } from '../components/Preview'
import { Timeline } from '../components/Timeline'
import type { JobState, ManualTimelinePayload, TimelineDocument, TimelineEditorModule } from '../types'

afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear() })
const job: JobState = { id: 'editor', mode: 'text', status: 'succeeded', stage: 'done', progress: 1, node: null,
  step: null, steps: null, shots: [], output_url: '/old.mp4', error: null, project_id: 'p_0123456789ab',
  style: {}, preview: 0, title: '', created_at: 1, pinned: false }
const document: TimelineDocument = { version: 1, project_id: job.project_id!, source_signature: 'source',
  fps_num: 24, fps_den: 1, clips: [{ id: 'clip_1', shot_id: 'SHOT_001', revision_id: 'take_001', in_frame: 0, out_frame: 24 }] }
const payload: ManualTimelinePayload = { initial: document, document, library: [{ id: 'SHOT_001',
  takes: [{ id: 'take_001', file: 'generated/red.mp4', frames: 72, offset: 0, prompt: 'red' }] }],
  music: { file: '@music', duration: 5, peaks: [0, 1, .2] }, etag: null, enabled: false, stale: false }
const key = 'secator.timeline.editor'
type Options = Parameters<TimelineEditorModule['openTimelineEditor']>[2]

function setup(data = payload) {
  const get = vi.spyOn(api, 'manualTimeline').mockResolvedValue(data)
  let options: Options
  const close = vi.fn(() => options?.onClose())
  const open = vi.fn<TimelineEditorModule['openTimelineEditor']>((_, __, callbacks) => { options = callbacks; return close })
  vi.spyOn(api, 'loadTimelineEditor').mockResolvedValue({ openTimelineEditor: open })
  const state = vi.fn()
  const component = render(<ManualTimeline job={job} onState={state} />)
  return { ...component, get, open, close, state, options: () => options }
}

async function openEditor() {
  const button = await screen.findByRole('button', { name: 'Open Timeline Edit' })
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(button)
}

test('opening pauses Studio media and blocks background autoplay until the editor closes', async () => {
  const ui = setup()
  const preview = window.document.createElement('section')
  preview.className = 'preview'
  const video = window.document.createElement('video')
  preview.append(video); ui.container.append(preview)
  const pause = vi.spyOn(video, 'pause').mockImplementation(() => {})
  await openEditor()
  await waitFor(() => expect(ui.open).toHaveBeenCalled())
  expect(pause).toHaveBeenCalledTimes(1)
  fireEvent.play(video)
  expect(pause).toHaveBeenCalledTimes(2)
  const editorVideo = window.document.createElement('video')
  const editorPause = vi.spyOn(editorVideo, 'pause').mockImplementation(() => {})
  ui.container.append(editorVideo)
  fireEvent.play(editorVideo)
  expect(editorPause).not.toHaveBeenCalled()
  act(() => ui.options().onClose())
  fireEvent.play(video)
  expect(pause).toHaveBeenCalledTimes(2)
})

test('opens the actual shared library contract and saves only a separate versioned document', async () => {
  const save = vi.spyOn(api, 'saveManualTimeline').mockResolvedValue({ etag: 'version1', enabled: true })
  const ui = setup()
  await openEditor()
  await waitFor(() => expect(ui.open).toHaveBeenCalled())
  expect(ui.open).toHaveBeenCalledWith(payload, document, expect.any(Object))
  expect(ui.options().theme).toBe('studio')
  expect(screen.getByRole('button', { name: 'Open Timeline Edit' }).classList.contains('primary')).toBe(true)
  expect(ui.options().urlFor('@music')).toContain('manual-timeline/media?file=%40music')
  const edit = { ...document, clips: [...document.clips, { ...document.clips[0], id: 'copy' }] }
  act(() => ui.options().onChange(edit))
  expect(JSON.parse(localStorage.getItem(key)!)).toEqual({ expected: null, document: edit })
  await act(async () => { await ui.options().onSave(edit) })
  expect(save).toHaveBeenCalledWith(job.id, edit, null, true)
  expect(localStorage.getItem(key)).toBeNull()
  act(() => ui.options().onChange(document))
  expect(JSON.parse(localStorage.getItem(key)!).expected).toBe('version1')
  expect(ui.state).not.toHaveBeenCalled()
})

test('export saves first, uses its new version, closes playback and watches the actual job', async () => {
  const save = vi.spyOn(api, 'saveManualTimeline').mockResolvedValue({ etag: 'version2', enabled: true })
  const queued = { ...job, status: 'running' as const }
  const run = vi.spyOn(api, 'renderManualTimeline').mockResolvedValue(queued)
  const ui = setup()
  await openEditor()
  await waitFor(() => expect(ui.open).toHaveBeenCalled())
  await act(async () => { await ui.options().onRender(document) })
  expect(save).toHaveBeenCalledBefore(run)
  expect(run).toHaveBeenCalledWith(job.id, 'version2')
  expect(ui.close).toHaveBeenCalled()
  expect(ui.state).toHaveBeenCalledWith(queued)
})

test('restores a matching draft across reopening without changing a source take', async () => {
  const edit = { ...document, clips: [{ ...document.clips[0], in_frame: 12 }] }
  localStorage.setItem(key, JSON.stringify({ expected: null, document: edit }))
  const ui = setup()
  await openEditor()
  await waitFor(() => expect(ui.open).toHaveBeenCalledWith(payload, edit, expect.any(Object)))
  ui.unmount()
  expect(ui.close).toHaveBeenCalled()
  expect(localStorage.getItem(key)).not.toBeNull()
})

test('conflicting drafts are never overwritten and require an explicit discard confirmation', async () => {
  const draft = JSON.stringify({ expected: 'different editor', document })
  localStorage.setItem(key, draft)
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
  const ui = setup()
  await openEditor()
  expect((await screen.findByRole('alert')).textContent).toContain('local draft conflicts')
  expect(ui.open).not.toHaveBeenCalled()
  expect(localStorage.getItem(key)).toBe(draft)
  fireEvent.click(screen.getByRole('button', { name: 'Discard local draft' }))
  expect(localStorage.getItem(key)).toBe(draft)
  await waitFor(() => expect((screen.getByRole('button', { name: 'Discard local draft' }) as HTMLButtonElement).disabled).toBe(false))
  confirm.mockReturnValue(true)
  fireEvent.click(screen.getByRole('button', { name: 'Discard local draft' }))
  await waitFor(() => expect(localStorage.getItem(key)).toBeNull())
})

test('failed save preserves the local draft and never starts export', async () => {
  vi.spyOn(api, 'saveManualTimeline').mockRejectedValue(new Error('Another editor changed this montage'))
  const run = vi.spyOn(api, 'renderManualTimeline')
  const ui = setup()
  await openEditor()
  await waitFor(() => expect(ui.open).toHaveBeenCalled())
  act(() => ui.options().onChange(document))
  await expect(ui.options().onRender(document)).rejects.toThrow('Another editor')
  expect(localStorage.getItem(key)).not.toBeNull()
  expect(run).not.toHaveBeenCalled()
})

test('stale montage cannot be opened, supports explicit safe rebase, and can be disabled without losing it', async () => {
  const rebase = vi.spyOn(api, 'rebaseManualTimeline').mockResolvedValue({ etag: 'new', document })
  const save = vi.spyOn(api, 'saveManualTimeline').mockResolvedValue({ etag: 'disabled', enabled: false })
  setup({ ...payload, stale: true, etag: 'saved', enabled: true })
  await waitFor(() => expect((screen.getByRole('button', { name: 'Rebase unchanged takes' }) as HTMLButtonElement).disabled).toBe(false))
  expect((screen.getByRole('button', { name: 'Open Timeline Edit' }) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Rebase unchanged takes' }))
  await waitFor(() => expect(rebase).toHaveBeenCalledWith(job.id, 'saved'))
  await waitFor(() => expect((screen.getByRole('button', { name: 'Use automatic montage' }) as HTMLButtonElement).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: 'Use automatic montage' }))
  await waitFor(() => expect(save).toHaveBeenCalledWith(job.id, document, 'saved', false))
})

test('running operations close the editor and prohibit every editing action', async () => {
  const ui = setup()
  await openEditor()
  await waitFor(() => expect(ui.open).toHaveBeenCalled())
  ui.rerender(<ManualTimeline job={{ ...job, status: 'running' }} onState={ui.state} />)
  expect(ui.close).toHaveBeenCalled()
  for (const button of screen.getAllByRole('button')) expect((button as HTMLButtonElement).disabled).toBe(true)
})

test('an editor still loading cannot reopen after an operation starts', async () => {
  const ui = setup()
  let resolve!: (value: TimelineEditorModule) => void
  vi.spyOn(api, 'loadTimelineEditor').mockReturnValue(new Promise(done => { resolve = done }))
  await openEditor()
  await waitFor(() => expect(api.loadTimelineEditor).toHaveBeenCalled())
  ui.rerender(<ManualTimeline job={{ ...job, status: 'running' }} onState={ui.state} />)
  await act(async () => { resolve({ openTimelineEditor: ui.open }) })
  expect(ui.open).not.toHaveBeenCalled()
})

test('manual exports cannot pretend to follow the generation-shot timeline or compare source timestamps', () => {
  const manual = { ...job, manual_export: { duration: 2, clips: 3, etag: 'exported' } }
  const timeline = vi.spyOn(api, 'timeline')
  const waveform = vi.spyOn(api, 'waveform')
  const input = { source: { id: 'source', name: 'source.mp4', kind: 'video' as const, url: '/source.mp4' },
    refs: [], refVideo: null, music: null, voice: null }
  const props = { mode: 'remix' as const, ratio: '16:9' as const, inputs: input, job,
    videoRef: createRef<HTMLVideoElement>(), onTime: vi.fn(), onShape: vi.fn(), startedAt: null }
  const { rerender } = render(<Preview {...props} />)
  expect(screen.getByRole('button', { name: /compare/i })).toBeTruthy()
  rerender(<Preview {...props} job={manual} />)
  expect(screen.queryByRole('button', { name: /compare/i })).toBeNull()
  expect(screen.getByText('Manual montage')).toBeTruthy()
  render(<Timeline job={manual} position={null} onSeek={vi.fn()} selection={[]} primary={0} edits={{}}
    onSelect={vi.fn()} onRegenerate={vi.fn()} onLock={vi.fn()} />)
  expect(screen.getByText(/Generation sources, not the exported manual montage/)).toBeTruthy()
  expect(timeline).not.toHaveBeenCalled()
  expect(waveform).not.toHaveBeenCalled()
})
