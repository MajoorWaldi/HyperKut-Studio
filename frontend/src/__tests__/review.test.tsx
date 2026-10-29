import { render,screen,fireEvent,waitFor,cleanup } from '@testing-library/react'
import { afterEach,expect,test,vi } from 'vitest'
import { ReviewPanel,ReferenceEnergy } from '../components/ReviewPanel'

afterEach(cleanup)
test('missing measurements are not displayed as zero',()=>{
  render(<ReferenceEnergy energy={null} />)
  expect(screen.getByText(/not measured/i)).toBeTruthy()
})
test('review shows frames and does not automatically certify identity',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({frames:[{seconds:.5,url:'/frame.jpg'}],checks:{identity:'human_review'}}))))
  render(<ReviewPanel jobId="a" />)
  fireEvent.click(screen.getByRole('button',{name:/review/i}))
  await waitFor(()=>expect(screen.getByRole('img')).toBeTruthy())
  expect(screen.getByText(/identity.*manual/i)).toBeTruthy()
})
