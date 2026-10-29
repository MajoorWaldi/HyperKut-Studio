import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { EditStyle } from '../components/EditStyle'
import { Preview } from '../components/Preview'
import { ShotPanel } from '../components/ShotPanel'
import { Timeline } from '../components/Timeline'
import { dictionaries } from '../i18n'
import type { JobState, Shot } from '../types'

const shot = (id: string, over: Partial<Shot> = {}): Shot => ({ id, start: 0, duration: 2, prompt: `prompt ${id}`, version: 1, locked: false, thumb: null, done: true, takes: 1, ...over })
const job = (over: Partial<JobState> = {}): JobState => ({ id: 'j1', mode: 'text', status: 'succeeded', stage: 'done', progress: 1, node: null, step: null, steps: null, shots: [shot('SHOT_001'), shot('SHOT_002')], output_url: null, error: null, project_id: 'p', style: {}, preview: 0, title: '', created_at: 1, pinned: false, ...over })

const view = (extra: Partial<Parameters<typeof Timeline>[0]> = {}) => ({ job: job(), position: null, onSeek: vi.fn(), selection: [], primary: 0, edits: {}, onSelect: vi.fn(), onRegenerate: vi.fn(), onLock: vi.fn(), ...extra })
const panel = (extra: Partial<Parameters<typeof ShotPanel>[0]> = {}) => ({ job: job(), primary: 0, selection: [], edits: {}, quality: 'draft' as const, onEdit: vi.fn(), onStep: vi.fn(), onRegenerate: vi.fn(), onLock: vi.fn(), onChooseTake: vi.fn(), onTrimTake: vi.fn(), ...extra })

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url === '/api/jobs' ? [] : url === '/api/presets' ? [{ id: 'x', name: 'Neon', mode: 'text', description: '', prompt: 'a fox', settings: { duration: 20 } }] : { mock: true, comfyui: false, proxy: false, videotools: false, output_dir: null }))))
})
afterEach(cleanup)

const library = async () => { await userEvent.click(await screen.findByText(new RegExp(dictionaries.en.library))) }

test('importing a preset preserves both language variants', async () => {
  const { container } = render(<App />)
  await library()
  await userEvent.click(screen.getByText(new RegExp(`^${dictionaries.en.presets}`)))
  const translations = {fr: {name: 'Produit', description: 'Démo', prompt: 'Un flacon', settings: {mood: 'Calme'}}}
  const file = new File([JSON.stringify({name: 'Product', mode: 'text', prompt: 'A bottle', translations})], 'preset.json', {type: 'application/json'})
  fireEvent.change(container.querySelector('input[accept="application/json,.json"]')!, {target: {files: [file]}})
  await waitFor(() => {
    const calls = vi.mocked(fetch).mock.calls
    const sent = calls.find(([url, options]) => url === '/api/presets' && options?.method === 'POST')
    expect(sent).toBeTruthy()
    expect(JSON.parse(sent![1]!.body as string).translations).toEqual(translations)
  })
})

test('a preset of the library sets the mode, the settings and the prompt, and can be undone', async () => {
  render(<App />)
  await library()
  await userEvent.click(screen.getByText(new RegExp(`^${dictionaries.en.presets}`)))
  expect(screen.getByText('20 s')).toBeTruthy()  // what the preset sets, as a chip
  await userEvent.click(screen.getByText('Neon'))
  expect(await screen.findByDisplayValue('a fox')).toBeTruthy()
  expect(screen.getByText('Describe an idea: a soundtrack is made, then the edit is cut on its beats.')).toBeTruthy()
  await userEvent.click(screen.getByText(dictionaries.en.undo))
  expect(screen.getByText('Your video is the template of the edit: its cuts, rhythm, effects and camera stay; your subject replaces the one in it.')).toBeTruthy()
})

