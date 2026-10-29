import { afterEach, expect, test, vi } from 'vitest'
import { fireEvent } from '@testing-library/react'
import { openTimelineEditor } from '../../../../web/timeline_edit_panel.js'

let close
afterEach(async () => {
  close?.(); close = null
  await Promise.resolve()
  vi.restoreAllMocks(); document.body.replaceChildren()
  delete HTMLDialogElement.prototype.showModal; delete HTMLDialogElement.prototype.close
})

function setup() {
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ clearRect() {}, fillRect() {}, fillText() {} })
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
  const doc = { version: 1, project_id: 'p', source_signature: 's', fps_num: 24, fps_den: 1,
    clips: [{ id: 'a', shot_id: 's1', revision_id: 'take1', in_frame: 12, out_frame: 60 },
      { id: 'b', shot_id: 's1', revision_id: 'take1', in_frame: 0, out_frame: 24 }] }
  const payload = { initial: doc, library: [{ id: 's1', takes: [
    { id: 'take1', file: 'take.mp4', frames: 96, offset: 0 },
    { id: 'take2', file: 'take2.mp4', frames: 144, offset: 2 },
  ] }], music: null }
  const change = vi.fn()
  close = openTimelineEditor(payload, doc, { urlFor: f => f, onChange: change, onClose: vi.fn(), theme: 'studio' })
  const track = document.querySelector('.mjr-source-track')
  track.getBoundingClientRect = () => ({ width: 960 })
  track.setPointerCapture = vi.fn()
  track.hasPointerCapture = () => true
  track.releasePointerCapture = vi.fn()
  return { change, track }
}

function pointer(target, type, x) {
  const event = new Event(type, { bubbles: true })
  Object.defineProperties(event, { button: { value: 0 }, pointerId: { value: 1 }, clientX: { value: x } })
  target.dispatchEvent(event)
}

test('loop defaults off and toggles without changing the saved montage', () => {
  const { change } = setup()
  const loop = document.querySelector('[aria-label="Loop playback"]')
  expect(loop.getAttribute('aria-pressed')).toBe('false')
  fireEvent.click(loop)
  expect(loop.getAttribute('aria-pressed')).toBe('true')
  fireEvent.click(loop)
  expect(loop.getAttribute('aria-pressed')).toBe('false')
  expect(change).not.toHaveBeenCalled()
})

test('close is a single accessible cross in the editor header, not the transport', () => {
  setup()
  const buttons = document.querySelectorAll('.mjr-edit-close')
  expect(buttons).toHaveLength(1)
  expect(buttons[0].getAttribute('aria-label')).toBe('Close')
  expect(buttons[0].textContent).toBe('\u00d7')
  expect(buttons[0].parentElement.className).toBe('mjr-edit-header')
  expect(document.querySelector('.mjr-edit-transport .mjr-edit-close')).toBeNull()
})

function navigationTrack() {
  const track = document.querySelector('.mjr-edit-track')
  track.getBoundingClientRect = () => ({ left: 100, width: 360 })
  Object.defineProperty(track, 'offsetWidth', { configurable: true, value: 180 })
  track.setPointerCapture = vi.fn()
  track.hasPointerCapture = () => true
  track.releasePointerCapture = vi.fn()
  document.querySelector('.mjr-edit-scroll').getBoundingClientRect = () => ({ left: 100, right: 460 })
  return track
}

test('dragging waveform seeks at displayed scale, selects the source clip and never changes the edit', () => {
  const { change } = setup()
  const track = navigationTrack()
  pointer(track.querySelector('canvas'), 'pointerdown', 150)
  expect(document.querySelector('[aria-label="Playback position"]').value).toBe('10')
  pointer(track, 'pointermove', 375)
  expect(document.querySelector('[aria-label="Playback position"]').value).toBe('55')
  expect(document.querySelector('.mjr-edit-selection').textContent).toContain('b (96')
  pointer(track, 'pointerup', 400)
  expect(track.getAttribute('aria-valuenow')).toBe('60')
  expect(change).not.toHaveBeenCalled()
})

test('ruler and playhead scrubbing clamp to edit bounds and cancel restores previous position', () => {
  setup()
  const track = navigationTrack()
  pointer(document.querySelector('.mjr-edit-ruler'), 'pointerdown', 250)
  pointer(track, 'pointerup', 250)
  expect(track.getAttribute('aria-valuenow')).toBe('30')
  pointer(document.querySelector('.mjr-edit-head'), 'pointerdown', 250)
  pointer(track, 'pointermove', 9999)
  expect(track.getAttribute('aria-valuenow')).toBe('71')
  pointer(track, 'pointercancel', 9999)
  expect(track.getAttribute('aria-valuenow')).toBe('30')
  expect(document.querySelector('.mjr-edit-selection').textContent).toContain('a (96')
  fireEvent.keyDown(track, { key: 'End' })
  expect(track.getAttribute('aria-valuenow')).toBe('71')
  fireEvent.keyDown(track, { key: 'ArrowLeft' })
  expect(track.getAttribute('aria-valuenow')).toBe('70')
  fireEvent.keyDown(track, { key: 'Home' })
  expect(track.getAttribute('aria-valuenow')).toBe('0')
})

