"""Small opt-in finishing defaults. No model calls, remote assets or invented copy."""
from collections import Counter
from PIL import Image
import colorsys
import json

PACKS = ('tech', 'editorial', 'pop')


def with_motion_accent(direction, color):
    """Add only color; let the existing renderer resolve plain-language intent."""
    if direction.lstrip().startswith('{'):
        return json.dumps({**json.loads(direction),'accent':color})
    return direction.rstrip()+' '+color


def subject_accent(path, mask=None):
    """Conservative center/foreground color; abstain on flat or ambiguous images."""
    with Image.open(path) as original:
        image = original.convert('RGB').resize((80,80))
    def bucket(rgb): return tuple(min(255, (v//24)*24+12) for v in rgb)
    pixels = image.load()
    border = Counter(bucket(pixels[x,y]) for x in range(80) for y in range(80)
                     if x<8 or y<8 or x>=72 or y>=72)
    backgrounds = {rgb for rgb,n in border.items() if n/2304 > .15}
    alpha = mask.resize((80,80)).convert('L') if mask is not None else None
    choices=[]
    for x in range(12,68):
        for y in range(12,68):
            rgb=pixels[x,y];key=bucket(rgb)
            if alpha is not None and alpha.getpixel((x,y))<128: continue
            if alpha is None and key in backgrounds: continue
            _, saturation, value=colorsys.rgb_to_hsv(*(v/255 for v in rgb))
            if saturation>.2 and .12<value<.96: choices.append(key)
    if len(choices)<160: return None
    color,count=Counter(choices).most_common(1)[0]
    if count/len(choices)<.15: return None
    return '#'+''.join(f'{v:02x}' for v in color)


def pack_layers(pack, shots, manifest, existing, accent='#e4c081'):
    if pack not in PACKS: raise ValueError('Motion pack must be tech, editorial or pop')
    by_id={row['shot_id']:row.get('plan') or {} for row in manifest.get('shots',[])}
    result=[]
    for shot in shots:
        if shot.duration<.75 or by_id.get(shot.id,{}).get('story',{}).get('protect_action') is True:
            continue
        if any(row.get('shot_id')==shot.id for row in existing): continue
        base={'type':'vector','shot_id':shot.id,'scene':'style-pack','design':pack,'color':accent,
              'start':'12%','end':'85%','animation':'draw','out':'fade','sync':'onset'}
        if pack=='tech':
            result.extend([{**base,'shape':'line','at':[.12,.72],'to':[.4,.72]},
                           {**base,'shape':'dot','at':[.12,.72],'radius':.005}])
        elif pack=='editorial':
            result.append({**base,'shape':'line','at':[.15,.74],'to':[.38,.74],'opacity':.55})
        else:
            result.append({**base,'shape':'ring','at':[.8,.7],'radius':.06,'thickness':.005,'in_time':.12})
        if len(existing)+len(result)>118: break
    return result[:max(0,120-len(existing))]
