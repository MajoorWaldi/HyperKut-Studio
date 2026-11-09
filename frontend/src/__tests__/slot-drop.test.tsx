import { describe, expect, it } from 'vitest'
import { accepts } from '../components/Slot'

describe('Slot drag and drop', () => {
  it('takes the kind of file the slot asks for and nothing else', () => {
    expect(accepts('video/*', { name: 'a.mp4', type: 'video/mp4' })).toBe(true)
    expect(accepts('audio/*', { name: 'a.mp4', type: 'video/mp4' })).toBe(false)
    expect(accepts('image/*', { name: 'a.PNG', type: 'image/png' })).toBe(true)
    expect(accepts('.zip,application/zip', { name: 'p.ZIP', type: '' })).toBe(true)
  })
})
