"""Named creative intent; numeric legacy settings remain compatible with saved jobs."""

def level(percent, names):
    return names[0] if percent < 34 else names[1] if percent < 67 else names[2]


def canonical(percent):
    return level(percent,(0,50,85))


# What each remix strategy holds fixed, so the structure slider is not the only word on it.
STRATEGIES = ('preserve', 'creative', 'transfer')


def strategy_values(settings):
    """Workflow values a remix strategy sets over the sliders; nothing when none is chosen."""
    if settings.remix_strategy == 'preserve':  # same cuts and durations, same subject: only the look changes
        return {'pose_strength': 1.0, 'reference_fidelity': 'strict', 'creative_freedom': 'faithful'}
    if settings.remix_strategy == 'transfer':  # the motion of the source carries another subject
        return {'pose_strength': 1.0, 'reference_fidelity': 'balanced', 'creative_freedom': 'free', 'force_pose': True}
    if settings.remix_strategy == 'creative':  # the source is an inspiration: staging and cuts may change
        return {'pose_strength': 0.4, 'reference_fidelity': 'loose', 'creative_freedom': 'free'}
    return {}


def direction(settings):
    fidelity=level(settings.structure,('flexible','balanced','strict'))
    freedom=level(settings.creativity,('faithful','balanced','bold'))
    return (f'Creative choices for this new video: reference fidelity {fidelity}; creative freedom {freedom}. '
            'Fidelity concerns reference composition, setting and visual treatment; preserve subject identity, outfit and product design unless explicitly changed in the brief. '
            'Flexible allows reinterpretation of framing/background, balanced adapts the reference, strict retains its relevant visual choices. '
            'Faithful develops only the stated idea, balanced adds compatible details, bold proposes surprising but compatible staging, viewpoints and visual devices. '
            'Neither choice changes the requested narrative, shot/cut count, music genre or explicit exclusions. '
            'Camera moves to draw from, one per shot and never the same twice in a row: slow push-in, pull-back reveal, orbit left or right, lateral track, whip pan, handheld follow, tilt-up from the feet, crane up or down, rack focus, dolly zoom, top-down drift, low-angle track. '
            'A move may change during the take (start wide and end close, or the reverse); a hold needs a reason in the brief. '
            'Unless the brief names one place or a fixed camera, change the place, the distance and the camera movement from one shot to the next, and move the subject inside the frame: '
            'a reference picture fixes who the subject is, not where every shot happens, and no two shots may share the same background, framing and pose. '
            'Without a visual reference, follow the written brief and do not invent a supplied reference.')
