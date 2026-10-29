import type { AICandidate, AIOperation, EditStyle, Health, Inputs, JobInputs, Take, TimelineInfo, JobState, ManualTimelinePayload, Mode, Preset, Settings, TimelineDocument, TimelineEditorModule, Upload } from './types'

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ? (typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)) : `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export const health = (mode: Mode = 'remix', inputs: { refs?: number; ref_video?: boolean; voice?: boolean } = {}) => {
  const query = new URLSearchParams({ mode, refs: String(inputs.refs ?? 0), ref_video: String(inputs.ref_video ?? false), voice: String(inputs.voice ?? false) })
  return fetch(`/api/health?${query}`, { cache: 'no-store' }).then(json<Health>)
}

export function upload(file: File): Promise<Upload> {
  const form = new FormData()
  form.append('file', file)
  return fetch('/api/uploads', { method: 'POST', body: form }).then(json<Upload>)
}

export async function createJob(mode: Mode, settings: Settings, inputs: Inputs): Promise<JobState> {
  if ((mode !== 'remix' || settings.audio === 'new') && settings.music_edit_mode !== 'legacy') {
    const status = await health(mode, { refs: inputs.refs.filter(Boolean).length, ref_video: !!inputs.refVideo, voice: !!inputs.voice })
    const supported = mode === 'music' ? status.music_rhythm_modes : status.adaptive_editing_modes
    if (!supported && !status.mock) {
      throw new Error('Restart Studio after current jobs finish to enable the music rhythm modes. No generation has been submitted.')
    }
  }
  const body = { mode, settings: { ...settings, seed: settings.seed ?? Math.floor(Math.random() * 2 ** 31) }, source: inputs.source?.id ?? null, refs: inputs.refs.filter((r): r is Upload => r !== null).map(r => r.id), ref_video: inputs.refVideo?.id ?? null, music: inputs.music?.id ?? null, voice: inputs.voice?.id ?? null }
  return fetch('/api/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(json<JobState>)
}

export const jobInputs = (id: string) => fetch(`/api/jobs/${id}/inputs`).then(json<JobInputs>)

export const recentJobs = () => fetch('/api/jobs').then(json<JobState[]>)

export const presets = () => fetch('/api/presets').then(json<Preset[]>)

export const savePreset = (preset: Omit<Preset, 'id' | 'user'>) =>
  fetch('/api/presets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(preset) }).then(json<Preset>)

export const deletePreset = (id: string) => fetch(`/api/presets/${id}`, { method: 'DELETE' }).then(json<{ deleted: string }>)

export const sizes = () => fetch('/api/jobs/sizes').then(json<Record<string, number>>)

export const patchJob = (id: string, patch: { title?: string; pinned?: boolean }) =>
  fetch(`/api/jobs/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch) }).then(json<JobState>)

export const deleteJob = (id: string, withFiles: boolean) => fetch(`/api/jobs/${id}?project=${withFiles}`, { method: 'DELETE' }).then(json<{ deleted: string }>)

export const freeSpace = (id: string) => fetch(`/api/jobs/${id}/free`, { method: 'POST' }).then(json<{ freed: number }>)

export const regenerate = (id: string, shots: string[], prompts: Record<string, string>) =>
  fetch(`/api/jobs/${id}/regenerate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ shots, prompts }) }).then(json<JobState>)

export const reEdit = (id: string, style: EditStyle) =>
  fetch(`/api/jobs/${id}/re-edit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(style) }).then(json<JobState>)

export const timeline = (id: string) => fetch(`/api/jobs/${id}/timeline`).then(json<TimelineInfo>)

export const manualTimeline = (id: string) =>
  fetch(`/api/jobs/${id}/manual-timeline`).then(json<ManualTimelinePayload>)
export const saveManualTimeline = (id: string, document: TimelineDocument, expected: string | null, enabled: boolean) =>
  fetch(`/api/jobs/${id}/manual-timeline`, { method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document, expected, enabled }) }).then(json<{ etag: string; enabled: boolean }>)
export const rebaseManualTimeline = (id: string, expected: string | null) =>
  fetch(`/api/jobs/${id}/manual-timeline/rebase`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected }) }).then(json<{ etag: string; document: TimelineDocument }>)
export const renderManualTimeline = (id: string, expected: string) =>
  fetch(`/api/jobs/${id}/manual-timeline/render`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected }) }).then(json<JobState>)
export const timelineMediaURL = (id: string, file: string) =>
  `/api/jobs/${id}/manual-timeline/media?${new URLSearchParams({ file })}`
