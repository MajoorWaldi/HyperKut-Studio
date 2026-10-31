import { useRef, useState, type PointerEvent } from 'react'
import { useI18n } from '../i18n'
import { addTemplate, CATEGORIES, categoryRows, describeRows, moveRow, parseRows, removeRow, setCategory, setText, setTimes, TEMPLATES, textRows, writeRows, type MotionRow } from '../motionLayers'

interface Props { layers: string; busy: boolean; onLayers: (json: string) => void; duration?: number }

const PIXELS = 26

/** The motion layers as a short list of choices, one list for each category, and everything else (all the templates, the layers with their times, the text track) in one folded block. Only the undo history lives here. */
export function MotionGallery({ layers, busy, onLayers, duration = 0 }: Props) {
  const { lang } = useI18n()
  const fr = lang === 'fr'
  const rows = parseRows(layers)
  const [history, setHistory] = useState<string[]>([])
  const drag = useRef<{ index: number; x: number } | null>(null)
  const edited = useRef('')
  /** `key` names a field being typed in: its keystrokes make one undo step. */
  const save = (next: MotionRow[], key = '') => {
    if (!key || key !== edited.current) setHistory(past => [...past.slice(-19), layers])
    edited.current = key
    onLayers(writeRows(next, layers))
  }
  const undo = () => {
    const previous = history[history.length - 1]
    if (previous === undefined) return
    setHistory(past => past.slice(0, -1))
    edited.current = ''
    onLayers(previous)
  }
  const onDown = (event: PointerEvent<HTMLDivElement>, index: number) => {
    if (busy || (event.target as HTMLElement).tagName === 'INPUT') return
    event.currentTarget.setPointerCapture?.(event.pointerId)
    drag.current = { index, x: event.clientX }
  }
  const onUp = (event: PointerEvent<HTMLDivElement>) => {
    if (!drag.current || !rows) return
    const { index, x } = drag.current
    drag.current = null
    if (event.clientX !== x) save(moveRow(rows, index, (event.clientX - x) / PIXELS, duration))
  }
  const blocks = rows ? textRows(rows) : []
  const list = rows ? describeRows(rows) : []
  const time = (value: unknown) => typeof value === 'number' ? value : ''
  if (!rows) return <p className="tiny-label">{fr ? 'Le JSON des calques est invalide : corrige-le pour utiliser la galerie.' : 'The layers JSON is invalid: fix it to use the gallery.'}</p>
  return (
    <div className="motion-gallery">
      <div className="gallery-head">
        <span className="gallery-title">Motion</span>
        <button type="button" className="gallery-undo" disabled={busy || history.length === 0} onClick={undo} title={fr ? 'Annuler le dernier changement de calques' : 'Undo the last layers change'}>↶ {fr ? 'Annuler' : 'Undo'}</button>
      </div>
      <div className="cat-selects">
        {CATEGORIES.map(category => {
          const present = categoryRows(rows, category.id)
          const value = present.length === 0 ? '' : present.length === 1 ? String(rows[present[0]].template) : '__many__'
          return (
            <label className="cat-select" key={category.id} data-cat={category.id} title={fr ? `${category.fr} : choisis un effet, il remplace celui de cette liste.` : `${category.en}: pick one, it replaces the one of this list.`}>
              <span>{fr ? category.fr : category.en}</span>
              <select aria-label={fr ? category.fr : category.en} value={value} disabled={busy} onChange={event => save(setCategory(rows, category.id, event.target.value, duration))}>
                <option value="">{fr ? 'Aucun' : 'None'}</option>
                {value === '__many__' && <option value="__many__" disabled>{fr ? `Plusieurs (${present.length})` : `Several (${present.length})`}</option>}
                {Object.entries(TEMPLATES).filter(([, template]) => template.category === category.id).map(([id]) => <option key={id} value={id}>{id.replaceAll('_', ' ')}</option>)}
              </select>
            </label>
          )
        })}
      </div>
      <details className="gallery-more">
        <summary>{fr ? `Tous les templates, calques et piste texte · ${list.length}` : `All templates, layers and text track · ${list.length}`}</summary>
        <div className="tag-groups">
          {CATEGORIES.map(category => (
            <div className="tag-group" key={category.id}>
              <span className="tag-label">{fr ? category.fr : category.en}</span>
              <div className="template-grid">
                {Object.entries(TEMPLATES).filter(([, template]) => template.category === category.id).map(([id, template]) => (
                  <button type="button" key={id} data-cat={category.id} disabled={busy} title={fr ? template.fr : template.en} onClick={() => save(addTemplate(rows, id, duration))}>{id.replaceAll('_', ' ')}</button>
                ))}
              </div>
            </div>
          ))}
        </div>
        {list.length > 0 && <>
          <span className="gallery-title">{fr ? `Calques sur ce montage · ${list.length}` : `Layers on this edit · ${list.length}`}</span>
          <ul className="layer-list">
            {list.map(item => (
              <li key={item.index} className="layer-row" data-cat={item.category ?? 'other'}>
                <span className="layer-name" title={item.text ? `${item.name}: ${item.text}` : item.name}>{item.name}{item.text && <small> · {item.text}</small>}</span>
                {item.timed && <>
                  <input type="number" step={0.1} min={0} aria-label={fr ? `Début de ${item.name}` : `Start of ${item.name}`} value={time(item.start)} disabled={busy} onChange={event => event.target.value !== '' && save(setTimes(rows, item.index, { start: Number(event.target.value) }, duration), `start:${item.index}`)} />
                  {typeof item.end === 'number' ? <input type="number" step={0.1} min={0} aria-label={fr ? `Fin de ${item.name}` : `End of ${item.name}`} value={item.end} disabled={busy} onChange={event => event.target.value !== '' && save(setTimes(rows, item.index, { end: Number(event.target.value) }, duration), `end:${item.index}`)} /> : <span className="layer-point">{fr ? 'instant' : 'instant'}</span>}
                </>}
                <button type="button" aria-label={fr ? `Retirer ${item.name}` : `Remove ${item.name}`} disabled={busy} onClick={() => save(removeRow(rows, item.index))}>×</button>
              </li>
            ))}
          </ul>
        </>}
        {blocks.length > 0 && <>
          <span className="gallery-title">{fr ? 'Piste texte' : 'Text track'}</span>
          <div className="text-track" role="list">
            {blocks.map(block => (
              <div role="listitem" key={block.index} className="text-block" style={{ left: block.start * PIXELS, width: Math.max((block.end - block.start) * PIXELS, 70) }} onPointerDown={event => onDown(event, block.index)} onPointerUp={onUp}>
                <input aria-label={fr ? 'Texte' : 'Text'} value={block.text} disabled={busy} onChange={event => save(setText(rows, block.index, event.target.value), `text:${block.index}`)} />
              </div>
            ))}
          </div>
        </>}
      </details>
    </div>
  )
}
