import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { ArtDirection } from '../components/ArtDirection'
import { CountBadge } from '../components/CountBadge'
import { EditStyle, styleCounts } from '../components/EditStyle'
import { InputsPanel } from '../components/InputsPanel'
import { Options } from '../components/Options'
import { DEFAULTS } from '../settings'
import type { Inputs, JobState, Settings } from '../types'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const inputs: Inputs = { source: null, refs: [null, null, null, null, null], refVideo: null, music: null, voice: null }

test('a badge shows a number, says what it counts and disappears at zero', () => {
  const { container, rerender } = render(<CountBadge count={3} label="changed" />)
  expect(screen.getByRole('img', { name: '3 changed' }).textContent).toBe('3')
  rerender(<CountBadge count={0} label="changed" />)
  expect(container.textContent).toBe('')
})

test('the options count what changed in each group and in total', async () => {
  const settings = { ...DEFAULTS, casting: true, motion_title: 'NIGHT', bpm: 90, seed: 7 }
  render(<Options mode="music" settings={settings} busy={false} onSettings={vi.fn()} />)
  expect(screen.getByRole('img', { name: '4 changed' })).toBeTruthy()
  await userEvent.click(screen.getByText('Advanced options'))
  const head = (name: RegExp) => screen.getByRole('button', { name }) as HTMLElement
  expect(within(head(/Picture & editing/)).getByRole('img', { name: '2 changed' })).toBeTruthy()
  expect(within(head(/Music & sound/)).getByRole('img', { name: '1 changed' })).toBeTruthy()
  expect(within(head(/Quality & tools/)).getByRole('img', { name: '1 changed' })).toBeTruthy()
})

test('untouched options show no number', async () => {
  render(<Options mode="music" settings={DEFAULTS} busy={false} onSettings={vi.fn()} />)
  expect(screen.queryByRole('img')).toBeNull()
  await userEvent.click(screen.getByText('Advanced options'))
  expect(screen.queryByRole('img')).toBeNull()
})

test('the animated design counts its switch, its title and its layers', async () => {
  const settings = { ...DEFAULTS, motion_design: true, motion_title: 'NIGHT', motion_layers: '[{"template":"flash_hit","start":1},{"template":"letterbox","start":0,"end":4}]' }
  render(<Options mode="music" settings={settings} busy={false} onSettings={vi.fn()} />)
  await userEvent.click(screen.getByText('Advanced options'))
  await userEvent.click(screen.getByRole('button', { name: /Picture & editing/ }))
  const summary = screen.getByText('Animated design').closest('summary') as HTMLElement
  expect(within(summary).getByRole('img', { name: '4 active' })).toBeTruthy()
})

test('a reference video counts as one', () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}')))
  const video = { id: 'v', name: 'ref.mp4', kind: 'video' as const, url: '/v' }
  render(<InputsPanel mode="music" inputs={{ ...inputs, refVideo: video }} settings={{ ...DEFAULTS }} busy={false} onUpload={vi.fn()} onClear={vi.fn()} onSettings={vi.fn()} />)
  const summary = screen.getByText('Reference video').closest('summary') as HTMLElement
  expect(within(summary).getByRole('img', { name: '1 active' })).toBeTruthy()
})

test('the artistic direction counts the chosen looks and an approved brief', () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ fields: [] }))))
  const settings = { ...DEFAULTS, art_direction: { look: 'collage', mood: 'auto' }, approved_brief: 'My brief' } as Settings
  render(<ArtDirection mode="text" inputs={inputs} settings={settings} busy={false} onSettings={vi.fn()} />)
  const summary = screen.getByText('Artistic direction').closest('summary') as HTMLElement
  expect(within(summary).getByRole('img', { name: '2 active' })).toBeTruthy()
})

test('the edit style counts what is on in each block', () => {
  const style = { effects: true, text: true, auto_sfx: true, motion_design: true, motion_layers: '[{"template":"flash_hit","start":1}]', motion_direction: 'editorial' }
  const job = { status: 'succeeded', shots: [{ done: true, duration: 3 }], style, output_url: '/video' } as unknown as JobState
  render(<EditStyle job={job} onApply={vi.fn()} />)
  const block = (title: string) => screen.getByText(title, { selector: 'h4' }).closest('section') as HTMLElement
  expect(within(block('Editing')).getByRole('img', { name: '2 active' })).toBeTruthy()
  expect(within(block('Sound')).getByRole('img', { name: '1 active' })).toBeTruthy()
  expect(within(block('Animated design')).getByRole('img', { name: '2 active' })).toBeTruthy()
})

test('one function counts a style for the panel and for its tab', () => {
  expect(styleCounts({})).toEqual({ editing: 0, sound: 0, design: 0 })
  expect(styleCounts({ sub_cuts: true, effects: true, text: false, auto_sfx: true, motion_design: true, motion_layers: '[{"template":"flash_hit","start":1},{"template":"letterbox"}]' })).toEqual({ editing: 2, sound: 1, design: 3 })
  expect(styleCounts({ motion_layers: '{nope' })).toEqual({ editing: 0, sound: 0, design: 0 })
})

test('the panel counts a change before it is applied', async () => {
  const job = { status: 'succeeded', shots: [{ done: true, duration: 3 }], style: { effects: true }, output_url: '/video' } as unknown as JobState
  render(<EditStyle job={job} onApply={vi.fn()} />)
  const editing = () => screen.getByText('Editing', { selector: 'h4' }).closest('section') as HTMLElement
  expect(within(editing()).getByRole('img', { name: '1 active' })).toBeTruthy()
  await userEvent.click(screen.getByRole('checkbox', { name: 'Text' }))
  expect(within(editing()).getByRole('img', { name: '2 active' })).toBeTruthy()
})
