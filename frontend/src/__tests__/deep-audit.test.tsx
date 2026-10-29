import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../App'
import { follow } from '../api'
import { Timeline } from '../components/Timeline'
import type { JobState } from '../types'

class Stream {
  static all: Stream[] = []
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  constructor() { Stream.all.push(this) }
  close() { this.closed = true }
}

beforeEach(() => { localStorage.clear(); Stream.all = []; vi.stubGlobal('EventSource', Stream) })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })

test('a disconnected stream rereads the authoritative state and reconnects', async () => {
  vi.useFakeTimers()
  const states = vi.fn(), lost = vi.fn()
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ id: 'job', status: 'running' }))))
  const stop = follow('job', states, lost)
  Stream.all[0].onerror?.()
  await vi.advanceTimersByTimeAsync(500)
  expect(states).toHaveBeenCalledWith(expect.objectContaining({ status: 'running' }))
  expect(Stream.all).toHaveLength(2)
  Stream.all[1].onmessage?.({ data: JSON.stringify({ id: 'job', status: 'succeeded' }) })
  expect(Stream.all[1].closed).toBe(true)
  expect(lost).not.toHaveBeenCalled()
  stop()
})

test('stopping a follow cancels a scheduled reconnect', async () => {
  vi.useFakeTimers()
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher)
  const stop = follow('job', vi.fn(), vi.fn())
  Stream.all[0].onerror?.()
  stop()
  await vi.runAllTimersAsync()
  expect(fetcher).not.toHaveBeenCalled()
  expect(Stream.all).toHaveLength(1)
})

test('reconnection attempts are bounded when the server stays unavailable', async () => {
  vi.useFakeTimers()
  const lost = vi.fn(), fetcher = vi.fn(async () => { throw new Error('offline') })
  vi.stubGlobal('fetch', fetcher)
  follow('job', vi.fn(), lost)
  Stream.all[0].onerror?.()
  await vi.runAllTimersAsync()
  expect(fetcher).toHaveBeenCalledTimes(6)
  expect(lost).toHaveBeenCalledTimes(1)
})

test('rapid Generate clicks submit one job and a failed request unlocks the form', async () => {
  let finish: (response: Response) => void = () => {}
  const posted = vi.fn(() => new Promise<Response>(resolve => { finish = resolve }))
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/jobs' && init?.method === 'POST') return posted()
    return new Response(JSON.stringify(url === '/api/jobs' || url === '/api/presets' ? [] : { mock: true }))
  }))
  render(<App />)
  fireEvent.click(screen.getByRole('button', { name: /TEXT/ }))
  const generate = screen.getByRole('button', { name: /Generate/ })
  fireEvent.click(generate)
  fireEvent.click(generate)
  await waitFor(() => expect(posted).toHaveBeenCalledTimes(1))
  expect(generate.hasAttribute('disabled')).toBe(true)
  finish(new Response(JSON.stringify({ detail: 'injected request failure' }), { status: 503 }))
  await waitFor(() => expect(generate.hasAttribute('disabled')).toBe(false))
})

test('choosing another existing take changes the thumbnail URL', () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ shots: [] }))))
  const job = { id: 'job', mode: 'text', status: 'succeeded', stage: 'done', style: {}, shots: [{ id: 'A', start: 0, duration: 2, prompt: '', locked: false, done: true, takes: 2, version: 1, thumb: '/thumb' }] } as JobState
  const props = { job, position: null, selection: [], primary: 0, edits: {}, onSelect: vi.fn(), onSeek: vi.fn(), onRegenerate: vi.fn(), onLock: vi.fn() }
  const { container, rerender } = render(<Timeline {...props} />)
  const before = container.querySelector('.shot-image img')?.getAttribute('src')
  rerender(<Timeline {...props} job={{ ...job, shots: [{ ...job.shots[0], version: 2 }] }} />)
  expect(container.querySelector('.shot-image img')?.getAttribute('src')).not.toBe(before)
})