test('the projects are cards that can be searched, pinned, renamed and deleted', async () => {
  const jobs = [job({ id: 'a', title: 'Neon ad', output_url: '/api/jobs/a/video?v=1', created_at: 5 }), job({ id: 'b', title: 'Desert', mode: 'music', created_at: 9 })]
  const calls: [string, RequestInit | undefined][] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push([url, init])
    const body = url === '/api/jobs' ? jobs : url === '/api/jobs/sizes' ? { a: 52_000_000 } : url === '/api/presets' ? [] : url.startsWith('/api/jobs/') ? job() : { mock: true, comfyui: false, proxy: false, videotools: false, output_dir: null }
    return new Response(JSON.stringify(body))
  }))
  const { container } = render(<App />)
  await library()
  await userEvent.click(screen.getByText(new RegExp(`^${dictionaries.en.projects}`)))
  await waitFor(() => expect(container.ownerDocument.querySelectorAll('.lib-card').length).toBe(2))
  const titles = () => [...document.querySelectorAll('.lib-title')].map(e => e.textContent)
  expect(titles()).toEqual(['Desert', 'Neon ad'])  // the last one first
  expect(document.body.textContent).toContain('52 MB')
  await userEvent.type(screen.getByLabelText(dictionaries.en.search), 'neon')
  expect(titles()).toEqual(['Neon ad'])
  await userEvent.click(screen.getByTitle(dictionaries.en.pin))
  expect(calls.some(([url, init]) => url === '/api/jobs/a' && init?.method === 'PATCH' && String(init.body).includes('"pinned":true'))).toBe(true)
  await userEvent.click(screen.getByTitle(dictionaries.en.delete))
  await userEvent.click(screen.getByText(dictionaries.en.deleteFiles))
  expect(calls.some(([url, init]) => url === '/api/jobs/a?project=true' && init?.method === 'DELETE')).toBe(true)
})

test('the current settings can be saved as a preset', async () => {
  const calls: [string, RequestInit | undefined][] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => { calls.push([url, init]); return new Response(JSON.stringify(url === '/api/jobs' || url === '/api/presets' ? [] : { mock: true, comfyui: false, proxy: false, videotools: false, output_dir: null })) }))
  render(<App />)
  await library()
  await userEvent.click(screen.getByText(new RegExp(`^${dictionaries.en.presets}`)))
  await userEvent.type(screen.getByLabelText(dictionaries.en.presetName), 'My ad')
  await userEvent.click(screen.getByText(dictionaries.en.save))
  const saved = calls.find(([url, init]) => url === '/api/presets' && init?.method === 'POST')
  expect(JSON.parse(String(saved?.[1]?.body))).toMatchObject({ name: 'My ad', mode: 'remix', settings: { duration: 15, ratio: '9:16' } })
})

test('remix without a source video says what is missing and starts nothing', async () => {
  render(<App />)
  await userEvent.click(await screen.findByText(/Generate/))
  expect(await screen.findByText(dictionaries.en.needSource)).toBeTruthy()
  expect((fetch as ReturnType<typeof vi.fn>).mock.calls.some(([url, init]) => url === '/api/jobs' && init?.method === 'POST')).toBe(false)
})

test('Stop cancels only the current generation and stays disabled when idle', async () => {
  vi.stubGlobal('EventSource',class { close(){} })
  const active=job({status:'running',stage:'shots'})
  vi.stubGlobal('fetch',vi.fn(async (url:string,init?:RequestInit)=>new Response(JSON.stringify(
    url==='/api/jobs' && init?.method==='POST' ? active :
    url==='/api/jobs/j1/cancel' ? {...active,status:'cancelled'} :
    url==='/api/jobs' || url==='/api/presets' ? [] : {mock:true,comfyui:false,proxy:false,videotools:false,output_dir:null}
  ))))
  render(<App />)
  const stop=screen.getByRole('button',{name:'Cancel generation'}) as HTMLButtonElement
  expect(stop.disabled).toBe(true)
  await userEvent.click(screen.getByRole('button',{name:/TEXT/}))
  await userEvent.click(screen.getByRole('button',{name:/Generate/}))
  await waitFor(()=>expect(stop.disabled).toBe(false))
  await userEvent.click(stop)
  await waitFor(()=>expect(stop.disabled).toBe(true))
  expect(vi.mocked(fetch).mock.calls.filter(([url])=>url==='/api/jobs/j1/cancel')).toHaveLength(1)
})

