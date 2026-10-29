import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,test,vi} from 'vitest'
import {Toolbar} from '../components/Toolbar'
import {DEFAULTS,applySettingsChanges} from '../settings'
afterEach(cleanup)

test('named controls expose actual levels instead of pseudo-percentages',()=>{
 const change=vi.fn();render(<Toolbar mode="text" settings={DEFAULTS} busy={false} onSettings={change}/>)
 const fidelity=screen.getByLabelText('Reference fidelity') as HTMLSelectElement
 expect(fidelity.value).toBe('85');expect(fidelity.options.length).toBe(3)
 fireEvent.change(screen.getByLabelText('Creative freedom'),{target:{value:'85'}})
 expect(change).toHaveBeenCalledWith({creativity:85})
 expect(screen.queryByText('85%')).toBeNull()
})

test('remix exposes its actual nonzero pose range with an accessible name',()=>{
 render(<Toolbar mode="remix" settings={DEFAULTS} busy={false} onSettings={vi.fn()}/>)
 const pose=screen.getByRole('slider',{name:/Motion guidance/}) as HTMLInputElement
 expect(pose.min).toBe('0.4');expect(pose.value).toBe('0.91')
 expect(screen.queryByLabelText('Creative freedom')).toBeNull()
})

test('control changes preserve manual text and invalidate only changed effective levels',()=>{
 const current={...DEFAULTS,approved_brief:'My manual direction',approved_brief_context:'token'}
 expect(applySettingsChanges(current,{structure:86}).approved_brief_context).toBe('token')
 const changed=applySettingsChanges(current,{creativity:85})
 expect(changed.approved_brief).toBe(current.approved_brief)
 expect(changed.approved_brief_context).toBe('')
})

test('fidelity without references is disabled with a visible explanation',()=>{
 render(<Toolbar mode="text" settings={DEFAULTS} hasReferences={false} busy={false} onSettings={vi.fn()}/>)
 expect((screen.getByLabelText('Reference fidelity') as HTMLSelectElement).disabled).toBe(true)
 expect(screen.getByText(/Add a visual reference/)).toBeTruthy()
})
