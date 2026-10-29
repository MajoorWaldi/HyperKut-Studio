import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { Slot } from '../components/Slot'
import { dictionaries } from '../i18n'
import type { Upload } from '../types'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
const audio = (id: string): Upload => ({ id, kind: 'audio', url: `/api/uploads/${id}`, name: `${id}.wav` })
const props = { accept: 'audio/*', label: 'Music', onFile: vi.fn() }

test('selected audio shows a measured waveform, updates on replacement and clears', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([0, .4, 1, .2]))))
  const { rerender } = render(<Slot {...props} value={audio('first')} />)
  expect(await screen.findByRole('img', { name: dictionaries.en.waveform })).toBeTruthy()
  expect(screen.getByText('first.wav')).toBeTruthy()
  rerender(<Slot {...props} value={audio('second')} />)
  await waitFor(() => expect(fetch).toHaveBeenLastCalledWith('/api/uploads/second/waveform', expect.anything()))
  rerender(<Slot {...props} value={null} />)
  expect(screen.queryByRole('img')).toBeNull()
})

test('failed decoding keeps the filename and exposes an error', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 422 })))
  render(<Slot {...props} value={audio('bad')} />)
  expect(await screen.findByText(dictionaries.en.waveformError)).toBeTruthy()
  expect(screen.getByText('bad.wav')).toBeTruthy()
})

test('late response for an old upload never replaces the new waveform', async () => {
  let resolveFirst!: (response: Response) => void
  vi.stubGlobal('fetch', vi.fn((url: string) => url.includes('first')
    ? new Promise<Response>(resolve => { resolveFirst = resolve })
    : Promise.resolve(new Response(JSON.stringify([1, 0])))))
  const { rerender } = render(<Slot {...props} value={audio('first')} />)
  rerender(<Slot {...props} value={audio('second')} />)
  await screen.findByRole('img')
  resolveFirst(new Response(JSON.stringify([.2, .3, .4])))
  await waitFor(() => expect(screen.getByRole('img').getAttribute('viewBox')).toBe('0 0 2 100'))
})
