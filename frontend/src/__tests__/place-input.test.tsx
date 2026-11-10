import { cleanup, fireEvent, render } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { createJob } from '../api'
import { InputsPanel } from '../components/InputsPanel'
import { DEFAULTS } from '../settings'
import type { Inputs, Settings } from '../types'

vi.mock('../components/ArtDirection', () => ({ ArtDirection: () => null }))
vi.mock('../components/Options', () => ({ Options: () => null }))
vi.mock('../components/VideoModel', () => ({ VideoModel: () => null }))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const EMPTY: Inputs = { source: null, refs: [null, null, null, null, null], refVideo: null, music: null, voice: null, place: null }
const room = { id: 'pl', name: 'room.png', kind: 'image' as const, url: '/room.png' }

test('a picture of the place has its own slot, in every mode', () => {
  for (const mode of ['text', 'music', 'remix'] as const) {
    const onUpload = vi.fn()
    const { container, unmount } = render(<InputsPanel mode={mode} inputs={EMPTY} settings={{ prompt: '', audio: 'original', dialogue: '' } as Settings} busy={false}
      onUpload={onUpload} onClear={vi.fn()} onSettings={vi.fn()} />)
    const place = [...container.querySelectorAll('details')].find(d => /Place picture|Image du lieu/.test(d.querySelector('summary')?.textContent ?? ''))!
    const file = new File(['x'], 'room.png', { type: 'image/png' })
    fireEvent.change(place.querySelector('input[type=file]')!, { target: { files: [file] } })
    expect(onUpload).toHaveBeenCalledWith('place', file)
    unmount()
  }
})

test('the picture of the place goes with the job', async () => {
  const fetch = vi.fn(async () => new Response(JSON.stringify({ mock: true })))
  vi.stubGlobal('fetch', fetch)
  await createJob('text', DEFAULTS, { ...EMPTY, place: room })
  const body = JSON.parse(String((fetch.mock.calls.at(-1) as unknown as [string, RequestInit])[1].body))
  expect(body.place).toBe('pl')
  await createJob('text', DEFAULTS, EMPTY)
  expect(JSON.parse(String((fetch.mock.calls.at(-1) as unknown as [string, RequestInit])[1].body)).place).toBeNull()
})