test('the language can be switched to French', async () => {
  render(<App />)
  await userEvent.click(await screen.findByLabelText(/^Language/))
  await userEvent.click(screen.getByRole('option', { name: /Français/ }))
  expect(await screen.findByText(/Générer/)).toBeTruthy()
})

test('the edit style only sends what was touched, and waits until every shot is made', async () => {
  const onApply = vi.fn()
  const { rerender, container } = render(<EditStyle job={job({ shots: [shot('SHOT_001', { done: false })] })} onApply={onApply} />)
  expect(container.firstChild).toBeNull()
  rerender(<EditStyle job={job()} onApply={onApply} />)
  const button = screen.getByText(new RegExp(dictionaries.en.reEdit))
  expect((button as HTMLButtonElement).disabled).toBe(true)
  await userEvent.click(screen.getByLabelText(new RegExp(dictionaries.en.effects)))
  await userEvent.click(button)
  expect(onApply).toHaveBeenCalledWith({ effects: true })
})

test('the player offers to compare with the source, to download and to export, and shows the progress while it runs', async () => {
  const inputs = { source: { id: 's', name: 's.mp4', kind: 'video' as const, url: '/s.mp4' }, refs: [null, null, null, null, null], refVideo: null, music: null, voice: null }
  const props = { mode: 'remix' as const, ratio: '9:16' as const, inputs, videoRef: { current: null }, onTime: vi.fn(), onShape: vi.fn(), startedAt: Date.now() - 60000 }
  const { container, rerender } = render(<Preview {...props} job={job({ output_url: '/v.mp4' })} />)
  await userEvent.click(screen.getByLabelText(dictionaries.en.compare))
  expect(container.querySelectorAll('.player-art video').length).toBe(2)
  expect(container.querySelector('a[download]')?.getAttribute('href')).toBe('/v.mp4')
  expect(container.querySelector('a[href="/api/jobs/j1/export"]')).toBeTruthy()
  rerender(<Preview {...props} job={job({ status: 'running', stage: 'shots', progress: 0.5, output_url: null, shots: [shot('SHOT_001'), shot('SHOT_002', { done: false })] })} />)
  expect(screen.getByRole('status').textContent).toContain('2 of 2')
  expect(container.querySelectorAll('.progress-shots .active')).toHaveLength(1)
  expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('50')
  expect(screen.queryByText(/Generated footage budget/)).toBeNull()
  expect(screen.getByRole('status').textContent).toContain('50 %')
  expect(container.querySelector('.player-actions')).toBeNull()
})

test('the options are folded, grouped, set by the quick settings, and put back to their default', async () => {
  const { Options } = await import('../components/Options')
  const { DEFAULTS } = await import('../settings')
  const changes: Record<string, unknown>[] = []
  const props = { mode: 'text' as const, busy: false, onSettings: (change: Record<string, unknown>) => changes.push(change) }
  const { rerender } = render(<Options {...props} settings={DEFAULTS} />)
  expect(screen.queryByText(dictionaries.en.groupSound)).toBeNull()  // folded: a single line
  await userEvent.click(screen.getByText(new RegExp(dictionaries.en.options)))
  expect(screen.getByText(dictionaries.en.groupLook)).toBeTruthy()
  expect(screen.queryByText(dictionaries.en.places)).toBeNull()
  await userEvent.click(screen.getByText(dictionaries.en.groupLook))
  expect(screen.getByText(dictionaries.en.places)).toBeTruthy()  // the look of a creation
  expect(screen.queryByText(dictionaries.en.subjectMask)).toBeNull()  // computed on demand, no manual switch
  expect(screen.getByText(/Masks are computed automatically/)).toBeTruthy()
  await userEvent.click(screen.getByText(dictionaries.en.quickLight))
  expect(changes[0]).toMatchObject({ effects: false, sound_design: false, quality_check: false })
  await userEvent.click(screen.getByText(dictionaries.en.groupSound))
  expect(screen.getByText(dictionaries.en.soundDesign)).toBeTruthy()
  expect(screen.queryByText(dictionaries.en.places)).toBeNull()  // one group open at a time
  rerender(<Options {...props} settings={{ ...DEFAULTS, effects: true }} />)
  await userEvent.click(screen.getByText(dictionaries.en.resetOptions))
  expect(changes.at(-1)).toMatchObject({ effects: false, seed: null, motion_layers: '[]' })
})

