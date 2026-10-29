import { expect, test } from 'vitest'
import { beatGrid, rulerStep } from '../rhythm'

test('the grid uses measured music times, not the phase of the cuts', () => {
  const grid = beatGrid([1.1,2.1,3.1],120,4,[0,.25,.5,.75,1,1.25,1.5,1.75,2,2.25,2.5,2.75,3,3.25,3.5,3.75,4])!
  expect(grid.medianMs).toBe(100)
  expect(grid.ticks[0]).toBe(0)
})

test('a cut that is off the grid is measured as such, and no cut means no grid', () => {
  expect(beatGrid([0.0, 0.5, 1.0, 1.3], 120, 2)).toBeNull()
  expect(beatGrid([], 120, 4)).toBeNull()
  expect(beatGrid([1], 0, 4)).toBeNull()
})

test('the marks of the ruler get farther apart as the room gets smaller', () => {
  expect(rulerStep(15, 1500)).toBe(1)
  expect(rulerStep(15, 300)).toBe(5)
  expect(rulerStep(600, 300)).toBe(60)
})
