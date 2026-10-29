import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { TakeTrim } from '../components/TakeTrim'
import { I18n, dictionaries } from '../i18n'

afterEach(cleanup)
const take = {id:'take_001',active:true,url:'/take.mp4',duration:5,start:0,window:2,max_start:3,step:1/24}

test('moving the source window previews locally, applies explicitly, and clamps to its bounds', async () => {
  const video={current:document.createElement('video')}
  Object.defineProperty(video.current,'readyState',{value:1})
  const apply=vi.fn(async()=>{})
  render(<TakeTrim take={take} video={video} disabled={false} onApply={apply} />)
  const slider=screen.getByRole('slider',{name:'Move selected portion'})
  fireEvent.keyDown(slider,{key:'End'})
  expect(slider.getAttribute('aria-valuenow')).toBe('3')
  expect(video.current.currentTime).toBe(3)
  expect(apply).not.toHaveBeenCalled()
  fireEvent.keyDown(slider,{key:'ArrowRight'})
  expect(slider.getAttribute('aria-valuenow')).toBe('3')
  fireEvent.click(screen.getByRole('button',{name:'Apply to edit'}))
  await waitFor(()=>expect(apply).toHaveBeenCalledWith(3))
})

test('inactive takes cannot change the edit and a fully consumed take has no movable window', () => {
  const video={current:document.createElement('video')}
  const {rerender}=render(<TakeTrim take={{...take,active:false}} video={video} disabled={false} onApply={vi.fn()} />)
  expect((screen.getByRole('slider') as HTMLButtonElement).disabled).toBe(true)
  expect(screen.queryByRole('button',{name:'Apply to edit'})).toBeNull()
  rerender(<TakeTrim take={{...take,max_start:0,window:5}} video={video} disabled={false} onApply={vi.fn()} />)
  expect(screen.getByText('This edit uses the full take.')).toBeTruthy()
})

test('French labels and reset remain usable after an edit consumes the whole take', () => {
  const video={current:document.createElement('video')}
  const apply=vi.fn(async()=>{})
  render(<I18n.Provider value={{lang:'fr',t:dictionaries.fr,setLang:vi.fn()}}><TakeTrim take={{...take,start:1,max_start:0,window:4}} video={video} disabled={false} onApply={apply} /></I18n.Provider>)
  expect(screen.getByRole('slider',{name:'Déplacer la portion'})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Au début'}))
  expect(screen.getByRole('slider').getAttribute('aria-valuenow')).toBe('0')
  fireEvent.click(screen.getByRole('button',{name:'Appliquer au montage'}))
  expect(apply).toHaveBeenCalledWith(0)
})