export async function loadTimelineEditor(): Promise<TimelineEditorModule> {
  const url = '/api/timeline-editor/timeline_edit_panel.js'
  const module: TimelineEditorModule = await import(/* @vite-ignore */ url)
  if (typeof module.openTimelineEditor !== 'function') throw new Error('Timeline editor module is unavailable')
  return module
}

export const waveform = (id: string) => fetch(`/api/jobs/${id}/waveform`).then(json<number[]>)

export const takes = (id: string, shot: string) => fetch(`/api/jobs/${id}/shots/${shot}/takes`).then(json<Take[]>)

export const aiCandidates = (id: string, shot: string) =>
  fetch(`/api/jobs/${id}/shots/${shot}/ai-candidates`).then(json<{ enabled: boolean; candidates: AICandidate[] }>)

export const startAICandidate = (id: string, shot: string, body: { operation: AIOperation; take: string; prompt: string; seconds: number; seed: number }) =>
  fetch(`/api/jobs/${id}/shots/${shot}/ai-candidates`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    .then(json<{ job: JobState; candidate: AICandidate }>)

export const decideAICandidate = (id: string, candidate: string, decision: 'accept' | 'reject') =>
  fetch(`/api/jobs/${id}/ai-candidates/${candidate}/${decision}`, { method: 'POST' }).then(json<JobState>)

export const chooseTake = (id: string, shot: string, take: string) =>
  fetch(`/api/jobs/${id}/shots/${shot}/active`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ take }) }).then(json<Take[]>)

export const trimTake = (id: string, shot: string, take: string, start: number) =>
  fetch(`/api/jobs/${id}/shots/${shot}/trim`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ take, start }) }).then(json<Take[]>)

export const lockShot = (id: string, shot: string, locked: boolean) =>
  fetch(`/api/jobs/${id}/shots/${shot}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ locked }) }).then(json<JobState>)

export const cancelJob = (id: string) => fetch(`/api/jobs/${id}/cancel`, { method: 'POST' }).then(json<JobState>)

/** Follow a job: the server sends its whole state every time it changes. Returns the function that stops following. */
export function follow(id: string, onState: (state: JobState) => void, onLost: () => void): () => void {
  let source: EventSource | null = null
  let stopped = false
  let attempts = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  const apply = (state: JobState) => {
    if (stopped) return
    onState(state)
    if (state.status !== 'queued' && state.status !== 'running') {
      stopped = true
      source?.close()
      clearTimeout(timer)
    }
  }
  const reconnect = () => {
    if (stopped) return
    if (source) { source.onerror = null; source.onmessage = null; source.close() }
    if (++attempts > 6) { stopped = true; onLost(); return }
    timer = setTimeout(async () => {
      if (stopped) return
      try {
        apply(await fetch(`/api/jobs/${id}`).then(json<JobState>))
        if (!stopped) connect()
      } catch { reconnect() }
    }, Math.min(500 * 2 ** (attempts - 1), 5000))
  }
  const connect = () => {
    if (stopped) return
    source = new EventSource(`/api/jobs/${id}/events`)
    source.onmessage = event => {
      try { apply(JSON.parse(event.data) as JobState); attempts = 0 }
      catch { reconnect() }
    }
    source.onerror = reconnect
  }
  connect()
  return () => { stopped = true; clearTimeout(timer); source?.close() }
}

export const artDirectionCatalog = () => fetch('/api/art-direction').then(json<{ fields: import('./types').DirectionField[] }>)
export const approveBrief = (mode: Mode, settings: Settings, inputs: Inputs, brief: string) => fetch('/api/brief-approve', {
  method:'POST', headers:{'Content-Type':'application/json'},
  body:JSON.stringify({mode,settings:{...settings,seed:settings.seed ?? 42,approved_brief:brief,approved_brief_context:''},source:inputs.source?.id ?? null,refs:inputs.refs.filter((v):v is Upload=>v!==null).map(v=>v.id),ref_video:inputs.refVideo?.id ?? null,music:inputs.music?.id ?? null,voice:inputs.voice?.id ?? null}),
}).then(json<{context:string}>)
export const prepareBrief = (mode: Mode, settings: Settings, inputs: Inputs, language = 'en') => fetch(`/api/brief-preview?lang=${language}`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ mode, settings: { ...settings, seed: settings.seed ?? 42, approved_brief: '', approved_brief_context: '' }, source: inputs.source?.id ?? null, refs: inputs.refs.filter((v): v is Upload => v !== null).map(v => v.id), ref_video: inputs.refVideo?.id ?? null, music: inputs.music?.id ?? null, voice: inputs.voice?.id ?? null }),
}).then(json<import('./types').PreparedBrief>)

export const restartStudio = () => fetch('/api/studio/restart', { method: 'POST' }).then(json<{ restarting: boolean; instance_id: string }>)
