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
  const enabled=container.querySelector('details input[type="checkbox"]') as HTMLInputElement
  expect(enabled.checked).toBe(false)
  fireEvent.change(cueEditor,{target:{value:'[]'}})
  fireEvent.click(container.querySelector('button.primary')!)
  expect(apply).toHaveBeenCalledWith({motion_cues:'[]'})
})
