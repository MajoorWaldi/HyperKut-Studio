import { createRef } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { PlayerControls } from '../components/PlayerControls'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

test('transport controls seek the actual player and reflect its playback events', () => {
  const video=createRef<HTMLVideoElement>(), container=createRef<HTMLDivElement>()
  const play=vi.spyOn(HTMLMediaElement.prototype,'play').mockResolvedValue(undefined)
  const pause=vi.spyOn(HTMLMediaElement.prototype,'pause').mockImplementation(()=>{})
  render(<div ref={container}><video ref={video} /><PlayerControls video={video} container={container} mediaKey="/video.mp4" shape="9:16" /></div>)
  Object.defineProperty(video.current,'duration',{value:8,configurable:true})
  fireEvent.loadedMetadata(video.current!)
  fireEvent.click(screen.getByRole('button',{name:'Play'}))
  expect(play).toHaveBeenCalledTimes(1)
  Object.defineProperty(video.current,'paused',{value:false,configurable:true})
  fireEvent.play(video.current!)
  fireEvent.click(screen.getByRole('button',{name:'Pause'}))
  expect(pause).toHaveBeenCalledTimes(1)
  fireEvent.change(screen.getByRole('slider',{name:'Playback position'}),{target:{value:'3.2'}})
  expect(video.current!.currentTime).toBe(3.2)
  fireEvent.timeUpdate(video.current!)
  expect(screen.getByText('00:03.20')).toBeTruthy()
  fireEvent.change(screen.getByRole('slider',{name:'Volume'}),{target:{value:'0.4'}})
  expect(video.current!.volume).toBe(.4)
  fireEvent.click(screen.getByRole('button',{name:'Mute'}))
  expect(video.current!.muted).toBe(true)
})

test('controls cannot seek unavailable media', () => {
  const video=createRef<HTMLVideoElement>(), container=createRef<HTMLDivElement>()
  render(<PlayerControls video={video} container={container} mediaKey={null} shape="16:9" />)
  expect((screen.getByRole('button',{name:'Play'}) as HTMLButtonElement).disabled).toBe(true)
  expect((screen.getByRole('slider',{name:'Playback position'}) as HTMLInputElement).disabled).toBe(true)
  expect((screen.getByRole('button',{name:'Loop playback'}) as HTMLButtonElement).disabled).toBe(true)
})

test('loop button toggles actual video looping without starting playback', () => {
  const video=createRef<HTMLVideoElement>(), container=createRef<HTMLDivElement>()
  const play=vi.spyOn(HTMLMediaElement.prototype,'play').mockResolvedValue(undefined)
  render(<div ref={container}><video ref={video} /><PlayerControls video={video} container={container} mediaKey="/video.mp4" shape="9:16" /></div>)
  Object.defineProperty(video.current,'duration',{value:8,configurable:true})
  fireEvent.loadedMetadata(video.current!)
  const button=screen.getByRole('button',{name:'Loop playback'})
  expect(button.getAttribute('aria-pressed')).toBe('false')
  fireEvent.click(button)
  expect(video.current!.loop).toBe(true)
  expect(button.getAttribute('aria-pressed')).toBe('true')
  fireEvent.click(button)
  expect(video.current!.loop).toBe(false)
  expect(button.getAttribute('aria-pressed')).toBe('false')
  expect(play).not.toHaveBeenCalled()
})