test('the seed is random while it is empty, can be picked with the dice, and goes back to random', async () => {
  const { Options } = await import('../components/Options')
  const { DEFAULTS } = await import('../settings')
  const changes: Record<string, unknown>[] = []
  const props = { mode: 'text' as const, busy: false, onSettings: (change: Record<string, unknown>) => changes.push(change) }
  const { rerender } = render(<Options {...props} settings={DEFAULTS} />)
  await userEvent.click(screen.getByText(new RegExp(dictionaries.en.options)))
  await userEvent.click(screen.getByText(dictionaries.en.groupExpert))
  const field = screen.getByLabelText(dictionaries.en.seed) as HTMLInputElement
  expect(field.value).toBe('')
  expect(field.placeholder).toBe(dictionaries.en.seedRandom)
  expect(screen.queryByLabelText(dictionaries.en.seedClear)).toBeNull()
  await userEvent.click(screen.getByLabelText(dictionaries.en.seedPick))
  expect(typeof changes[0].seed).toBe('number')
  rerender(<Options {...props} settings={{ ...DEFAULTS, seed: 123 }} />)
  expect((screen.getByLabelText(dictionaries.en.seed) as HTMLInputElement).value).toBe('123')
  await userEvent.click(screen.getByLabelText(dictionaries.en.seedClear))
  expect(changes[1]).toEqual({ seed: null })
})

test('the panel makes the shot again with the edit or with the same prompt, and a locked shot cannot be made again', async () => {
  const props = panel({ edits: { SHOT_001: 'a red car' } })
  const { rerender } = render(<ShotPanel {...props} />)
  await userEvent.click(screen.getByText(new RegExp(dictionaries.en.regenerateEdit)))
  expect(props.onRegenerate).toHaveBeenLastCalledWith(['SHOT_001'], true)
  await userEvent.click(screen.getByText(dictionaries.en.newTake))
  expect(props.onRegenerate).toHaveBeenLastCalledWith(['SHOT_001'], false)
  await userEvent.click(screen.getByText(dictionaries.en.revert))
  expect(props.onEdit).toHaveBeenCalledWith('SHOT_001', 'prompt SHOT_001')
  await userEvent.type(screen.getByLabelText(dictionaries.en.shotPrompt), '!')
  expect(props.onEdit).toHaveBeenLastCalledWith('SHOT_001', 'a red car!')
  expect(screen.queryByRole('button', { name: dictionaries.en.lock })).toBeNull()
  rerender(<ShotPanel {...panel({ job: job({ shots: [shot('SHOT_001', { locked: true })] }) })} />)
  expect((screen.getByText(new RegExp(`^${dictionaries.en.regenerate}$`)) as HTMLButtonElement).disabled).toBe(true)
})

test('Remix shows the recorded prompt of the previewed take separately from the editable correction', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([
    { id: 'take_001', active: true, url: '/one.mp4', generation_prompt: 'Actual first prompt' },
    { id: 'take_002', active: false, url: '/two.mp4', generation_prompt: 'Actual retry prompt' },
  ]))))
  const props = panel({ job: job({ mode: 'remix', shots: [shot('SHOT_001', {
    prompt: 'Keep my glasses', generation_prompt: 'Actual first prompt', takes: 2,
  })] }) })
  const { container } = render(<ShotPanel {...props} />)
  await waitFor(() => expect(container.querySelectorAll('button.take').length).toBe(2))
  const recorded = screen.getByLabelText(dictionaries.en.generationPrompt) as HTMLTextAreaElement
  expect(recorded.value).toBe('Actual first prompt')
  expect(recorded.readOnly).toBe(true)
  expect((screen.getByLabelText(dictionaries.en.shotCorrection) as HTMLTextAreaElement).value).toBe('Keep my glasses')
  await userEvent.click(container.querySelectorAll('button.take')[1])
  expect(recorded.value).toBe('Actual retry prompt')
  await userEvent.type(screen.getByLabelText(dictionaries.en.shotCorrection), '!')
  expect(props.onEdit).toHaveBeenLastCalledWith('SHOT_001', 'Keep my glasses!')
})

