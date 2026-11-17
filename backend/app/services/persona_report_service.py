"""Persona report (PDF): a portrait of the user built only from stored data.

Two halves, so the rendering can be tested without a database:
  collect_report_data(db, user_id) -> ReportData   (queries)
  render_report(data) -> bytes                      (pure drawing, ReportLab)

What goes in, and where it comes from:
  - Trait readings + confidence ......... user_persona_metrics
  - How the traits moved ................ persona_snapshots (one point per day)
  - What keeps coming up ................ evidence-backed reflections (with the user's quotes)
  - Rhythm (when, how often) ............ message timestamps
  - Voice (how they write) .............. their own messages + linguistic fingerprint
  - How Reflectra adapts ................ derived from the trait readings

ReportLab is pure Python, so export works on Windows, Linux and serverless without
system libraries (the old WeasyPrint/matplotlib stack needed GTK and failed to import).
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Dict, List, Optional
from uuid import UUID

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas as pdfcanvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import TRAIT_LIST

# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------

TRAIT_META = {
    "communication_style": {
        "name": "Communication",
        "low": "Concise",
        "high": "Elaborate",
        "read_low": "You get to the point. Your messages are short and you rarely pad them.",
        "read_mid": "You flex: brief when it's simple, detailed when it matters.",
        "read_high": "You think out loud in full, giving context and detail before the point.",
        "tag_low": "gets to the point",
        "tag_high": "thinks out loud in full",
        "adapt_low": "Keeps its replies short, because you do.",
        "adapt_high": "Gives you fuller answers and room to elaborate.",
    },
    "emotional_expressiveness": {
        "name": "Emotional expressiveness",
        "low": "Reserved",
        "high": "Open",
        "read_low": "You keep feelings low-key and tend to report the facts first.",
        "read_mid": "You share feelings when something big is going on, and otherwise stay even.",
        "read_high": "You say how you feel, plainly and often.",
        "tag_low": "keeps feelings low-key",
        "tag_high": "open about feelings",
        "adapt_low": "Stays matter-of-fact unless you open the door to feelings.",
        "adapt_high": "Meets feelings head-on instead of steering around them.",
    },
    "decision_framing": {
        "name": "Decision framing",
        "low": "Hesitant",
        "high": "Decisive",
        "read_low": "You weigh things for a while and often hedge before committing.",
        "read_mid": "You are quick on small calls and careful on big ones.",
        "read_high": "You decide fast and say it flatly.",
        "tag_low": "weighs things before committing",
        "tag_high": "decides fast",
        "adapt_low": "Doesn't rush you to a verdict; helps you narrow the options.",
        "adapt_high": "Skips the hedging and gets to the call with you.",
    },
    "reflection_depth": {
        "name": "Reflection depth",
        "low": "Surface",
        "high": "Deep",
        "read_low": "You stay practical: what happened, and what's next.",
        "read_mid": "You reflect after setbacks without dwelling on them.",
        "read_high": "You dig for the why behind what you do.",
        "tag_low": "stays practical",
        "tag_high": "digs for the why",
        "adapt_low": "Keeps things practical rather than analytical.",
        "adapt_high": "Goes after the why with you, not just the what.",
    },
}

LOW, HIGH = 0.38, 0.62


@dataclass
class TraitReading:
    key: str
    score: float
    confidence: float
    evidence_count: int


@dataclass
class ReportData:
    name: str
    generated_at: datetime
    first_date: Optional[str] = None
    last_date: Optional[str] = None
    active_days: int = 0
    user_messages: int = 0
    conversations: int = 0
    longest_streak: int = 0
    busiest_day: Optional[Dict[str, object]] = None
    conversations_by_mode: Dict[str, int] = field(default_factory=dict)
    traits: List[TraitReading] = field(default_factory=list)
    trait_series: List[Dict[str, object]] = field(default_factory=list)
    milestones: List[Dict[str, object]] = field(default_factory=list)
    reflections: List[Dict[str, object]] = field(default_factory=list)
    reflections_read: int = 0
    hour_histogram: List[int] = field(default_factory=lambda: [0] * 24)
    weekday_histogram: List[int] = field(default_factory=lambda: [0] * 7)
    voice: Dict[str, object] = field(default_factory=dict)


def side(score: float) -> str:
    return "low" if score <= LOW else "high" if score >= HIGH else "mid"


def confidence_label(confidence: float) -> str:
    if confidence < 0.3:
        return "an early guess"
    if confidence < 0.6:
        return "taking shape"
    return "well established"


def headline(traits: List[TraitReading]) -> str:
    """One-line portrait from the two most distinctive, reasonably certain traits."""
    distinctive = sorted(
        (t for t in traits if side(t.score) != "mid" and t.confidence >= 0.3),
        key=lambda t: abs(t.score - 0.5) * t.confidence,
        reverse=True,
    )[:2]
    if not distinctive:
        return "Still getting to know you."
    tags = [TRAIT_META[t.key][f"tag_{side(t.score)}"] for t in distinctive]
    text = tags[0] if len(tags) == 1 else f"{tags[0]}, and {tags[1]}"
    return text[0].upper() + text[1:] + "."


def adaptation_lines(traits: List[TraitReading], voice: Dict[str, object]) -> List[str]:
    lines = []
    for t in traits:
        s = side(t.score)
        if s != "mid" and t.confidence >= 0.3:
            lines.append(TRAIT_META[t.key][f"adapt_{s}"])
    if voice.get("lowercase_share", 0) >= 0.7:
        lines.append("In Mirror mode it writes in lowercase, the way you do.")
    if voice.get("messages", 0) >= 20 and voice.get("emoji_share", 0) == 0:
        lines.append("It leaves emojis out, since you don't use them.")
    elif voice.get("emoji_share", 0) >= 0.25:
        lines.append("It uses the emojis you use, about as often as you do.")
    return lines or ["Nothing yet. It needs more conversation before it changes how it talks to you."]


def voice_profile(texts: List[str], fingerprint_abbreviations: Dict[str, int], phrases: List[str]) -> Dict[str, object]:
    cleaned = [t.strip() for t in texts if t and t.strip()]
    if not cleaned:
        return {"messages": 0}
    lengths = [len(t.split()) for t in cleaned]
    emoji = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
    return {
        "messages": len(cleaned),
        "median_words": int(median(lengths)),
        "longest_words": max(lengths),
        "lowercase_share": sum(1 for t in cleaned if not re.search(r"[A-Z]", t)) / len(cleaned),
        "question_share": sum(1 for t in cleaned if "?" in t) / len(cleaned),
        "emoji_share": sum(1 for t in cleaned if emoji.search(t)) / len(cleaned),
        "no_period_share": sum(1 for t in cleaned if not re.search(r"[.!?]\s*$", t)) / len(cleaned),
        "abbreviations": sorted(fingerprint_abbreviations.items(), key=lambda kv: kv[1], reverse=True)[:6],
        "phrases": phrases[:6],
    }


async def collect_report_data(db: AsyncSession, user_id: UUID, tz_offset_minutes: int = 0) -> ReportData:
    from app.db.models import LinguisticFingerprint, Message, User, UserPersonaMetric
    from app.services.reflection_service import get_reflections
    from app.services.timeline_service import build_timeline

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    name = (user.display_name or "").strip() if user else ""
    name = (name.split()[0] if name else "You")
    name = name[0].upper() + name[1:]

    timeline = await build_timeline(db, user_id, None, tz_offset_minutes)
    summary = timeline["summary"]

    metrics = (await db.execute(select(UserPersonaMetric).where(UserPersonaMetric.user_id == user_id))).scalars().all()
    by_name = {m.trait_name: m for m in metrics}
    traits = [
        TraitReading(key, float(by_name[key].score), float(by_name[key].confidence), int(by_name[key].evidence_count or 0))
        for key in TRAIT_LIST
        if key in by_name
    ]

    reflections_state = await get_reflections(db, user_id)

    rows = (
        await db.execute(
            select(Message.content, Message.created_at)
            .where(Message.user_id == user_id, Message.role == "user")
            .order_by(Message.created_at.desc())
            .limit(4000)
        )
    ).all()
    offset = timedelta(minutes=max(-840, min(840, tz_offset_minutes)))
    hours, weekdays = [0] * 24, [0] * 7
    for _, created_at in rows:
        if created_at is None:
            continue
        local = (created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)).astimezone(timezone.utc) + offset
        hours[local.hour] += 1
        weekdays[local.weekday()] += 1

    fingerprint = (
        await db.execute(select(LinguisticFingerprint).where(LinguisticFingerprint.user_id == user_id))
    ).scalar_one_or_none()
    abbreviations = dict(fingerprint.abbreviation_stats or {}) if fingerprint else {}
    phrases = list(fingerprint.characteristic_phrases or []) if fingerprint else []

    return ReportData(
        name=name,
        generated_at=datetime.now(timezone.utc) + offset,
        first_date=summary["first_date"],
        last_date=summary["last_date"],
        active_days=summary["active_days"],
        user_messages=summary["user_messages"],
        conversations=summary["conversations"],
        longest_streak=summary["longest_streak"],
        busiest_day=summary["busiest_day"],
        conversations_by_mode=summary["conversations_by_mode"],
        traits=traits,
        trait_series=timeline["trait_series"],
        milestones=timeline["milestones"],
        reflections=reflections_state["reflections"],
        reflections_read=reflections_state["status"]["messages_read"],
        hour_histogram=hours,
        weekday_histogram=weekdays,
        voice=voice_profile([content for content, _ in rows], abbreviations, phrases),
    )


async def build_persona_report_pdf(db: AsyncSession, user_id: UUID, tz_offset_minutes: int = 0) -> bytes:
    return render_report(await collect_report_data(db, user_id, tz_offset_minutes))


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------

PAGE_W, PAGE_H = A4
MARGIN = 54
CONTENT_W = PAGE_W - 2 * MARGIN

INK = HexColor("#15141C")
SOFT = HexColor("#5E5B6B")
FAINT = HexColor("#A7A4B3")
RULE = HexColor("#E6E3EC")
PAPER = HexColor("#FBFAF7")
NIGHT = HexColor("#0B0B12")
VIOLET = HexColor("#7C6BF2")
CYAN = HexColor("#1FA7BD")
PEACH = HexColor("#EE8E63")
ROSE = HexColor("#D9578C")
TRAIT_COLORS = {
    "communication_style": CYAN,
    "emotional_expressiveness": PEACH,
    "decision_framing": VIOLET,
    "reflection_depth": ROSE,
}

SERIF, SERIF_I, SANS, SANS_B, MONO = "Times-Roman", "Times-Italic", "Helvetica", "Helvetica-Bold", "Courier"

_REPLACEMENTS = {
    "’": "'", "‘": "'", "“": '"', "”": '"', "—": ", ", "–": "-",
    "…": "...", " ": " ", "→": "->", "↔": "<->",
}


def pdf_safe(text: str) -> str:
    """The built-in PDF fonts cover Latin text only: normalise punctuation, drop the rest."""
    out = str(text or "")
    for src, dst in _REPLACEMENTS.items():
        out = out.replace(src, dst)
    out = out.encode("cp1252", "ignore").decode("cp1252")
    return re.sub(r"\s+", " ", out).strip()


def printable(text: str) -> bool:
    """False when too much of the text would be lost (e.g. a quote in another script)."""
    original = re.sub(r"\s+", "", str(text or ""))
    return bool(original) and len(re.sub(r"\s+", "", pdf_safe(text))) >= 0.85 * len(original)


def _mix(a: Color, b: Color, t: float) -> Color:
    return Color(a.red + (b.red - a.red) * t, a.green + (b.green - a.green) * t, a.blue + (b.blue - a.blue) * t)


def _iris(t: float) -> Color:
    stops = [HexColor("#C4BAFF"), HexColor("#96E8F5"), HexColor("#FFCDB0"), HexColor("#C4BAFF")]
    x = (t % 1) * 3
    i = min(int(x), 2)
    return _mix(stops[i], stops[i + 1], x - i)


def _fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(iso)
        return f"{d.day} {d.strftime('%b %Y')}"
    except ValueError:
        return iso


class _Doc:
    """Thin layout helper around a ReportLab canvas: a cursor, wrapped text, page breaks."""

    def __init__(self, data: ReportData):
        self.buffer = io.BytesIO()
        self.c = pdfcanvas.Canvas(self.buffer, pagesize=A4)
        self.c.setTitle(pdf_safe(f"Reflectra: a portrait of {data.name}"))
        self.c.setAuthor("Reflectra")
        self.data = data
        self.page = 0
        self.y = PAGE_H - MARGIN

    # -- pages --
    def new_page(self, section: str = "") -> None:
        if self.page:
            self.c.showPage()
        self.page += 1
        self.c.setFillColor(PAPER)
        self.c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        self.c.setFont(MONO, 7.5)
        self.c.setFillColor(FAINT)
        self.c.drawString(MARGIN, PAGE_H - 34, "REFLECTRA  /  A PORTRAIT OF " + pdf_safe(self.data.name).upper())
        self.c.drawRightString(PAGE_W - MARGIN, PAGE_H - 34, section.upper())
        self.c.drawString(MARGIN, 30, f"Generated {self.data.generated_at.strftime('%d %b %Y')}. Built only from your own conversations.")
        self.c.drawRightString(PAGE_W - MARGIN, 30, str(self.page))
        self.y = PAGE_H - 78

    def ensure(self, height: float, section: str = "") -> None:
        if self.y - height < 56:
            self.new_page(section)

    # -- text --
    def text(self, text: str, font: str = SANS, size: float = 10, color: Color = INK, x: float = MARGIN,
             width: float = CONTENT_W, leading: Optional[float] = None, gap: float = 0) -> None:
        leading = leading or size * 1.42
        for line in simpleSplit(pdf_safe(text), font, size, width):
            self.c.setFont(font, size)
            self.c.setFillColor(color)
            self.c.drawString(x, self.y - size, line)
            self.y -= leading
        self.y -= gap

    def eyebrow(self, text: str) -> None:
        self.c.setFont(MONO, 7.5)
        self.c.setFillColor(VIOLET)
        self.c.drawString(MARGIN, self.y - 7.5, pdf_safe(text).upper())
        self.y -= 18

    def heading(self, plain: str, italic: str = "", size: float = 27) -> None:
        self.c.setFont(SERIF, size)
        self.c.setFillColor(INK)
        self.c.drawString(MARGIN, self.y - size, pdf_safe(plain))
        if italic:
            x = MARGIN + self.c.stringWidth(pdf_safe(plain) + " ", SERIF, size)
            self.c.setFont(SERIF_I, size)
            self.c.setFillColor(VIOLET)
            self.c.drawString(x, self.y - size, pdf_safe(italic))
        self.y -= size * 1.5

    def rule(self, gap: float = 14) -> None:
        self.c.setStrokeColor(RULE)
        self.c.setLineWidth(0.6)
        self.c.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.y -= gap

    def finish(self) -> bytes:
        self.c.showPage()
        self.c.save()
        return self.buffer.getvalue()


def _cover(doc: _Doc) -> None:
    c, d = doc.c, doc.data
    doc.page += 1
    c.setFillColor(NIGHT)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    # Iridescent oval mirror: short strokes with a colour that travels round the rim.
    cx, cy, rx, ry = PAGE_W / 2, PAGE_H * 0.62, 118, 158
    c.setLineWidth(1.6)
    segments = 240
    for i in range(segments):
        a0, a1 = 2 * math.pi * i / segments, 2 * math.pi * (i + 1.4) / segments
        c.setStrokeColor(_iris(i / segments + 0.1))
        c.line(cx + rx * math.cos(a0), cy + ry * math.sin(a0), cx + rx * math.cos(a1), cy + ry * math.sin(a1))

    c.setFillColor(HexColor("#F3F1FA"))
    c.setFont(SERIF, 50)
    c.drawCentredString(cx, cy + 4, "Reflectra")
    c.setFont(MONO, 8)
    c.setFillColor(HexColor("#8D8AA0"))
    c.drawCentredString(cx, cy - 22, "A MIRROR FOR YOUR MIND")

    c.setFillColor(HexColor("#F3F1FA"))
    c.setFont(SERIF, 30)
    c.drawCentredString(cx, 262, "A portrait of")
    c.setFont(SERIF_I, 40)
    c.setFillColor(HexColor("#C4BAFF"))
    c.drawCentredString(cx, 218, pdf_safe(d.name))

    c.setFont(SANS, 10.5)
    c.setFillColor(HexColor("#B9B6C9"))
    c.drawCentredString(cx, 186, pdf_safe(headline(d.traits)))

    # Numbers strip
    stats = [
        (str(d.user_messages), "messages"),
        (str(d.conversations), "conversations"),
        (str(d.active_days), "days talked"),
        (str(d.longest_streak), "day streak"),
    ]
    col = CONTENT_W / len(stats)
    for i, (value, label) in enumerate(stats):
        x = MARGIN + col * i + col / 2
        c.setFont(SERIF, 24)
        c.setFillColor(HexColor("#F3F1FA"))
        c.drawCentredString(x, 118, value)
        c.setFont(MONO, 7)
        c.setFillColor(HexColor("#8D8AA0"))
        c.drawCentredString(x, 102, label.upper())

    c.setFont(MONO, 7.5)
    c.setFillColor(HexColor("#6F6C80"))
    period = f"{_fmt_date(d.first_date)} to {_fmt_date(d.last_date)}" if d.first_date else "No conversations yet"
    c.drawCentredString(cx, 58, pdf_safe(f"{period}   /   generated {d.generated_at.strftime('%d %b %Y')}").upper())


def _trait_bar(doc: _Doc, trait: TraitReading) -> None:
    c = doc.c
    meta = TRAIT_META[trait.key]
    color = TRAIT_COLORS[trait.key]
    doc.ensure(96, "At a glance")
    top = doc.y

    c.setFont(SANS_B, 11)
    c.setFillColor(INK)
    c.drawString(MARGIN, top - 11, meta["name"])
    c.setFont(SERIF, 22)
    c.setFillColor(color)
    c.drawRightString(PAGE_W - MARGIN, top - 16, f"{round(trait.score * 100)}")
    c.setFont(MONO, 7)
    c.setFillColor(FAINT)
    c.drawRightString(PAGE_W - MARGIN - 30, top - 9, "OUT OF 100")

    # Track with an uncertainty band: the wider the band, the less sure Reflectra is.
    track_y = top - 36
    c.setStrokeColor(RULE)
    c.setLineWidth(5)
    c.setLineCap(1)
    c.line(MARGIN, track_y, PAGE_W - MARGIN, track_y)
    x = MARGIN + CONTENT_W * max(0.0, min(1.0, trait.score))
    band = CONTENT_W * 0.22 * (1 - max(0.0, min(1.0, trait.confidence)))
    c.setStrokeColor(Color(color.red, color.green, color.blue, alpha=0.28))
    c.line(max(MARGIN, x - band), track_y, min(PAGE_W - MARGIN, x + band), track_y)
    c.setFillColor(color)
    c.circle(x, track_y, 5.5, stroke=0, fill=1)
    c.setFillColor(PAPER)
    c.circle(x, track_y, 2, stroke=0, fill=1)
    c.setLineCap(0)

    c.setFont(MONO, 7)
    c.setFillColor(FAINT)
    c.drawString(MARGIN, track_y - 15, meta["low"].upper())
    c.drawRightString(PAGE_W - MARGIN, track_y - 15, meta["high"].upper())
    c.drawCentredString(PAGE_W / 2, track_y - 15, "50")

    doc.y = track_y - 26
    doc.text(meta[f"read_{side(trait.score)}"], SANS, 10, INK)
    doc.text(
        f"{round(trait.confidence * 100)}% sure ({confidence_label(trait.confidence)}), from {trait.evidence_count} signals in your messages.",
        SANS, 8.5, SOFT, gap=14,
    )


def _glance(doc: _Doc) -> None:
    d = doc.data
    doc.new_page("At a glance")
    doc.eyebrow("01 / At a glance")
    doc.heading("How you", "come across")
    doc.text(
        "Four things Reflectra measures from the way you write to it. Each score moves a little with every "
        "message, so it reflects a pattern, not a single day. The shaded band shows how unsure it still is.",
        SANS, 10, SOFT, gap=16,
    )
    if not d.traits:
        doc.text("Not enough conversation yet to read any of these.", SERIF_I, 14, SOFT)
        return
    for trait in d.traits:
        _trait_bar(doc, trait)

    unsure = [TRAIT_META[t.key]["name"].lower() for t in d.traits if t.confidence < 0.5]
    doc.ensure(50, "At a glance")
    doc.rule()
    doc.text(
        "Still unsure about: " + (", ".join(unsure) + "." if unsure else "nothing major. All four readings are past the halfway mark in confidence."),
        SANS, 9, SOFT,
    )


def _reflections(doc: _Doc) -> None:
    d = doc.data
    section = "What keeps coming up"
    doc.new_page(section)
    doc.eyebrow("02 / What keeps coming up")
    doc.heading("Patterns in", "your own words")
    if not d.reflections:
        doc.text(
            "No reflections yet. Reflectra writes these once it has seen the same thing come up at least twice "
            "in what you've told it. Open the Reflections page in the app to generate them.",
            SANS, 10.5, SOFT,
        )
        return
    doc.text(
        f"Each pattern below showed up on at least two separate occasions in your last {d.reflections_read} messages. "
        "The quotes are yours, word for word.",
        SANS, 10, SOFT, gap=14,
    )
    for index, reflection in enumerate(d.reflections, start=1):
        quotes = [e for e in reflection.get("evidence", []) if printable(str(e.get("quote", "")))]
        insight_lines = simpleSplit(pdf_safe(reflection.get("insight", "")), SANS, 10, CONTENT_W - 30)
        needed = 44 + len(insight_lines) * 14.2 + sum(
            len(simpleSplit(pdf_safe(str(q["quote"])), SERIF_I, 10.5, CONTENT_W - 62)) * 14 + 16 for q in quotes
        )
        doc.ensure(min(needed, 420), section)

        doc.c.setFont(SERIF, 30)
        doc.c.setFillColor(Color(VIOLET.red, VIOLET.green, VIOLET.blue, alpha=0.35))
        doc.c.drawString(MARGIN, doc.y - 26, f"{index:02d}")
        top = doc.y
        doc.text(reflection.get("title", ""), SERIF, 17, INK, x=MARGIN + 44, width=CONTENT_W - 44, leading=20)
        doc.c.setFont(MONO, 7)
        doc.c.setFillColor(FAINT)
        confidence = reflection.get("confidence") or 0
        doc.c.drawString(MARGIN + 44, doc.y - 8, pdf_safe(f"{reflection.get('theme', 'other')}  /  seen {len(reflection.get('evidence', []))} times  /  {round(confidence * 100)}% sure").upper())
        doc.y = min(doc.y - 20, top - 44)
        doc.text(reflection.get("insight", ""), SANS, 10, INK, x=MARGIN + 44, width=CONTENT_W - 44, gap=6)
        for quote in quotes:
            start = doc.y
            doc.text(f'"{quote["quote"]}"', SERIF_I, 10.5, SOFT, x=MARGIN + 58, width=CONTENT_W - 62, leading=14)
            doc.c.setFont(MONO, 6.5)
            doc.c.setFillColor(FAINT)
            doc.c.drawString(MARGIN + 58, doc.y - 8, pdf_safe(_fmt_date(quote.get("date"))).upper())
            doc.c.setStrokeColor(PEACH)
            doc.c.setLineWidth(1.4)
            doc.c.line(MARGIN + 48, start - 2, MARGIN + 48, doc.y - 9)
            doc.y -= 16
        doc.y -= 8
        if index < len(d.reflections):
            doc.rule(16)


def _trajectory_chart(doc: _Doc, height: float = 150) -> None:
    c, series = doc.c, doc.data.trait_series
    left, right, bottom = MARGIN + 22, PAGE_W - MARGIN, doc.y - height
    width = right - left

    c.setFont(MONO, 6.5)
    for value in (0, 50, 100):
        y = bottom + height * value / 100
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(left, y, right, y)
        c.setFillColor(FAINT)
        c.drawRightString(left - 5, y - 2, str(value))

    # Evenly spaced by day talked: long silences would otherwise squash the chart.
    xs = [left + width * (i / max(len(series) - 1, 1)) for i in range(len(series))]
    for trait in TRAIT_LIST:
        points = [(x, bottom + height * float(p[trait])) for x, p in zip(xs, series) if p.get(trait) is not None]
        if len(points) < 2:
            continue
        c.setStrokeColor(TRAIT_COLORS[trait])
        c.setLineWidth(1.6)
        c.setLineJoin(1)
        path = c.beginPath()
        path.moveTo(*points[0])
        for point in points[1:]:
            path.lineTo(*point)
        c.drawPath(path, stroke=1, fill=0)
        c.setFillColor(TRAIT_COLORS[trait])
        c.circle(points[-1][0], points[-1][1], 2.4, stroke=0, fill=1)

    c.setFillColor(FAINT)
    c.drawString(left, bottom - 11, _fmt_date(str(series[0]["date"])).upper())
    c.drawRightString(right, bottom - 11, _fmt_date(str(series[-1]["date"])).upper())

    # Legend
    x = left
    y = bottom - 28
    for trait in TRAIT_LIST:
        c.setFillColor(TRAIT_COLORS[trait])
        c.circle(x + 3, y + 2.5, 3, stroke=0, fill=1)
        c.setFillColor(SOFT)
        c.setFont(SANS, 8)
        label = TRAIT_META[trait]["name"]
        c.drawString(x + 10, y, label)
        x += c.stringWidth(label, SANS, 8) + 28
    doc.y = y - 18


def _bars(doc: _Doc, values: List[int], labels: Dict[int, str], x: float, width: float, height: float, color: Color) -> None:
    c = doc.c
    peak = max(values) or 1
    gap = 2
    bar_w = (width - gap * (len(values) - 1)) / len(values)
    base = doc.y - height
    for i, value in enumerate(values):
        h = height * value / peak
        c.setFillColor(color if value == peak and value else Color(color.red, color.green, color.blue, alpha=0.35))
        c.roundRect(x + i * (bar_w + gap), base, bar_w, max(h, 0.8), 1, stroke=0, fill=1)
    c.setFont(MONO, 6.5)
    c.setFillColor(FAINT)
    for i, label in labels.items():
        c.drawCentredString(x + i * (bar_w + gap) + bar_w / 2, base - 10, label)


def _change_and_rhythm(doc: _Doc) -> None:
    d = doc.data
    section = "Over time"
    doc.new_page(section)
    doc.eyebrow("03 / Over time")
    doc.heading("How you've", "moved")
    if len(d.trait_series) >= 2:
        doc.text("Your four readings, one point for each day you talked (gaps between days are not shown). Early swings are normal: the first few messages count for a lot until a pattern forms.", SANS, 10, SOFT, gap=14)
        _trajectory_chart(doc)
    else:
        doc.text("This chart appears once you've talked on at least two different days.", SANS, 10, SOFT, gap=10)

    notable = [m for m in d.milestones if m.get("kind") in {"trait", "activity", "start", "import"}][:5]
    if notable:
        doc.ensure(30 + 18 * len(notable), section)
        for milestone in reversed(notable):
            doc.c.setFont(MONO, 7)
            doc.c.setFillColor(VIOLET)
            doc.c.drawString(MARGIN, doc.y - 8, pdf_safe(_fmt_date(str(milestone["date"]))).upper())
            doc.text(str(milestone["text"]), SANS, 9.5, INK, x=MARGIN + 86, width=CONTENT_W - 86, gap=4)

    doc.ensure(200, section)
    doc.y -= 10
    doc.rule(18)
    doc.eyebrow("When you talk")
    total = sum(d.hour_histogram)
    if not total:
        doc.text("No messages yet.", SANS, 10, SOFT)
        return
    peak_hour = max(range(24), key=lambda h: d.hour_histogram[h])
    late = sum(d.hour_histogram[h] for h in (22, 23, 0, 1, 2, 3)) / total
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    peak_day = max(range(7), key=lambda i: d.weekday_histogram[i])
    hour12 = f"{(peak_hour % 12) or 12} {'am' if peak_hour < 12 else 'pm'}"
    doc.text(
        f"You talk most around {hour12}, and {days[peak_day]} is your busiest day. "
        f"{round(late * 100)}% of your messages come between 10 pm and 4 am."
        + (f" Your biggest day was {_fmt_date(str(d.busiest_day['date']))}: {d.busiest_day['user_messages']} messages." if d.busiest_day else ""),
        SANS, 10, INK, gap=14,
    )
    half = (CONTENT_W - 30) * 0.68
    _bars(doc, d.hour_histogram, {0: "12A", 6: "6A", 12: "12P", 18: "6P", 23: "11P"}, MARGIN, half, 70, VIOLET)
    _bars(doc, d.weekday_histogram, {i: day[0] for i, day in enumerate(days)}, MARGIN + half + 30, CONTENT_W - half - 30, 70, PEACH)
    doc.y -= 96


def _voice_and_adaptation(doc: _Doc) -> None:
    d = doc.data
    section = "Your voice"
    doc.new_page(section)
    doc.eyebrow("04 / Your voice")
    doc.heading("How you", "write")
    voice = d.voice
    if voice.get("messages", 0) < 5:
        doc.text("Not enough messages yet to describe how you write.", SANS, 10, SOFT, gap=20)
    else:
        doc.text(f"Measured across your {voice['messages']} most recent messages. This is what Mirror mode copies.", SANS, 10, SOFT, gap=16)
        stats = [
            (str(voice["median_words"]), "words in a typical message"),
            (f"{round(voice['lowercase_share'] * 100)}%", "typed with no capitals"),
            (f"{round(voice['question_share'] * 100)}%", "contain a question"),
            (f"{round(voice['emoji_share'] * 100)}%", "contain an emoji"),
        ]
        col = CONTENT_W / 4
        for i, (value, label) in enumerate(stats):
            x = MARGIN + col * i
            doc.c.setFont(SERIF, 30)
            doc.c.setFillColor(INK)
            doc.c.drawString(x, doc.y - 30, value)
            doc.c.setFont(SANS, 8)
            doc.c.setFillColor(SOFT)
            for j, line in enumerate(simpleSplit(label, SANS, 8, col - 14)):
                doc.c.drawString(x, doc.y - 44 - j * 10, line)
        doc.y -= 78
        habits = [f"{word} ({count})" for word, count in voice.get("abbreviations", []) if count >= 2]
        if habits:
            doc.text("Shorthand you use: " + ", ".join(habits) + ".", SANS, 10, INK, gap=4)
        phrases = [p for p in voice.get("phrases", []) if printable(p)]
        if phrases:
            doc.text("Phrases that recur: " + ", ".join(f'"{p}"' for p in phrases) + ".", SANS, 10, INK, gap=4)
        doc.y -= 12

    doc.rule(18)
    doc.eyebrow("Because of all this")
    doc.heading("How Reflectra", "talks to you", size=22)
    for line in adaptation_lines(d.traits, voice):
        doc.ensure(24, section)
        doc.c.setFillColor(CYAN)
        doc.c.circle(MARGIN + 3, doc.y - 6.5, 2.2, stroke=0, fill=1)
        doc.text(line, SANS, 10.5, INK, x=MARGIN + 16, width=CONTENT_W - 16, gap=5)

    doc.ensure(110, section)
    doc.y -= 12
    doc.rule(16)
    doc.eyebrow("How to read this report")
    doc.text(
        "Everything here is computed from conversations stored in your account. Trait scores are a running "
        "average that each message nudges by at most a fifth of the way, so one bad day cannot rewrite you. "
        "Reflections are written by an AI model, then checked: any pattern whose quotes are not found word for "
        "word in your messages is thrown out. Incognito conversations are never stored and are not part of this. "
        "This is a mirror, not a diagnosis.",
        SANS, 8.8, SOFT,
    )


def render_report(data: ReportData) -> bytes:
    doc = _Doc(data)
    _cover(doc)
    _glance(doc)
    _reflections(doc)
    _change_and_rhythm(doc)
    _voice_and_adaptation(doc)
    return doc.finish()


__all__ = ["ReportData", "TraitReading", "build_persona_report_pdf", "collect_report_data", "render_report"]
