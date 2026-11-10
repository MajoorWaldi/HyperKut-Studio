import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { InputsPanel } from '../components/InputsPanel'
import { kindOf, routeFiles } from '../drop'
import type { Inputs, Settings } from '../types'

vi.mock('../components/ArtDirection', () => ({ ArtDirection: () => null }))
vi.mock('../components/Options', () => ({ Options: () => null }))
vi.mock('../components/VideoModel', () => ({ VideoModel: () => null }))
afterEach(cleanup)

const EMPTY: Inputs = { source: null, refs: [null, null, null, null, null], refVideo: null, music: null, voice: null }
const file = (name: string, type: string) => new File(['x'], name, { type })
const video = file('clip.mp4', 'video/mp4'), song = file('song.mp3', 'audio/mpeg'), pdf = file('notes.pdf', 'application/pdf')
const pics = ['a.png', 'b.png', 'c.png'].map(name => file(name, 'image/png'))
const uploaded = { id: 'u', name: 'u', kind: 'image' as const, url: '/u' }

test('a file is known by its type, or by its extension when the system gives none', () => {
  expect([kindOf(video), kindOf(song), kindOf(pics[0]), kindOf(pdf)]).toEqual(['video', 'audio', 'image', null])
  expect(kindOf({ name: 'take.MOV', type: '' })).toBe('video')
})

test('each dropped file goes to the first free slot of its kind, and what has none is refused', () => {
  const remix = routeFiles([video, video, video, ...pics, song, pdf], { mode: 'remix', audio: 'original', inputs: { ...EMPTY, refs: [uploaded, null, null, null, null] } })
  expect(remix.placed.map(p => p.slot)).toEqual(['source', 'refVideo', { ref: 1 }, { ref: 2 }, { ref: 3 }])
  expect(remix.refused).toEqual([video, song, pdf])  // a third video, a sound with no sound slot in this audio choice, not a medium
  expect(routeFiles([song], { mode: 'music', audio: 'original', inputs: EMPTY }).placed).toEqual([{ slot: 'music', file: song }])
  expect(routeFiles([song], { mode: 'text', audio: 'voice', inputs: EMPTY }).placed).toEqual([{ slot: 'voice', file: song }])
  expect(routeFiles([video], { mode: 'text', audio: 'new', inputs: EMPTY }).placed).toEqual([{ slot: 'refVideo', file: video }])  // no source outside a Remix
  expect(routeFiles(pics, { mode: 'text', audio: 'new', inputs: EMPTY }, 2).placed.map(p => p.slot)).toEqual([{ ref: 2 }, { ref: 0 }, { ref: 1 }])  // the slot it was dropped on first
})

const panel = (mode: 'text' | 'music' | 'remix' = 'remix') => {
  const onUpload = vi.fn(), onRejected = vi.fn()
  const view = render(<InputsPanel mode={mode} inputs={EMPTY} settings={{ prompt: '', audio: 'original', dialogue: '' } as Settings} busy={false}
    onUpload={onUpload} onClear={vi.fn()} onRejected={onRejected} onSettings={vi.fn()} />)
  return { ...view, onUpload, onRejected }
}

test('files dropped anywhere on the panel go to their slots', () => {
  const { container, onUpload, onRejected } = panel('remix')
  fireEvent.drop(container.querySelector('aside')!, { dataTransfer: { files: [video, pics[0], pdf], types: ['Files'] } })
  expect(onUpload.mock.calls).toEqual([['source', video], [{ ref: 0 }, pics[0]]])
  expect(onRejected).toHaveBeenCalledWith([pdf])
})

test('several pictures dropped on a reference slot fill the free ones, a wrong kind is said', () => {
  const { container, onUpload, onRejected } = panel('text')
  const slot = container.querySelector('.ref-grid .slot-wrap')!
  fireEvent.drop(slot, { dataTransfer: { files: pics, types: ['Files'] } })
  expect(onUpload.mock.calls.map(call => call[0])).toEqual([{ ref: 0 }, { ref: 1 }, { ref: 2 }])
  fireEvent.drop(slot, { dataTransfer: { files: [song], types: ['Files'] } })
  expect(onRejected).toHaveBeenLastCalledWith([song])
  expect(onUpload).toHaveBeenCalledTimes(3)  // the slot did not take it, the panel did not route it again
  fireEvent.dragOver(container.querySelector('aside')!, { dataTransfer: { types: ['Files'], dropEffect: '' } })
  expect(container.querySelector('aside')!.className).toContain('drop-ready')
  fireEvent.drop(slot, { dataTransfer: { files: [pics[0]], types: ['Files'] } })
  expect(container.querySelector('aside')!.className).not.toContain('drop-ready')  // a drop taken by a slot ends the hint of the panel too
})

test('a slot shows while dragging whether the file can land on it', () => {
  const { container } = panel('remix')
  const source = container.querySelector('.slot-wrap')!
  fireEvent.dragOver(source, { dataTransfer: { types: ['Files'], items: [{ kind: 'file', type: 'audio/mpeg' }], dropEffect: '' } })
  expect(source.className).toContain('drag-refused')
  fireEvent.dragOver(source, { dataTransfer: { types: ['Files'], items: [{ kind: 'file', type: 'video/mp4' }], dropEffect: '' } })
  expect(source.className).toContain('drag-over')
})
