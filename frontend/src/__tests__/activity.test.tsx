import { useRef } from 'react'
import { cleanup, render } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { useCompletionFlash, workingShots } from '../activity'
import type { JobState } from '../types'

const job=(patch:Partial<JobState>={})=>({id:'one',operation:1,status:'succeeded',stage:'done',shots:[{id:'A',done:true},{id:'B',done:true}],...patch}) as JobState
const original=Object.getOwnPropertyDescriptor(HTMLElement.prototype,'animate')
afterEach(()=>{cleanup();vi.unstubAllGlobals();if(original)Object.defineProperty(HTMLElement.prototype,'animate',original);else Reflect.deleteProperty(HTMLElement.prototype,'animate')})

function Signal({state}:{state:JobState}) {
  const ref=useRef<HTMLDivElement>(null)
  useCompletionFlash(ref,state)
  return <div ref={ref} />
}

test('only known affected shots pulse during regeneration; failures and editing stop shot pulses',()=>{
  expect(workingShots(job({status:'running',stage:'shots'}),['B'])).toEqual(['B'])
  expect(workingShots(job({status:'running',stage:'shots'}))).toEqual([])
  expect(workingShots(job({status:'failed',stage:'shots'}),['B'])).toEqual([])
  expect(workingShots(job({status:'running',stage:'edit'}),['B'])).toEqual([])
})

test('completion flashes once after observed work, never on an old result or error',()=>{
  const animate=vi.fn(()=>({cancel:vi.fn()}))
  Object.defineProperty(HTMLElement.prototype,'animate',{value:animate,configurable:true})
  const {rerender}=render(<Signal state={job()} />)
  expect(animate).not.toHaveBeenCalled()
  rerender(<Signal state={job({status:'running',stage:'edit',operation:2})} />)
  rerender(<Signal state={job({status:'failed',operation:2})} />)
  expect(animate).not.toHaveBeenCalled()
  rerender(<Signal state={job({status:'running',stage:'edit',operation:3})} />)
  rerender(<Signal state={job({operation:3})} />)
  expect(animate).toHaveBeenCalledTimes(1)
  rerender(<Signal state={job({operation:3,progress:1})} />)
  expect(animate).toHaveBeenCalledTimes(1)
})

test('reduced motion skips the completion flash',()=>{
  const animate=vi.fn()
  Object.defineProperty(HTMLElement.prototype,'animate',{value:animate,configurable:true})
  vi.stubGlobal('matchMedia',()=>({matches:true}))
  const {rerender}=render(<Signal state={job({status:'running',stage:'edit'})} />)
  rerender(<Signal state={job()} />)
  expect(animate).not.toHaveBeenCalled()
})
