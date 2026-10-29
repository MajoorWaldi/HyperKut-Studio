"""Translate planned typography into the shared finishing layer contract."""
import json
import math
import re


def validate_finishing(values, duration):
    """Reject invalid finishing instructions before submitting any generation."""
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Motion values must be finite numbers')
        if isinstance(value, dict):
            for item in value.values(): finite(item)
        elif isinstance(value, list):
            for item in value: finite(item)

    def read(text, label):
        try:
            value = json.loads(text or '[]')
        except (ValueError, TypeError) as error:
            raise ValueError(f'{label} must be valid JSON') from error
        finite(value)
        return value

    raw = read(values.get('motion_layers', '[]'), 'Motion layers')
    if isinstance(raw,dict):
        if 'pack' in raw and raw['pack'] not in ('tech','editorial','pop'):
            raise ValueError('Motion pack must be tech, editorial or pop')
        if 'accent_from_subject' in raw and not isinstance(raw['accent_from_subject'],bool):
            raise ValueError('accent_from_subject must be boolean')
        if 'accent' in raw and not re.fullmatch(r'#[0-9a-fA-F]{6}',str(raw['accent'])):
            raise ValueError('Motion pack accent must use #RRGGBB')
    rows = raw.get('layers', []) if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or len(rows) > 120 or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Motion layers must contain at most 120 objects')
    for row in rows:
        if row.get('sound_palette') not in (None,'subtle','electronic','metallic'):
            raise ValueError('Unknown sound palette')
        if row.get('sync', 'none') not in ('none', 'onset'):
            raise ValueError('Motion sync must be none or onset')
        if 'shot_id' in row and not isinstance(row['shot_id'], str):
            raise ValueError('Motion shot_id must be text')
        for key in ('scene','id','after'):
            if key in row and row[key] is not None and (not isinstance(row[key],str) or len(row[key])>80):
                raise ValueError('Motion scene names must be short text')
        if 'design' in row and row['design'] not in ('tech','editorial','pop'):
            raise ValueError('Unknown motion design')
        for key in ('motion_from','motion_to'):
            if key in row and (not isinstance(row[key],dict) or set(row[key])-{'x','y','scale','rotate'}):
                raise ValueError('Motion transform keys: x, y, scale, rotate')
        kind = row.get('type', 'text')
        if kind not in ('text', 'emoji', 'box', 'brackets', 'outline', 'effect', 'track', 'vector'):
            raise ValueError(f'Unknown motion layer type: {kind}')
        if kind == 'vector' and row.get('shape', 'line') not in ('line', 'dot', 'ring'):
            raise ValueError('Motion vector shape must be line, dot or ring')
        if kind in ('text', 'emoji') and not str(row.get('content', '')).strip():
            raise ValueError('Text and emoji layers need content')
        if kind == 'effect' and row.get('kind', 'chromatic') not in ('chromatic', 'glitch', 'scanlines', 'grid', 'dots', 'grain', 'vignette', 'light_leak', 'pan', 'roll', 'handheld'):
            raise ValueError('Unknown motion effect')
        if kind in ('box', 'brackets') and 'rect' in row and (not isinstance(row['rect'], list) or len(row['rect']) != 4):
            raise ValueError('Motion rect must contain x, y, width and height')
        numeric = ('opacity', 'in_time') + {
            'text': ('size', 'rotate', 'stroke', 'repeat', 'x', 'y'),
            'emoji': ('size', 'rotate', 'stroke', 'repeat', 'x', 'y'),
            'box': ('thickness', 'arm'), 'brackets': ('thickness', 'arm'),
            'outline': ('width', 'glow'),
            'effect': ('amount', 'spacing', 'thickness', 'radius', 'flicker', 'speed'),
            'track': ('size', 'radius'),
            'vector': ('radius','thickness'),
        }[kind]
        try:
            for name in numeric:
                if name in row and not math.isfinite(float(row[name])):
                    raise ValueError('Non-finite motion value')
            if kind in ('text', 'emoji') and 'repeat' in row: int(row['repeat'])
            points = ('rect',) if kind in ('box', 'brackets') else ('at', 'offset') if kind == 'track' else ()
            for name in points:
                value = row.get(name)
                if isinstance(value, list) and len(value) == (4 if name == 'rect' else 2):
                    if any(not math.isfinite(float(v)) for v in value):
                        raise ValueError('Non-finite motion position')
            for name in ('start', 'end'):
                value = row.get(name)
                if value not in (None, '') and not math.isfinite(float(str(value).removesuffix('%'))):
                    raise ValueError('Non-finite motion time')
        except (ValueError, TypeError, OverflowError) as error:
            raise ValueError('Motion layer values and times must be numeric') from error
    direction = values.get('motion_direction', 'editorial') or 'editorial'
    if direction.lstrip().startswith('{'):
        spec = read(direction, 'Motion direction')
        if not isinstance(spec, dict) or set(spec) - {'preset', 'accent', 'reactive', 'title', 'intensity'}:
            raise ValueError('Invalid motion direction keys')
        if spec.get('preset', 'editorial') not in ('editorial', 'minimal', 'energetic'):
            raise ValueError('Unknown motion preset')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', str(spec.get('accent', '#e4c081'))):
            raise ValueError('Motion accent must use #RRGGBB')
        if not isinstance(spec.get('reactive', True), bool) or not isinstance(spec.get('title', ''), str) or len(spec.get('title', '')) > 120:
            raise ValueError('Invalid motion title or reactive flag')
        intensity = spec.get('intensity', .6)
        if isinstance(intensity, bool) or not isinstance(intensity, (float, int)) or not 0 <= intensity <= 1:
            raise ValueError('Motion intensity must be between 0 and 1')
    cues = read(values.get('motion_cues', '[]'), 'Motion cues')
    if not isinstance(cues, list) or len(cues) > 30:
        raise ValueError('Motion cues must contain at most 30 objects')
    windows = []
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) - {'shot_id', 'start', 'end', 'text', 'position'}:
            raise ValueError('Invalid motion cue keys')
        if not isinstance(cue.get('text', ''), str) or len(cue.get('text', '')) > 120 or cue.get('position', 'top') not in ('top', 'bottom'):
            raise ValueError('Invalid motion cue text or position')
        try:
            start = float(cue.get('start', 0))
            end = float(cue.get('end', min(duration, start + 2.4)))
        except (ValueError, TypeError) as error:
            raise ValueError('Motion cue times must be numeric') from error
        if not math.isfinite(start + end) or start < 0 or end > duration + 1 / 24 or end <= start:
            raise ValueError('Motion cues must fit the requested duration')
        if 'shot_id' not in cue and cue.get('text', '').strip(): windows.append((start, end))
    windows.sort()
    if any(a[1] > b[0] for a, b in zip(windows, windows[1:])):
        raise ValueError('Motion titles must not overlap')