test('Remix does not invent a generation prompt for legacy takes', async () => {
  render(<ShotPanel {...panel({ job: job({ mode: 'remix' }) })} />)
  const recorded = screen.getByLabelText(dictionaries.en.generationPrompt) as HTMLTextAreaElement
  expect(recorded.value).toBe('')
  expect(recorded.placeholder).toBe(dictionaries.en.missingGenerationPrompt)
})

test('the panel waits until the job is over, tells what it is for, and the arrow keys change the shot', async () => {
  const props = panel({ job: job({ status: 'running', stage: 'shots' }) })
  render(<ShotPanel {...props} />)
  expect((screen.getByText(new RegExp(`^${dictionaries.en.regenerate}$`)) as HTMLButtonElement).disabled).toBe(true)
  await userEvent.keyboard('{ArrowRight}')
  expect(props.onStep).toHaveBeenCalledWith(1)
  await userEvent.type(screen.getByLabelText(dictionaries.en.shotPrompt), '{ArrowLeft}')  // typing in the prompt does not change the shot
  expect(props.onStep).toHaveBeenCalledTimes(1)
  cleanup()
  render(<ShotPanel {...panel({ job: null })} />)
  expect(screen.getByText(dictionaries.en.emptyShot)).toBeTruthy()
})

test('the versions of a shot are shown, watched, and one can be chosen', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([{ id: 'take_001', active: true, url: '/t1.mp4' }, { id: 'take_002', active: false, url: '/t2.mp4' }]))))
  const props = panel()
  const { container } = render(<ShotPanel {...props} />)
  const chips = await waitFor(() => { const found = container.querySelectorAll('.take'); expect(found.length).toBe(2); return found })
  expect(container.querySelector('.shot-view video')?.getAttribute('src')).toBe('/t1.mp4')
  await userEvent.click(chips[1])
  expect(container.querySelector('.shot-view video')?.getAttribute('src')).toBe('/t2.mp4')
  await userEvent.click(screen.getByText(dictionaries.en.useTake))
  expect(props.onChooseTake).toHaveBeenCalledWith('SHOT_001', 'take_002')
})

test('the shot that is playing is lit, and a click on a shot selects it and seeks to its start', async () => {
  const onSeek = vi.fn()
  const onSelect = vi.fn()
  const shots = [shot('SHOT_001', { duration: 2 }), shot('SHOT_002', { duration: 4 })]
  const { container } = render(<Timeline {...view({ job: job({ output_url: '/v.mp4', shots }), position: 3, onSeek, onSelect })} />)
  const buttons = container.querySelectorAll('.shot')
  expect(buttons[0].classList.contains('playing')).toBe(false)
  expect(buttons[1].classList.contains('playing')).toBe(true)
  expect((buttons[1].querySelector('.shot-progress') as HTMLElement).style.transform).toBe('scaleX(0.25)')
  await userEvent.click(buttons[1])
  expect(onSeek).toHaveBeenCalledWith(2)
  expect(onSelect).toHaveBeenCalledWith(['SHOT_002'], 1)
})

test('shift-click selects a range, and the buttons of the timeline act on the selected shots that are not locked', async () => {
  const shots = [shot('SHOT_001'), shot('SHOT_002', { locked: true }), shot('SHOT_003'), shot('SHOT_004')]
  const props = view({ job: job({ shots }), selection: ['SHOT_001', 'SHOT_002', 'SHOT_003'] })
  const { container } = render(<Timeline {...props} />)
  expect(container.querySelectorAll('.shot.selected').length).toBe(3)
  fireEvent.click(container.querySelectorAll('.shot')[2], { shiftKey: true })
  expect(props.onSelect).toHaveBeenCalledWith(['SHOT_001', 'SHOT_002', 'SHOT_003'], 2)
  fireEvent.click(container.querySelectorAll('.shot')[3], { ctrlKey: true })
  expect(props.onSelect).toHaveBeenLastCalledWith(['SHOT_001', 'SHOT_002', 'SHOT_003', 'SHOT_004'], 3)
  await userEvent.click(screen.getByText(`${dictionaries.en.regenerate} (2)`))
  expect(props.onRegenerate).toHaveBeenCalledWith(['SHOT_001', 'SHOT_003'])  // the locked one is left out
  await userEvent.click(screen.getByText(dictionaries.en.regenerateAll))
  expect(props.onRegenerate).toHaveBeenLastCalledWith(['SHOT_001', 'SHOT_003', 'SHOT_004'])
  await userEvent.click(screen.getByText(dictionaries.en.lock))
  expect(props.onLock).toHaveBeenCalledWith(['SHOT_001', 'SHOT_002', 'SHOT_003'], true)
})

