import { useState } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { Dropdown } from '../components/Dropdown'
import App from '../App'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
beforeEach(() => localStorage.clear())

function Choice() {
  const [value, setValue] = useState('a')
  return <><Dropdown value={value} choices={[{value:'a',label:'First'},{value:'b',label:'Second'}]} label="Style" onChange={setValue} /><button>Next</button></>
}

test('keyboard choices have a focused listbox and restore trigger after selection', async () => {
  render(<Choice />)
  await userEvent.tab()
  const trigger = screen.getByRole('button', {name:'Style: First'})
  expect(document.activeElement).toBe(trigger)
  await userEvent.keyboard('{ArrowDown}')
  const menu = screen.getByRole('listbox', {name:'Style'})
  expect(document.activeElement).toBe(menu)
  await userEvent.keyboard('{End}')
  expect(document.getElementById(menu.getAttribute('aria-activedescendant')!)?.textContent).toContain('Second')
  await userEvent.keyboard('{Enter}')
  expect(screen.queryByRole('listbox')).toBeNull()
  expect(document.activeElement).toBe(screen.getByRole('button', {name:'Style: Second'}))
})

test('Escape restores focus and Tab closes without trapping the keyboard', async () => {
  render(<Choice />)
  const trigger = screen.getByRole('button', {name:'Style: First'})
  await userEvent.click(trigger)
  await userEvent.keyboard('{Escape}')
  expect(document.activeElement).toBe(trigger)
  await userEvent.keyboard('{ArrowDown}{Tab}')
  expect(screen.queryByRole('listbox')).toBeNull()
  expect(document.activeElement).toBe(screen.getByRole('button', {name:'Next'}))
})

test('empty or disabled dropdowns cannot expose an invalid active option', async () => {
  render(<Dropdown value="a" choices={[]} label="Empty" onChange={vi.fn()} />)
  const trigger = screen.getByRole('button', {name:/Empty/}) as HTMLButtonElement
  expect(trigger.disabled).toBe(true)
  await userEvent.click(trigger)
  expect(screen.queryByRole('listbox')).toBeNull()
})

test('document language follows the selected interface language', async () => {
  localStorage.setItem('secator.lang', 'fr')
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify([]))))
  render(<App />)
  await waitFor(() => expect(document.documentElement.lang).toBe('fr'))
  const trigger = screen.getByRole('button', {name:/Langue/})
  await userEvent.click(trigger)
  await userEvent.keyboard('{Home}{Enter}')
  await waitFor(() => expect(document.documentElement.lang).toBe('en'))
})

test('library moves focus inside and returns it on Escape; optional panels start closed', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => new Response(JSON.stringify(url === '/api/jobs' || url === '/api/presets' ? [] : {mock:true, comfyui:true, proxy:true, videotools:true}))))
  const {container} = render(<App />)
  await waitFor(() => expect(document.documentElement.lang).toBe('en'))
  const trigger = await screen.findByRole('button', {name:/Library/})
  await userEvent.click(trigger)
  const panel = screen.getByRole('region', {name:'Library'})
  await waitFor(() => expect(panel.contains(document.activeElement)).toBe(true))
  await userEvent.keyboard('{Escape}')
  expect(screen.queryByRole('region', {name:'Library'})).toBeNull()
  expect(document.activeElement).toBe(trigger)
  const panels = [...container.querySelectorAll<HTMLDetailsElement>('details.secondary-settings')]
  expect(panels.length).toBeGreaterThan(0)
  expect(panels.every(p => !p.open)).toBe(true)
})
