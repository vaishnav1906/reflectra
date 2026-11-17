"""Renders the PDF portrait for the made-up demo person and saves a preview strip of
three pages for the README (docs/media/screenshots/16-pdf.png).

    .venv/Scripts/python scripts/media/pdf_preview.py      (needs pymupdf and ffmpeg)
"""

import math
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.persona_report_service import ReportData, TraitReading, render_report  # noqa: E402

now = datetime.now(timezone.utc)
day = lambda n: (now - timedelta(days=n)).date().isoformat()  # noqa: E731

series = []
for i, n in enumerate([181, 156, 131, 110, 92, 77, 63, 48, 35, 23, 12, 4, 0]):
    t = i / 12
    wobble = lambda k: math.sin(i * 1.7 + k) * 0.05 * (1 - t)  # noqa: E731
    series.append({
        "date": day(n),
        "communication_style": 0.5 + (0.34 - 0.5) * t + wobble(1),
        "emotional_expressiveness": 0.5 + (0.71 - 0.5) * t + wobble(2),
        "decision_framing": 0.5 + (0.44 - 0.5) * t + wobble(3),
        "reflection_depth": 0.5 + (0.77 - 0.5) * t + wobble(4),
    })

data = ReportData(
    name="Maya",
    generated_at=now,
    first_date=day(199),
    last_date=day(0),
    active_days=58,
    user_messages=412,
    conversations=63,
    longest_streak=4,
    busiest_day={"date": day(92), "user_messages": 31},
    traits=[
        TraitReading("communication_style", 0.34, 0.66, 141),
        TraitReading("emotional_expressiveness", 0.71, 0.64, 102),
        TraitReading("decision_framing", 0.44, 0.52, 88),
        TraitReading("reflection_depth", 0.77, 0.69, 77),
    ],
    trait_series=series,
    milestones=[
        {"date": day(18), "kind": "trait", "text": "Your reflection depth settled on the deep side (now 77/100)."},
        {"date": day(46), "kind": "import", "text": "Imported 420 of your WhatsApp messages."},
        {"date": day(199), "kind": "start", "text": "Your first conversation with Reflectra."},
    ],
    reflections=[
        {
            "title": "Deadlines are when you finally start",
            "insight": "You plan early and mean it, but the real work only begins once the date feels close.",
            "theme": "work", "confidence": 0.78, "feedback": "agree",
            "evidence": [
                {"quote": "i had three weeks for this model and i started it last night", "date": day(41)},
                {"quote": "why do i only start working when it's basically too late", "date": day(9)},
            ],
        },
        {
            "title": "Running resets your head",
            "insight": "On days you run before class you describe yourself as calmer and more focused.",
            "theme": "health", "confidence": 0.69,
            "evidence": [
                {"quote": "ran before studio and honestly my head is so much clearer", "date": day(30)},
                {"quote": "the run this morning made the whole day feel lighter", "date": day(3)},
            ],
        },
    ],
    reflections_read=160,
    hour_histogram=[14, 9, 4, 1, 0, 0, 2, 9, 12, 7, 6, 8, 10, 7, 6, 9, 11, 13, 15, 18, 24, 31, 37, 29],
    weekday_histogram=[58, 61, 49, 66, 44, 52, 82],
    voice={"messages": 160, "median_words": 11, "longest_words": 94, "lowercase_share": 0.83, "question_share": 0.22, "emoji_share": 0.08, "no_period_share": 0.71, "abbreviations": [("lol", 22), ("ngl", 14), ("rn", 9)], "phrases": ["small win"]},
    trait_feedback={"communication_style": {"verdict": "agree"}},
    feedback={"replies": {"reflection": {"up": 18, "down": 3}, "mirror": {"up": 7, "down": 2}}, "reasons": [{"reason": "too_long", "count": 2}], "traits": {"agree": 1, "disagree": 0}, "reflections": {"agree": 1, "disagree": 0}},
    life_facts=[
        {"kind": "about", "text": "Final-year architecture student in Bengaluru", "quote": "final year of arch and it's eating me alive", "pinned": True},
        {"kind": "situation", "text": "Thesis submission is due on 12 December", "quote": "thesis is due dec 12 and i'm not ready", "pinned": True},
        {"kind": "goal", "text": "Wants a studio job in Mumbai after graduating", "quote": None},
        {"kind": "routine", "text": "Runs before morning classes", "quote": None},
    ],
    loose_ends=[{"what": "Email Prof. Iyer about the thesis extension", "due": day(-1)}],
    people=[
        {"name": "Ananya", "relationship": "best friend", "description": "Known her since school. Brutally honest, the first person I call when I'm stuck.", "mention_count": 23, "last_mentioned_at": now.isoformat()},
        {"name": "Mom", "relationship": "mother", "description": "Worries a lot, asks about placements every call. Means well.", "mention_count": 15, "last_mentioned_at": now.isoformat()},
        {"name": "Prof. Iyer", "relationship": "thesis guide", "description": "Strict but fair. Likes bold concepts, hates late submissions.", "mention_count": 11},
    ],
    voice_import={"samples": 420, "format": "whatsapp"},
)

if __name__ == "__main__":
    import pymupdf

    out = ROOT / "docs" / "media" / "screenshots" / "16-pdf.webp"
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "maya.pdf"
        pdf.write_bytes(render_report(data))
        doc = pymupdf.open(pdf)
        pages = [0, 1, 3]  # cover, at a glance, your life + people
        files = []
        for n in pages:
            path = Path(tmp) / f"p{n}.png"
            doc[n].get_pixmap(dpi=110).save(path)
            files.append(str(path))
        doc.close()
        inputs = sum((["-i", f] for f in files), [])
        pad = "pad=iw+40:ih+40:20:20:color=0x0b0b12"
        graph = ";".join(f"[{i}:v]{pad}[p{i}]" for i in range(len(files))) + ";" + "".join(f"[p{i}]" for i in range(len(files))) + f"hstack=inputs={len(files)}"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-c:v", "libwebp", "-quality", "88", str(out)], check=True)
    print("saved", out)
