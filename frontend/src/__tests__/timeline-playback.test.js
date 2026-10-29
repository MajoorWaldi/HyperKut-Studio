import { afterEach, expect, test, vi } from 'vitest'
import { fireEvent } from '@testing-library/react'
import { openTimelineEditor } from '../../../../web/timeline_edit_panel.js'

let close
afterEach(async () => {
  close?.(); close = null
  await vi.advanceTimersByTimeAsync(0)
  vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals()
  document.body.replaceChildren()
  delete HTMLDialogElement.prototype.showModal; delete HTMLDialogElement.prototype.close
})

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const flush = () => vi.advanceTimersByTimeAsync(0)
function mockPlay(media) {
  const play = vi.fn(() => HTMLMediaElement.prototype.play.call(media))
  Object.defineProperty(media, 'play', { configurable: true, value: play })
  return play
}

async function setup(music = true, dialogue = null, sourceAudio = false) {
  vi.useFakeTimers()
  const times = new WeakMap(), paused = new WeakMap(), callbacks = new Map()
  let next = 0
  vi.stubGlobal('requestAnimationFrame', callback => { callbacks.set(++next, callback); return next })
  vi.stubGlobal('cancelAnimationFrame', id => callbacks.delete(id))
  vi.spyOn(HTMLMediaElement.prototype, 'readyState', 'get').mockReturnValue(4)
  vi.spyOn(HTMLMediaElement.prototype, 'seeking', 'get').mockReturnValue(false)
  vi.spyOn(HTMLMediaElement.prototype, 'ended', 'get').mockReturnValue(false)
  vi.spyOn(HTMLMediaElement.prototype, 'paused', 'get').mockImplementation(function () { return paused.get(this) ?? true })
  vi.spyOn(HTMLMediaElement.prototype, 'currentTime', 'get').mockImplementation(function () { return times.get(this) || 0 })
  vi.spyOn(HTMLMediaElement.prototype, 'currentTime', 'set').mockImplementation(function (value) {
    times.set(this, value)
    if (!this.holdSeek) queueMicrotask(() => this.dispatchEvent(new Event('seeked')))
  })
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(function () {
    if (this.isConnected && this.getAttribute('src'))
      queueMicrotask(() => this.dispatchEvent(new Event('loadedmetadata')))
  })
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(function () { paused.set(this, true) })
  const start = vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(function () {
    paused.set(this, false); return Promise.resolve()
  })
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ clearRect() {}, fillRect() {}, fillText() {} })
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
  const doc = { version: 1, project_id: 'p', source_signature: 's', fps_num: 24, fps_den: 1,
    clips: [{ id: 'a', shot_id: 's1', revision_id: 't1', in_frame: 0, out_frame: 24 },
      { id: 'b', shot_id: 's1', revision_id: 't1', in_frame: 24, out_frame: 48 }] }
  const payload = { initial: doc, library: [{ id: 's1', takes: [{ id: 't1', file: 'take.mp4', frames: 96, offset: 0 }] }],
    music: music ? { file: 'music.wav', duration: 4, peaks: [1], source_audio: sourceAudio } : null }
  payload.library[0].takes[0].audio = { file: 'voice.wav', duration: 4, peaks: [1, .5] }
  if (dialogue) doc.dialogue = [{ ...doc.clips[0], id: 'voice', out_frame: 48, at_frame: 0, gain: .5, ...dialogue }]
  const change = vi.fn()
  close = openTimelineEditor(payload, doc, { urlFor: f => f, onChange: change, onClose: vi.fn() })
  await flush()
  const dialog = document.querySelector('.mjr-edit')
  const video = dialog.querySelector('video'), audio = dialog.querySelector('audio')
  const play = dialog.querySelector('.mjr-edit-play'), status = dialog.querySelector('.mjr-edit-error')
  return { dialog, video, audio, play, status, start, change, times,
    tick: async () => { const tasks = [...callbacks.values()]; callbacks.clear(); tasks.forEach(task => task()); await flush() } }
}

