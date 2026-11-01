import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import * as api from '../api'
import { Examples } from '../components/Examples'
import { ReviewPanel } from '../components/ReviewPanel'
import type { Preset } from '../types'

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

const preset = (id: string): Preset => ({ id, name: id, description: '', mode: 'text', prompt: id, settings: {}, preview: `${id}.mp4` } as unknown as Preset)

test('only the example under the pointer plays its loop', () => {
  const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined)
  const { container } = render(<Examples presets={[preset('a'), preset('b')]} applied={null} onApply={vi.fn()} />)
  expect(play).not.toHaveBeenCalled()
  fireEvent.mouseEnter(container.querySelector('.example-card')!)
  expect(play).toHaveBeenCalledTimes(1)
})

test('the review panel shows the energy of the result and seeks to a frame', async () => {
  vi.spyOn(api, 'reviewJob').mockResolvedValue({ frames: [{ seconds: 1.5, url: '/f.jpg' }], checks: {} })
  const seek = vi.fn()
  render(<ReviewPanel jobId="a" energy={{ status: 'measured', reference: { cut_rate: 1 }, result: { cut_rate: 2 }, ratios: {} }} onSeek={seek} />)
  expect(screen.getByText(/Energy: reference and result/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: /review result/i }))
  fireEvent.click(await screen.findByRole('button', { name: /1\.50 s/ }))
  expect(seek).toHaveBeenCalledWith(1.5)
})

test('a failed review reports the server message, not a raw error object', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'This job has no video' }), { status: 404 })))
  render(<ReviewPanel jobId="a" />)
  fireEvent.click(screen.getByRole('button', { name: /review result/i }))
  await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('This job has no video'))
})

test('choosing a take and moving its window is a single request', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: 'j' }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  await api.takeEdit('j', 'SHOT_001', 'take_002', 1.5)
  expect(fetchMock).toHaveBeenCalledTimes(1)
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toBe('/api/jobs/j/shots/SHOT_001/take-edit')
  expect(JSON.parse(init.body as string)).toEqual({ take: 'take_002', start: 1.5 })
})