def needs_subject_mask(text):
    data=json.loads(text or '[]')
    rows=data.get('layers',[]) if isinstance(data,dict) else data
    if not isinstance(rows,list):
        raise ValueError('Motion layers must be a list')
    return any(isinstance(row,dict) and (row.get('type')=='outline' or
        (row.get('type')=='effect' and row.get('target','frame')!='frame') or
        (row.get('type')=='track' and str(row.get('anchor','')).startswith('subject_'))) for row in rows)


def finishing_layers(manifest, shots, configured, text_on=True, motion_on=True):
    raw=json.loads(configured or '[]')
    rows=raw.get('layers',[]) if isinstance(raw,dict) else raw
    if not isinstance(rows,list):
        raise ValueError('Motion layers must be a JSON list')
    rows=list(rows)
    by_id={row['shot_id']:row for row in manifest.get('shots',[])}
    for shot in shots:
        plan = by_id.get(shot.id,{}).get('plan') or {}
        # A manual shot-local layer replaces planned layers for that same shot.
        if motion_on and not any(row.get('shot_id') == shot.id for row in rows):
            rows.extend({**layer, 'shot_id': shot.id} for layer in plan.get('motion', []))
        spec=(plan.get('fx') or {}).get('text') if text_on else None
        if not spec or not spec.get('content'):
            continue
        start=max(0.,float(spec.get('start') or 0))
        end=min(shot.duration,float(spec.get('end') if spec.get('end') is not None else shot.duration))
        if end<=start:
            continue
        content=spec['content'].upper() if spec.get('upper',True) else spec['content']
        rows.append({'type':'text','content':content,'position':spec.get('position','center'),
                     'size':spec.get('size',.08),'color':spec.get('color','white'),
                     'shot_id':shot.id,'start':start,'end':end,'rotate':spec.get('rotate',0),'repeat':spec.get('repeat',1),
                     'font':spec.get('font','impact'),'stroke':.06 if spec.get('stroke',True) else 0,
                     'animation':spec.get('animation','words'),'out':'fade' if spec.get('animation','words')!='none' else 'none','sync':'onset',
                     'background':spec.get('background',''),'safe':True,'accent_last':spec.get('accent_last',True)})
    if motion_on and isinstance(raw,dict) and raw.get('pack'):
        from .motion_presets import pack_layers
        rows.extend(pack_layers(raw['pack'],shots,manifest,rows,raw.get('accent','#e4c081')))
    if not text_on:
        referenced={(row.get('shot_id'),row.get('scene'),row.get('after')) for row in rows if row.get('after')}
        filtered=[]
        for row in rows:
            if row.get('type','text') not in ('text','emoji'):
                filtered.append(row)
            elif row.get('id') and (row.get('shot_id'),row.get('scene'),row['id']) in referenced:
                # Keep its timing anchor without drawing words or requesting its sound.
                anchor={key:row[key] for key in ('shot_id','scene','id','after','after_phase','delay','duration','start','end','in_time','sync') if key in row}
                filtered.append({**anchor,'type':'vector','shape':'dot','opacity':0})
        rows=filtered
    return json.dumps(rows,ensure_ascii=False)