test('source filmstrip trim synchronizes timeline live and commits one undoable command', () => {
  const { change, track } = setup()
  const handle = document.querySelector('[aria-label="Source trim end"]')
  pointer(handle, 'pointerdown', 0)
  pointer(track, 'pointermove', 120)
  expect(document.querySelector('.mjr-source-window').style.width).toBe('62.5%')
  expect(document.querySelector('.mjr-edit-clip').style.width).toBe('150px')
  expect(change).not.toHaveBeenCalled()
  pointer(track, 'pointerup', 120)
  expect(change).toHaveBeenCalledTimes(1)
  expect(change.mock.calls[0][0].clips[0]).toMatchObject({ in_frame: 12, out_frame: 72 })
  fireEvent.click([...document.querySelectorAll('button')].find(b => b.textContent === 'Undo'))
  expect(change.mock.calls[1][0].clips[0]).toMatchObject({ in_frame: 12, out_frame: 60 })
  expect(document.querySelector('.mjr-source-window').style.width).toBe('50%')
  fireEvent.click([...document.querySelectorAll('button')].find(b => b.textContent === 'Redo'))
  expect(change.mock.calls[2][0].clips[0].out_frame).toBe(72)
})

test('slipping filmstrip preserves timeline duration and clamps to available source frames', () => {
  const { change, track } = setup()
  pointer(document.querySelector('.mjr-source-window'), 'pointerdown', 0)
  pointer(track, 'pointermove', 9999)
  pointer(track, 'pointerup', 9999)
  expect(change.mock.calls[0][0].clips[0]).toMatchObject({ in_frame: 48, out_frame: 96 })
  expect(document.querySelector('.mjr-edit-clip').style.width).toBe('120px')
})

test('cancel restores the window without saving; keyboard trim updates filmstrip and timeline', () => {
  const { change, track } = setup()
  pointer(document.querySelector('[aria-label="Source trim start"]'), 'pointerdown', 0)
  pointer(track, 'pointermove', 9999)
  pointer(track, 'pointercancel', 9999)
  expect(change).not.toHaveBeenCalled()
  expect(document.querySelector('.mjr-source-window').style.left).toBe('12.5%')
  fireEvent.keyDown(document.querySelector('[aria-label="Source trim start"]'), { key: 'ArrowRight' })
  expect(change.mock.calls[0][0].clips[0]).toMatchObject({ in_frame: 13, out_frame: 60 })
  expect(document.querySelector('.mjr-edit-clip').style.width).toBe('117.5px')
})

test('timeline handles update filmstrip while dragging and commit the same source range', () => {
  const { change } = setup()
  const handle = document.querySelector('[aria-label="Trim end a"]')
  handle.setPointerCapture = vi.fn(); handle.releasePointerCapture = vi.fn()
  pointer(handle, 'pointerdown', 0)
  pointer(handle, 'pointermove', 30)
  expect(document.querySelector('.mjr-source-window').style.width).toBe('62.5%')
  expect(change).not.toHaveBeenCalled()
  pointer(handle, 'pointerup', 30)
  expect(change.mock.calls[0][0].clips[0].out_frame).toBe(72)
})

test('take replacement, precision fields and clip selection all update the filmstrip', () => {
  const { change } = setup()
  fireEvent.change(document.querySelector('[aria-label="Take"]'), { target: { value: 'take2' } })
  expect(change.mock.calls[0][0].clips[0].revision_id).toBe('take2')
  expect(document.querySelector('.mjr-source-window').style.width).toBe(`${100 * 48 / 144}%`)
  const inputs = document.querySelectorAll('.mjr-source-advanced input')
  fireEvent.change(inputs[0], { target: { value: 24 } })
  fireEvent.click([...document.querySelectorAll('button')].find(b => b.textContent === 'Apply trim'))
  expect(change.mock.calls[1][0].clips[0]).toMatchObject({ in_frame: 24, out_frame: 60 })
  expect(document.querySelector('.mjr-source-window').style.width).toBe('25%')
  fireEvent.click(document.querySelectorAll('.mjr-edit-body')[1])
  expect(document.querySelector('.mjr-edit-selection').textContent).toContain('b (96')
  expect(document.querySelector('.mjr-source-window').style.left).toBe('0%')
  expect(document.querySelector('.mjr-source-window').style.width).toBe('25%')
})