test.each(['resolve', 'reject'])('obsolete play %s cannot stop a newer playback', async outcome => {
  const ui = await setup()
  const old = deferred()
  mockPlay(ui.video).mockImplementationOnce(() => old.promise)
  fireEvent.click(ui.play); await flush()
  expect(ui.play.textContent).toBe('Pause')
  expect(ui.audio.paused).toBe(true)
  fireEvent.click(ui.play)
  fireEvent.click(ui.play); await flush()
  expect(ui.audio.paused).toBe(false)
  old[outcome](outcome === 'reject' ? new Error('Old play failed') : undefined)
  await flush()
  expect(ui.video.paused).toBe(false)
  expect(ui.audio.paused).toBe(false)
  expect(ui.play.textContent).toBe('Pause')
  expect(ui.status.textContent).toBe('')
})

test('a blocked video start never starts music and times out with a retryable error', async () => {
  const ui = await setup(), old = deferred()
  mockPlay(ui.video).mockImplementationOnce(() => old.promise)
  fireEvent.click(ui.play); await flush()
  expect(ui.play.getAttribute('aria-busy')).toBe('true')
  expect(ui.audio.paused).toBe(true)
  await vi.advanceTimersByTimeAsync(15001)
  expect(ui.video.paused).toBe(true)
  expect(ui.audio.paused).toBe(true)
  expect(ui.status.textContent).toContain('playback timed out')
  expect(ui.play.getAttribute('aria-busy')).toBe('false')
  fireEvent.click(ui.play); await flush()
  old.resolve(); await flush()
  expect(ui.play.textContent).toBe('Pause')
  expect(ui.audio.paused).toBe(false)
})

test('audio failure stops both media and a late video completion cannot restart it', async () => {
  const ui = await setup()
  mockPlay(ui.audio).mockRejectedValueOnce(new Error('Audio playback denied'))
  fireEvent.click(ui.play); await flush()
  expect(ui.video.paused).toBe(true)
  expect(ui.audio.paused).toBe(true)
  expect(ui.status.textContent).toContain('Audio playback denied')
  expect(ui.play.textContent).toBe('Play')
})

test('dialogue remains on its own source clock across a picture cut and seeks with transport', async () => {
  const ui = await setup(false, {})
  const voice = ui.dialog.querySelector('audio[data-dialogue]')
  expect(voice.getAttribute('src')).toBe('voice.wav')
  fireEvent.click(ui.play); await flush()
  expect(voice.volume).toBe(.5)
  expect(voice.paused).toBe(false)
  ui.times.set(ui.video, 1.1); ui.times.set(voice, 1.1)
  await ui.tick()
  expect(voice.currentTime).toBeCloseTo(26 / 24)
  expect(voice.paused).toBe(false)
  expect(ui.video.muted).toBe(true)
  fireEvent.input(ui.dialog.querySelector('[aria-label="Playback position"]'), { target: { value: '12' } })
  await flush()
  expect(voice.currentTime).toBe(.5)
  expect(voice.paused).toBe(true)
  expect(ui.status.textContent).toBe('')
})

test('dialogue starts at its own position and stops at its out point while music continues', async () => {
  const ui = await setup(true, { at_frame: 12, out_frame: 24 })
  expect(ui.dialog.querySelector('audio[data-dialogue]')).toBeNull()
  fireEvent.click(ui.play); await flush()
  ui.times.set(ui.video, .75); ui.times.set(ui.audio, .75)
  await ui.tick()
  const voice = ui.dialog.querySelector('audio[data-dialogue]')
  expect(voice.currentTime).toBe(.25)
  expect(voice.paused).toBe(false)
  ui.times.set(ui.video, 1.75); ui.times.set(ui.audio, 1.75); ui.times.set(voice, 1.25)
  await ui.tick()
  expect(voice.paused).toBe(true)
  expect(ui.audio.paused).toBe(false)
})