test('a shot shows what it carries: locked, edited, several takes, its effects', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/timeline') ? { bpm: 120, beat_times: [0,0.5,1,1.5,2,2.5,3,3.5,4], shots: [{ id: 'SHOT_001', cuts: [0.5], effects: ['zoom', 'transition:glitch', 'text'] }] } : url.endsWith('/waveform') ? [0.2, 1, 0.5] : []))))
  const props = view({ job: job({ output_url: '/v.mp4', shots: [shot('SHOT_001', { takes: 3, locked: true }), shot('SHOT_002')] }), position: 0.5, edits: { SHOT_002: 'changed' } })
  const { container } = render(<Timeline {...props} />)
  await waitFor(() => expect(container.querySelector('.shot .badges i')).toBeTruthy())
  const marks = (shot: Element) => [...shot.querySelectorAll('[data-badge]')].map(badge => badge.getAttribute('data-badge'))
  expect(marks(container.querySelector('.shot')!)).toEqual(expect.arrayContaining(['lock', 'takes', 'zoom', 'sparkles', 'type']))
  expect(container.querySelector('.shot [data-badge="takes"]')!.textContent).toBe('×3')
  expect(marks(container.querySelectorAll('.shot')[1])).toContain('edited')  // its prompt was edited
  await waitFor(() => expect(container.querySelector('.wave path')).toBeTruthy())
  expect(container.querySelectorAll('.rhythm .cut').length).toBe(2)  // the cut inside the first shot, and the start of the second
  expect(container.querySelector('.playhead')).toBeTruthy()
  expect(container.querySelector('.tl-heading small')!.textContent).not.toContain('ms')
  expect(screen.queryByRole('button', { name: /review result/i })).toBeNull()
  expect(screen.queryByText(/energy: reference and result/i)).toBeNull()
})

test('a press outside the library closes it, a press inside or on its button does not close it by itself', async () => {
  render(<App />)
  await library()
  await userEvent.click(screen.getByText(new RegExp(`^${dictionaries.en.presets}`)))
  await userEvent.click(screen.getByLabelText(dictionaries.en.presetName))  // inside
  expect(document.querySelector('.library-block')).toBeTruthy()
  await userEvent.click(document.querySelector('.workarea') as HTMLElement)  // outside
  expect(document.querySelector('.library-block')).toBeNull()
  await library()
  expect(document.querySelector('.library-block')).toBeTruthy()  // the button opens it again
  await userEvent.click(screen.getByText(new RegExp(dictionaries.en.library)))
  expect(document.querySelector('.library-block')).toBeNull()  // and closes it, once
})

test('a tooltip shows after a short wait, not on what is already chosen, and not again after a press', async () => {
  const { Tooltips } = await import('../components/Tooltips')
  vi.useFakeTimers()
  try {
    render(<div><Tooltips /><button title="Make it">plain</button><button title="Already on" className="selected">chosen</button><button title="Pressed" aria-pressed="true">pressed</button></div>)
    const hover = (name: string) => fireEvent.mouseOver(screen.getByText(name))
    hover('plain')
    expect(screen.getByText('plain').getAttribute('title')).toBeNull()  // the native tip is off
    await act(async () => { await vi.advanceTimersByTimeAsync(600) })
    expect(screen.getByRole('tooltip').textContent).toBe('Make it')
    fireEvent.mouseDown(screen.getByText('plain'))
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.mouseOver(screen.getByText('plain'))
    await act(async () => { await vi.advanceTimersByTimeAsync(600) })
    expect(screen.queryByRole('tooltip')).toBeNull()  // quiet after a press
    fireEvent.mouseOut(screen.getByText('plain'), { relatedTarget: document.body })
    expect(screen.getByText('plain').getAttribute('title')).toBe('Make it')  // given back
    for (const name of ['chosen', 'pressed']) {
      hover(name)
      await act(async () => { await vi.advanceTimersByTimeAsync(600) })
      expect(screen.queryByRole('tooltip')).toBeNull()
      fireEvent.mouseOut(screen.getByText(name), { relatedTarget: document.body })
    }
  } finally { vi.useRealTimers() }
})

