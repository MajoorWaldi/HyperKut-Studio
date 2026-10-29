"""Named creative intent; numeric legacy settings remain compatible with saved jobs."""

def level(percent, names):
    return names[0] if percent < 34 else names[1] if percent < 67 else names[2]


def canonical(percent):
    return level(percent,(0,50,85))


def direction(settings):
    fidelity=level(settings.structure,('flexible','balanced','strict'))
    freedom=level(settings.creativity,('faithful','balanced','bold'))
    return (f'Creative choices for this new video: reference fidelity {fidelity}; creative freedom {freedom}. '
            'Fidelity concerns reference composition, setting and visual treatment; preserve subject identity, outfit and product design unless explicitly changed in the brief. '
            'Flexible allows reinterpretation of framing/background, balanced adapts the reference, strict retains its relevant visual choices. '
            'Faithful develops only the stated idea, balanced adds compatible details, bold proposes surprising but compatible staging, viewpoints and visual devices. '
            'Neither choice changes the requested narrative, shot/cut count, music genre or explicit exclusions. '
            'Without a visual reference, follow the written brief and do not invent a supplied reference.')
