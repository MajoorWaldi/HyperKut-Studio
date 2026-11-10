import { afterEach, expect, test, vi } from 'vitest'
import * as api from '../api'

afterEach(() => vi.unstubAllGlobals())

test('an answer with no body is no value, not an error', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))
  await expect(api.recentJobs()).resolves.toBeUndefined()
})

test('a Studio that cannot be reached says so in words', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
  await expect(api.recentJobs()).rejects.toThrow('could not be reached')
})
