"""Source bounds for slip editing; output duration and existing cut pattern stay fixed."""
import math


def trim_bounds(shot, revision, style, fps):
    actual = float(revision.get('actual_duration_seconds', 0))
    target = round(float(shot.get('target_duration_seconds', 0)) * fps) / fps
    start = float(revision.get('source_start_seconds', 0))
    if not math.isfinite(actual) or actual <= 0 or target <= 0:
        return {'duration':0.0,'start':0.0,'window':0.0,'max_start':0.0,'step':1/fps}
    if revision.get('duration_policy') == 'keep_generated':
        extent = actual
    else:
        fx = (shot.get('plan') or {}).get('fx') if style.get('effects', True) else None
        extent = min(actual, target)
        if fx:
            subs = (fx.get('sub_cuts') if style.get('sub_cuts', True) else None) or [None]
            total = round(target * fps)
            subs = subs[:max(total, 1)]
            weights = [row['frames'] for row in subs] if subs[0] else [total]
            raw = [total * weight / sum(weights) for weight in weights]
            frames = [int(value) for value in raw]
            for i in sorted(range(len(raw)), key=lambda i: raw[i]-int(raw[i]), reverse=True)[:total-sum(frames)]:
                frames[i] += 1
            # Same minimum-one-frame distribution used by the assembler.
            for i in range(len(frames)):
                while frames[i] < 1:
                    donor = max(range(len(frames)), key=lambda j: frames[j])
                    if frames[donor] <= 1: break
                    frames[donor] -= 1; frames[i] += 1
            extent, cursor = 0.0, 0.0
            for sub, count in zip(subs, frames):
                spec = {k:fx[k] for k in ('speed','speed_ramp') if k in fx}
                if sub:
                    if 'speed' in sub: spec = {'speed':sub['speed']}
                    if 'speed_ramp' in sub: spec = {'speed_ramp':sub['speed_ramp']}
                speed = sum(spec['speed_ramp'])/2 if 'speed_ramp' in spec else spec.get('speed',1)
                need = count / fps * speed
                at = (sub or {}).get('start', cursor)
                cursor = at + need
                at = max(0.0,min(at,actual-need))
                extent = max(extent,min(actual,at+need))
    maximum = math.floor(max(0,actual-extent)*fps+1e-6)/fps
    return {'duration':actual,'start':start,'window':extent,'max_start':maximum,'step':1/fps}