test('dialogue editing, mute, removal and music levels are persistent and undoable', async () => {
  const ui = await setup()
  fireEvent.click(ui.dialog.querySelector('.mjr-dialogue-add')); await flush()
  expect(ui.change.mock.lastCall[0].dialogue[0]).toMatchObject({ in_frame: 0, out_frame: 96, at_frame: 0 })
  expect(ui.dialog.querySelector('.mjr-dialogue-warning').textContent).toContain('exceeds')
  fireEvent.change(ui.dialog.querySelector('[aria-label="Dialogue out frame"]'), { target: { value: '36' } })
  fireEvent.change(ui.dialog.querySelector('[aria-label="Dialogue position frame"]'), { target: { value: '6' } })
  fireEvent.change(ui.dialog.querySelector('[aria-label="Dialogue volume"]'), { target: { value: '0' } })
  fireEvent.click([...ui.dialog.querySelectorAll('button')].find(b => b.textContent === 'Apply dialogue')); await flush()
  expect(ui.change.mock.lastCall[0].dialogue[0]).toMatchObject({ out_frame: 36, at_frame: 6, gain: 0 })
  fireEvent.change(ui.dialog.querySelector('[aria-label="Music volume"]'), { target: { value: '.3' } }); await flush()
  expect(ui.audio.volume).toBe(.3)
  fireEvent.click([...ui.dialog.querySelectorAll('button')].find(b => b.textContent === 'Delete dialogue')); await flush()
  expect(ui.change.mock.lastCall[0].dialogue).toEqual([])
  fireEvent.click([...ui.dialog.querySelectorAll('button')].find(b => b.textContent === 'Undo')); await flush()
  expect(ui.change.mock.lastCall[0].dialogue[0].gain).toBe(0)
})

test('dialogue load failure stops music and video and close releases the source', async () => {
  const ui = await setup(true, {})
  const voice = ui.dialog.querySelector('audio[data-dialogue]')
  mockPlay(voice).mockRejectedValueOnce(new Error('Dialogue playback denied'))
  fireEvent.click(ui.play); await flush()
  expect(ui.video.paused).toBe(true)
  expect(ui.audio.paused).toBe(true)
  expect(voice.paused).toBe(true)
  expect(ui.status.textContent).toContain('Dialogue playback denied')
  close()
  expect(voice.hasAttribute('src')).toBe(false)
})

test('a Remix source soundtrack is not mixed twice when explicit dialogue replaces it', async () => {
  const ui = await setup(true, {}, true)
  fireEvent.click(ui.play); await flush()
  expect(ui.video.paused).toBe(false)
  expect(ui.dialog.querySelector('audio[data-dialogue]').paused).toBe(false)
  expect(ui.audio.paused).toBe(true)
  expect(ui.dialog.querySelector('[aria-label="Music volume"]').disabled).toBe(true)
})

test('music seek must finish before either player starts', async () => {
  const ui = await setup()
  ui.audio.holdSeek = true
  Object.defineProperty(ui.audio, 'seeking', { configurable: true, get: () => ui.audio.holdSeek })
  const scrub = ui.dialog.querySelector('[aria-label="Playback position"]')
  fireEvent.input(scrub, { target: { value: '12' } }); await flush()
  fireEvent.click(ui.play); await flush()
  expect(ui.start).not.toHaveBeenCalled()
  ui.audio.holdSeek = false
  ui.audio.dispatchEvent(new Event('seeked')); await flush()
  expect(ui.start).toHaveBeenCalledTimes(2)
  expect(ui.audio.currentTime).toBe(.5)
  expect(ui.play.textContent).toBe('Pause')
})

