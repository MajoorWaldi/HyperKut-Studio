"""Kinetic lyrics: the words the transcription kept in the project, as the `kinetic_lyrics` layer of the finishing pass (one word at a time, a bigger one on the beats)."""
import json
from pathlib import Path

MAX_LAYERS = 120  # what the finishing pass takes; one layer per word, so the user's own layers keep their room
KEPT = "music/lyrics.json"
TEMPLATE = "kinetic_lyrics"


def lyrics_layer(project: Path, duration: float, rows: list, configured: list = ()) -> dict | None:
    """The layer for the words of the project, or None: no words, one already asked for by the user (`configured`), or no room left in `rows`, the layers of the pass."""
    if any(isinstance(row, dict) and row.get("template") == TEMPLATE for row in configured):
        return None
    try:
        words = json.loads((project / KEPT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    words = [{"word": w["word"], "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3), **({"accent": True} if w.get("accent") else {})}
             for w in words if isinstance(w, dict) and isinstance(w.get("word"), str) and w["word"].strip() and float(w["start"]) < duration]
    room = MAX_LAYERS - 4 - len(rows)  # a few layers stay free for the templates that expand into several
    words = words[:max(room, 0)]
    if not words:
        return None
    return {"template": TEMPLATE, "start": 0, "end": round(duration, 3), "words": words, "position": "bottom"}
