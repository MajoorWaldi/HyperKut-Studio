import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { EditStyle } from '../components/EditStyle'
import type { JobState } from '../types'

afterEach(cleanup)

test('each layer editor shows its own saved JSON and additional music starts at zero', () => {
  const apply=vi.fn()
  const layers='[{"type":"text","content":"LEGACY"}]'
  const cues='[{"text":"HYPERFRAMES","start":1,"end":2}]'
  const job={status:'succeeded',shots:[{done:true}],style:{motion_layers:layers,motion_cues:cues,motion_direction:'editorial'},output_url:'/video'} as JobState
  const {container}=render(<EditStyle job={job} onApply={apply}/> )
  const editors=Array.from(container.querySelectorAll('textarea'))
  expect(editors.find(e=>e.value===JSON.stringify(JSON.parse(layers),null,2))).toBeTruthy()
  const cueEditor=editors.find(e=>e.value===JSON.stringify(JSON.parse(cues),null,2))!
  expect(cueEditor).toBeTruthy()
  const ranges=screen.getAllByRole('slider') as HTMLInputElement[]
  expect(ranges[ranges.length-1].value).toBe('0')
  const enabled=screen.getByLabelText(/animated design/i) as HTMLInputElement
  expect(enabled.checked).toBe(false)
  fireEvent.change(cueEditor,{target:{value:'[]'}})
  fireEvent.click(container.querySelector('button.primary')!)
  expect(apply).toHaveBeenCalledWith({motion_cues:'[]'})
})

test('the actions sit in the header, count the changes and add a template to the layers of a finished job', () => {
  const apply=vi.fn()
  const job={status:'succeeded',shots:[{done:true}],style:{motion_layers:'[]',motion_direction:'editorial'},output_url:'/video'} as JobState
  render(<EditStyle job={job} onApply={apply}/>)
  const action=screen.getByRole('button',{name:/edit again/i}) as HTMLButtonElement
  expect(action.disabled).toBe(true)
  expect(action.closest('header')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'flash hit'}))
  expect(screen.getByRole('status').textContent).toMatch(/1 change/)
  fireEvent.click(screen.getByLabelText(/animated design/i))
  fireEvent.click(screen.getByRole('button',{name:'Energetic'}))
  expect(screen.getByRole('status').textContent).toMatch(/3 changes/)
  fireEvent.click(action)
  expect(apply).toHaveBeenCalledWith({motion_layers:expect.stringContaining('flash_hit'),motion_design:true,motion_direction:'energetic'})
})
