import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import type { Health } from '../types'

const ready: Health = { mock: false, comfyui: true, proxy: true, videotools: true, output_dir: 'output', missing_nodes: [], missing_models: [] }
const response = (value: unknown) => new Response(JSON.stringify(value))

beforeEach(() => localStorage.clear())
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('mode changes refresh scoped health and an older failing response cannot block the new mode', async () => {
  let finishRemix!: (value: Response) => void
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (!url.startsWith('/api/health')) return response([])
    const mode = new URL(url, 'http://studio').searchParams.get('mode')
    if (mode === 'remix') return new Promise<Response>(resolve => { finishRemix = resolve })
    return response({ ...ready, mode })
  }))
  const { container } = render(<App />)
  await waitFor(() => expect(finishRemix).toBeTypeOf('function'))
  await userEvent.click(screen.getByRole('button', { name: /TEXT/ }))
  await waitFor(() => expect(container.querySelector('.head-right .dot.on')).toBeTruthy())
  await act(async () => { finishRemix(response({ ...ready, mode: 'remix', videotools: false, missing_nodes: ['RemixOnly'] })) })
  expect(screen.queryByText(/RemixOnly/)).toBeNull()
  expect(container.querySelector('.head-right .dot.on')).toBeTruthy()
  expect((screen.getByRole('button', { name: /Generate/ }) as HTMLButtonElement).disabled).toBe(false)
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('mode=text'))).toBe(true)
})

test('an older ready response cannot hide the selected mode missing models', async () => {
  let finishRemix!: (value: Response) => void
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (!url.startsWith('/api/health')) return response([])
    const mode = new URL(url, 'http://studio').searchParams.get('mode')
    if (mode === 'remix') return new Promise<Response>(resolve => { finishRemix = resolve })
    return response({ ...ready, mode, missing_models: mode === 'text' ? ['CheckpointLoaderSimple.ckpt_name: TextOnly'] : [] })
  }))
  const { container } = render(<App />)
  await waitFor(() => expect(finishRemix).toBeTypeOf('function'))
  await userEvent.click(screen.getByRole('button', { name: /TEXT/ }))
  expect(await screen.findByText('CheckpointLoaderSimple.ckpt_name: TextOnly')).toBeTruthy()
  await act(async () => { finishRemix(response({ ...ready, mode: 'remix' })) })
  expect(screen.getByText('CheckpointLoaderSimple.ckpt_name: TextOnly')).toBeTruthy()
  expect(container.querySelector('.head-right .dot.on')).toBeNull()
  await userEvent.click(container.querySelector('.head-right .chip')!)
  await userEvent.click(screen.getByRole('button', { name: /MUSIC/ }))
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('mode=music'))).toBe(true))
  await waitFor(() => expect(container.querySelector('.head-right .dot.on')).toBeTruthy())
  expect(screen.queryByText(/TextOnly/)).toBeNull()
})
