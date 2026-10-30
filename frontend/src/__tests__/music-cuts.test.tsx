import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { Options } from '../components/Options'
import { DEFAULTS, optionDefaults, restoreSettings } from '../settings'
import { createJob } from '../api'
import type { Settings } from '../types'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

async function show(changes: Partial<Settings> = {}, busy = false) {
  const onSettings = vi.fn()
  const props = {mode: 'music' as const, settings: {...DEFAULTS, ...changes}, busy, onSettings}
  const rendered = render(<Options {...props}/>)
  await userEvent.click(screen.getByText('Advanced options'))
  await userEvent.click(screen.getByText('Music & sound'))
  return {...rendered, props, onSettings}
}

test('new music defaults to adaptive with variation and synchronization', async () => {
  const {onSettings} = await show()
  expect((screen.getByLabelText('Editing rhythm') as HTMLSelectElement).value).toBe('adaptive')
  expect(screen.queryByLabelText('Cut every')).toBeNull()
  expect((screen.getByLabelText('Cut pace') as HTMLSelectElement).value).toBe('auto')
  const variation = screen.getByLabelText('Duration variation · 100%')
  fireEvent.change(variation, {target: {value: '.75'}})
  expect(onSettings).toHaveBeenLastCalledWith({music_cut_variation: .75})
  fireEvent.change(screen.getByLabelText('Musical synchronization · 100%'), {target: {value: '.25'}})
  expect(onSettings).toHaveBeenLastCalledWith({music_cut_sync: .25})
})

test('regular reveals grid and free hides synchronization', async () => {
  const {rerender, props, onSettings} = await show({music_edit_mode: 'regular'})
  expect(screen.getByLabelText('Cut every')).toBeTruthy()
  expect(screen.queryByRole('slider')).toBeNull()
  await userEvent.selectOptions(screen.getByLabelText('Editing rhythm'), 'free')
  expect(onSettings).toHaveBeenLastCalledWith({music_edit_mode: 'free'})
  rerender(<Options {...props} settings={{...props.settings, music_edit_mode: 'free'}}/>)
  expect(screen.queryByLabelText('Cut every')).toBeNull()
  expect(screen.queryByRole('slider')).toBeNull()
})

test('legacy settings remain visible and reset includes the new fields', async () => {
  await show({music_edit_mode: 'legacy'})
  expect((screen.getByLabelText('Editing rhythm') as HTMLSelectElement).value).toBe('legacy')
  expect(screen.getByLabelText('Cut every')).toBeTruthy()
  expect(optionDefaults()).toMatchObject({music_edit_mode: 'adaptive', music_cut_sync: 1, music_cut_variation: 1})
})

test('busy controls cannot be changed and Text also defaults to adaptive', async () => {
  const {rerender, props} = await show({}, true)
  expect((screen.getByLabelText('Editing rhythm') as HTMLSelectElement).disabled).toBe(true)
  expect(screen.getAllByRole('slider').every(el => (el as HTMLInputElement).disabled)).toBe(true)
  rerender(<Options {...props} mode="text"/>)
  expect((screen.getByLabelText('Editing rhythm') as HTMLSelectElement).value).toBe('adaptive')
})

test('Remix shows random controls only with new music', async () => {
  const {rerender, props} = await show()
  rerender(<Options {...props} mode="remix" settings={{...props.settings, audio: 'original'}}/>)
  expect(screen.queryByLabelText('Editing rhythm')).toBeNull()
  rerender(<Options {...props} mode="remix" settings={{...props.settings, audio: 'new'}}/>)
  expect((screen.getByLabelText('Editing rhythm') as HTMLSelectElement).value).toBe('adaptive')
  rerender(<Options {...props} mode="remix" settings={{...props.settings, audio: 'voice'}}/>)
  expect(screen.queryByLabelText('Editing rhythm')).toBeNull()
})

test('opening old projects preserves legacy timing while new presets keep random', () => {
  expect(restoreSettings({cut_every: 'bar'})).toMatchObject({music_edit_mode: 'legacy', music_cut_sync: 1, music_cut_variation: .5, cut_every: 'bar'})
  expect(restoreSettings({music_edit_mode: 'random'}).music_edit_mode).toBe('random')
  expect(DEFAULTS.music_edit_mode).toBe('adaptive')
})

test('an old real Studio backend cannot silently ignore the new controls', async () => {
  const fetch = vi.fn(async () => new Response(JSON.stringify({mock: false})))
  vi.stubGlobal('fetch', fetch)
  await expect(createJob('music', DEFAULTS, {source: null, refs: [], refVideo: null, music: null, voice: null})).rejects.toThrow('Restart Studio')
  expect(fetch.mock.calls).toHaveLength(1)
  expect(fetch).toHaveBeenCalledWith('/api/health?mode=music&refs=0&ref_video=false&voice=false', {cache: 'no-store'})
})