test('cancelled trim during loading needs only one Play click to start', async () => {
  const ui = await setup()
  Object.defineProperty(ui.video, 'readyState', { configurable: true, value: 0 })
  fireEvent.input(ui.dialog.querySelector('[aria-label="Playback position"]'), { target: { value: '3' } })
  const handle = ui.dialog.querySelector('.mjr-edit-handle')
  handle.setPointerCapture = vi.fn()
  const down = new Event('pointerdown', { bubbles: true })
  Object.defineProperties(down, { button: { value: 0 }, pointerId: { value: 1 }, clientX: { value: 0 } })
  handle.dispatchEvent(down); handle.dispatchEvent(new Event('pointercancel'))
  Object.defineProperty(ui.video, 'readyState', { configurable: true, value: 4 })
  fireEvent.click(ui.play); await flush()
  expect(ui.play.textContent).toBe('Pause')
  expect(ui.audio.paused).toBe(false)
})

test('buffering pauses both players until the video can play again', async () => {
  const ui = await setup()
  fireEvent.click(ui.play); await flush()
  Object.defineProperty(ui.video, 'readyState', { configurable: true, value: 2 })
  ui.video.dispatchEvent(new Event('waiting')); await flush()
  expect(ui.video.paused).toBe(true)
  expect(ui.audio.paused).toBe(true)
  Object.defineProperty(ui.video, 'readyState', { configurable: true, value: 4 })
  ui.video.dispatchEvent(new Event('canplay')); await flush()
  expect(ui.play.textContent).toBe('Pause')
  expect(ui.audio.paused).toBe(false)
})

test('loop rewinds video and music together; disabling it stops at the edit end', async () => {
  const ui = await setup()
  fireEvent.click(ui.dialog.querySelector('.mjr-edit-loop'))
  fireEvent.click(ui.play); await flush()
  ui.times.set(ui.audio, 2.01); ui.times.set(ui.video, 2.01)
  await ui.tick()
  expect(ui.video.currentTime).toBe(0)
  expect(ui.audio.currentTime).toBe(0)
  expect(ui.play.textContent).toBe('Pause')
  fireEvent.click(ui.dialog.querySelector('.mjr-edit-loop'))
  ui.times.set(ui.audio, 2.01); ui.times.set(ui.video, 2.01)
  await ui.tick()
  expect(ui.play.textContent).toBe('Play')
  expect(ui.audio.paused).toBe(true)
  expect(ui.dialog.querySelector('[aria-label="Playback position"]').value).toBe('47')
  expect(ui.change).not.toHaveBeenCalled()
})

test('closing during a pending start cancels it without late media activity', async () => {
  const ui = await setup(), old = deferred()
  mockPlay(ui.video).mockReturnValue(old.promise)
  fireEvent.click(ui.play); await flush()
  close(); close = null
  old.resolve(); await flush()
  expect(ui.audio.paused).toBe(true)
  expect(ui.video.paused).toBe(true)
  expect(document.querySelector('.mjr-edit')).toBeNull()
})

test('a media decoding error cancels startup and cannot be overwritten by its late completion', async () => {
  const ui = await setup(), old = deferred()
  mockPlay(ui.video).mockReturnValueOnce(old.promise)
  fireEvent.click(ui.play); await flush()
  ui.video.dispatchEvent(new Event('error'))
  old.resolve(); await flush()
  expect(ui.play.textContent).toBe('Play')
  expect(ui.video.paused).toBe(true)
  expect(ui.audio.paused).toBe(true)
  expect(ui.status.textContent).toContain('cannot be decoded')
})

test('without music, the video clock advances across clips and ended loops back to zero', async () => {
  const ui = await setup(false)
  fireEvent.click(ui.play); await flush()
  ui.times.set(ui.video, 1.1); await ui.tick()
  expect(ui.dialog.querySelector('[aria-label="Playback position"]').value).toBe('26')
  expect(ui.audio.paused).toBe(true)
  fireEvent.click(ui.dialog.querySelector('.mjr-edit-loop'))
  ui.times.set(ui.video, 2)
  ui.video.dispatchEvent(new Event('ended')); await flush()
  expect(ui.video.currentTime).toBe(0)
  expect(ui.play.textContent).toBe('Pause')
  expect(ui.video.paused).toBe(false)
})
