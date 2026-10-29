import { cleanup,render,screen,waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach,beforeEach,expect,test,vi } from 'vitest'
import { ArtDirection } from '../components/ArtDirection'
import { DEFAULTS } from '../settings'
const inputs={source:null,refs:[null,null,null,null,null],refVideo:null,music:null,voice:null}
beforeEach(()=>{vi.stubGlobal('fetch',vi.fn(async (url:string)=>new Response(JSON.stringify(url==='/api/art-direction'?{fields:[{key:'look',en:'Visual style',fr:'Style visuel',choices:[{value:'collage',en:'Paper collage',fr:'Collage papier'}]}]}:{brief:'An enriched urban portrait',context:'context-token'}))))})
afterEach(cleanup)
test('optional artistic direction prepares editable text and requires explicit use',async()=>{
 const change=vi.fn();render(<ArtDirection mode="text" inputs={inputs} settings={{...DEFAULTS,prompt:'Urban portrait'}} busy={false} onSettings={change}/> )
 await userEvent.click(screen.getByText('Artistic direction'))
 const style=await screen.findByLabelText('Visual style');expect((style as HTMLSelectElement).value).toBe('auto')
 await userEvent.selectOptions(style,'collage');expect(change).toHaveBeenLastCalledWith({art_direction:{look:'collage'}})
 change.mockClear();await userEvent.click(screen.getByText('Preview the creative brief'))
 const text=await screen.findByLabelText('Enriched brief — editable');expect(change).not.toHaveBeenCalled()
 await userEvent.clear(text);await userEvent.type(text,'My preferred direction')
 await userEvent.click(screen.getByText('Use this brief'))
 expect(change).toHaveBeenLastCalledWith({approved_brief:'My preferred direction',approved_brief_context:'context-token'})
})
test('a changed request discards an unaccepted prepared brief',async()=>{
 const props={mode:'text' as const,inputs,settings:{...DEFAULTS,prompt:'Urban portrait'},busy:false,onSettings:vi.fn()};const {rerender}=render(<ArtDirection {...props}/> )
 await userEvent.click(screen.getByText('Artistic direction'));await userEvent.click(screen.getByText('Preview the creative brief'));await screen.findByDisplayValue('An enriched urban portrait')
 rerender(<ArtDirection {...props} settings={{...props.settings,prompt:'Quiet portrait'}}/> )
 await waitFor(()=>expect(screen.queryByDisplayValue('An enriched urban portrait')).toBeNull())
})

test('changing a creative level preserves a manual draft and can reuse it without a model call',async()=>{
 const props={mode:'text' as const,inputs,settings:{...DEFAULTS,prompt:'Urban portrait'},busy:false,onSettings:vi.fn()}
 const {rerender}=render(<ArtDirection {...props}/> )
 await userEvent.click(screen.getByText('Artistic direction'));await userEvent.click(screen.getByText('Preview the creative brief'))
 const text=await screen.findByLabelText('Enriched brief — editable')
 await userEvent.clear(text);await userEvent.type(text,'My carefully edited direction')
 rerender(<ArtDirection {...props} settings={{...props.settings,creativity:85}}/> )
 expect(screen.getByDisplayValue('My carefully edited direction')).toBeTruthy()
 const calls=(fetch as ReturnType<typeof vi.fn>).mock.calls.length
 await userEvent.click(screen.getByText('Use this brief'))
 await waitFor(()=>expect(props.onSettings).toHaveBeenCalledWith({approved_brief:'My carefully edited direction',approved_brief_context:'context-token'}))
 expect((fetch as ReturnType<typeof vi.fn>).mock.calls.slice(calls).map(call=>call[0])).toEqual(['/api/brief-approve'])
})
