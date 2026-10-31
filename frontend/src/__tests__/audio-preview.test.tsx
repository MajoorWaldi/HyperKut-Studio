import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { Slot } from '../components/Slot'
import type { Upload } from '../types'

class FakeAudio {
  static all: FakeAudio[] = []
  paused = true
  duration = 10
  currentTime = 0
  listeners: Record<string, (() => void)[]> = {}
  src: string
  constructor(src: string) { this.src = src; FakeAudio.all.push(this) }
  addEventListener(name: string, fn: () => void) { (this.listeners[name] ??= []).push(fn) }
  emit(name: string) { this.listeners[name]?.forEach(fn => fn()) }
  play() { this.paused = false; return Promise.resolve() }
  pause() { if (!this.paused) { this.paused = true; this.emit('pause') } }
}

beforeEach(() => {
  FakeAudio.all = []
  vi.stubGlobal('Audio', FakeAudio)
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([0, .5, 1]))))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const audio = (id: string): Upload => ({ id, kind: 'audio', url: `/api/uploads/${id}`, name: `${id}.wav` })
const slot = (value: Upload | null, onClear = vi.fn()) => <Slot accept="audio/*" label="Music" value={value} onFile={vi.fn()} onClear={onClear} />

test('a loaded sound has a listen button that plays it, pauses it and plays on from there', () => {
  render(slot(audio('song')))
  fireEvent.click(screen.getByRole('button', { name: 'Listen' }))
  expect(FakeAudio.all).toHaveLength(1)
  expect(FakeAudio.all[0].src).toBe('/api/uploads/song')
  expect(FakeAudio.all[0].paused).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
  expect(FakeAudio.all[0].paused).toBe(true)
  expect(screen.getByRole('button', { name: 'Listen' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Listen' }))
  expect(FakeAudio.all).toHaveLength(1)
  expect(FakeAudio.all[0].paused).toBe(false)
})

test('nothing to listen to without a sound, or on a picture or a video', () => {
  const { rerender } = render(slot(null))
  expect(screen.queryByRole('button', { name: 'Listen' })).toBeNull()
  rerender(slot({ id: 'p', kind: 'image', url: '/p', name: 'p.png' }))
  expect(screen.queryByRole('button', { name: 'Listen' })).toBeNull()
  rerender(slot({ id: 'v', kind: 'video', url: '/v', name: 'v.mp4' }))
  expect(screen.queryByRole('button', { name: 'Listen' })).toBeNull()
})

test('the progress line follows the playing time and the end resets the button', () => {
  const { container } = render(slot(audio('song')))
  fireEvent.click(screen.getByRole('button', { name: 'Listen' }))
  act(() => { FakeAudio.all[0].currentTime = 5; FakeAudio.all[0].emit('timeupdate') })
  expect((container.querySelector('.upload-progress') as HTMLElement).style.left).toContain('0.5')
  act(() => { FakeAudio.all[0].paused = true; FakeAudio.all[0].emit('ended') })
  expect(container.querySelector('.upload-progress')).toBeNull()
  expect(screen.getByRole('button', { name: 'Listen' })).toBeTruthy()
})

test('another file, a cleared slot or a closed panel stops the sound', () => {
  const { rerender, unmount } = render(slot(audio('first')))
  fireEvent.click(screen.getByRole('button', { name: 'Listen' }))
  const first = FakeAudio.all[0]
  rerender(slot(audio('second')))
  expect(first.paused).toBe(true)
  expect(screen.getByRole('button', { name: 'Listen' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Listen' }))
  expect(FakeAudio.all[1].src).toBe('/api/uploads/second')
  unmount()
  expect(FakeAudio.all[1].paused).toBe(true)
})

test('two slots never play at once', () => {
  render(<>{slot(audio('music'))}{slot(audio('voice'))}</>)
  const [one, two] = screen.getAllByRole('button', { name: 'Listen' })
  fireEvent.click(one)
  fireEvent.click(two)
  expect(FakeAudio.all[0].paused).toBe(true)
  expect(FakeAudio.all[1].paused).toBe(false)
})

test('a sound that cannot be played leaves the button ready again', async () => {
  vi.stubGlobal('Audio', class extends FakeAudio { play() { return Promise.reject(new Error('blocked')) } })
  render(slot(audio('bad')))
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Listen' })) })
  expect(screen.getByRole('button', { name: 'Listen' })).toBeTruthy()
})