test('the first screen offers the six example presets in their order, a click applies one, and a job takes the screen over', async () => {
  const modes = ['remix', 'remix', 'text', 'text', 'music', 'music']
  const featured = [4, 1, 6, 3, 2, 5].map(order => ({ id: `p${order}`, name: `Preset ${order}`, mode: modes[order - 1], description: `about ${order}`, prompt: `prompt ${order}`, settings: { duration: 10 + order }, featured: order }))
  const others = [{ id: 'z', name: 'Not featured', mode: 'text', description: '', prompt: '' }, { id: 'p7', name: 'Seventh', mode: 'text', description: '', prompt: '', featured: 7 }]
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url === '/api/jobs' ? [] : url === '/api/presets' ? [...featured, ...others] : { mock: true, comfyui: false, proxy: false, videotools: false, output_dir: null }))))
  render(<App />)
  const cards = await waitFor(() => { const found = document.querySelectorAll('.example-card'); expect(found.length).toBe(6); return found })
  expect([...cards].map(card => card.querySelector('b')!.textContent)).toEqual([1, 2, 3, 4, 5, 6].map(n => `Preset ${n}`))
  expect(screen.getByText(dictionaries.en.startHint)).toBeTruthy()
  await userEvent.click(cards[3])  // a creation preset
  expect(await screen.findByDisplayValue('prompt 4')).toBeTruthy()
  expect(document.querySelectorAll('.example-card')[3].getAttribute('aria-pressed')).toBe('true')
  expect(screen.getByText(dictionaries.en.startNextText)).toBeTruthy()
})


test('applying a preset restores source and sparse references and undo restores prior inputs', async () => {
  const source = { id: 'src', name: 'source.mp4', kind: 'video', url: '/api/uploads/src' }
  const reference = { id: 'ref', name: 'reference.png', kind: 'image', url: '/api/uploads/ref' }
  const full = { id: 'full', name: 'Full example', mode: 'remix', description: '', prompt: 'A paper world', settings: { seed: 731 }, inputs: { source, refs: [null, null, reference, null, null], refVideo: null, music: null, voice: null } }
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url === '/api/jobs' ? [] : url === '/api/presets' ? [full] : { mock: true, preset_inputs: true, comfyui: false, proxy: false, videotools: false, output_dir: null }))))
  const { container } = render(<App />)
  await library()
  await userEvent.click(screen.getByText(new RegExp(`^${dictionaries.en.presets}`)))
  await userEvent.click(screen.getByText('Full example'))
  expect(await screen.findByDisplayValue('A paper world')).toBeTruthy()
  expect(container.querySelector('video[src="/api/uploads/src"]')).toBeTruthy()
  expect(container.querySelector('img[src="/api/uploads/ref"]')).toBeTruthy()
  await userEvent.click(screen.getByText(dictionaries.en.undo))
  expect(container.querySelector('video[src="/api/uploads/src"]')).toBeNull()
  expect(container.querySelector('img[src="/api/uploads/ref"]')).toBeNull()
})


test('Restart reports a busy-server refusal in the visible error banner', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => url === '/api/studio/restart'
    ? new Response(JSON.stringify({ detail: 'Another generation is running' }), { status: 409 })
    : new Response(JSON.stringify(url === '/api/jobs' || url === '/api/presets' ? [] : { mock: true, comfyui: false, proxy: false, videotools: false, output_dir: null }))))
  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: 'Restart Studio' }))
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Another generation is running'))
  expect(screen.getByRole('button', { name: 'Restart Studio' }).hasAttribute('disabled')).toBe(false)
})
