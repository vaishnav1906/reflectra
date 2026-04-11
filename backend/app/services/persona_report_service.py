import base64
import io
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import UUID

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from weasyprint import HTML

from app.db.models import (
    BehavioralInsight,
    Message,
    PersonaSnapshot,
    ReflectionLog,
    ScheduleContext,
    User,
    UserPersonaMetric,
)

def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))

def _safe_float(value, default: float = 0.5) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _limit_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    trimmed = " ".join(words[:max_words]).rstrip(" ,;:-")
    if trimmed.endswith((".", "!", "?")):
        return trimmed
    return f"{trimmed}."

def _chart_story(what_it_shows: str, what_data_means: str, why_this_matters: str) -> Dict[str, str]:
    return {
        "what_it_shows": _limit_words(what_it_shows, 14),
        "what_your_data_means": _limit_words(what_data_means, 16),
        "why_this_matters": _limit_words(why_this_matters, 14),
    }

def _file_to_data_uri(file_path: Path, mime: str) -> str | None:
    try:
        payload = base64.b64encode(file_path.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{payload}"
    except OSError:
        return None

def _load_brand_icon_uri() -> str | None:
    root = Path(__file__).resolve().parents[3]
    favicon_path = root / "frontend" / "public" / "favicon.ico"
    if favicon_path.exists():
        icon_uri = _file_to_data_uri(favicon_path, "image/x-icon")
        if icon_uri:
            return icon_uri

    # Fallback if icon file is unavailable in a runtime.
    fallback_svg = root / "frontend" / "public" / "placeholder.svg"
    if fallback_svg.exists():
        return _file_to_data_uri(fallback_svg, "image/svg+xml")
    return None

@dataclass
class ReportPayload:
    display_name: str
    generated_at: str
    overall_score: int
    emotional_identity_line: str
    why_this_score: str
    archetype_name: str
    archetype_tagline: str
    archetype_summary: str
    about_this_report: str
    how_to_read_report: List[Tuple[str, str]]
    executive_analysis: str
    key_findings: List[Tuple[str, str]]
    what_this_means: str
    chart_interpretations: Dict[str, Dict[str, str]]
    inferred_tags: List[str]
    insight_cards: List[Tuple[str, str, str]]
    strengths: List[str]
    blind_spots: List[str]
    optimization_dos: List[str]
    optimization_donts: List[str]
    interests_distribution: Dict[str, float]
    communication_traits: Dict[str, float]
    personality_dimensions: Dict[str, float]
    timeline_points: List[Tuple[str, float, float]]

async def build_persona_report_pdf(db: AsyncSession, user_id: UUID) -> bytes:
    payload = await _build_payload(db, user_id)

    pie_b64 = _build_pie_chart(payload.interests_distribution)
    bar_b64 = _build_bar_chart(payload.communication_traits)
    radar_b64 = _build_radar_chart(payload.personality_dimensions)
    timeline_b64 = _build_timeline_chart(payload.timeline_points)
    brand_icon_uri = _load_brand_icon_uri()

    html_content = _render_html(payload, pie_b64, bar_b64, radar_b64, timeline_b64, brand_icon_uri)
    pdf = HTML(string=html_content).write_pdf()
    return pdf

async def _build_payload(db: AsyncSession, user_id: UUID) -> ReportPayload:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    snapshots_result = await db.execute(
        select(PersonaSnapshot).where(PersonaSnapshot.user_id == user_id).order_by(PersonaSnapshot.created_at.asc()).limit(30)
    )
    snapshots = snapshots_result.scalars().all()

    metrics_result = await db.execute(
        select(UserPersonaMetric).where(UserPersonaMetric.user_id == user_id).order_by(desc(UserPersonaMetric.last_updated))
    )
    metrics = metrics_result.scalars().all()

    insights_result = await db.execute(
        select(BehavioralInsight).where(BehavioralInsight.user_id == user_id).order_by(desc(BehavioralInsight.created_at)).limit(120)
    )
    insights = insights_result.scalars().all()

    reflections_result = await db.execute(
        select(ReflectionLog).where(ReflectionLog.user_id == user_id).order_by(desc(ReflectionLog.created_at)).limit(60)
    )
    reflections = reflections_result.scalars().all()

    messages_result = await db.execute(
        select(Message).where(Message.user_id == user_id, Message.role == "user").order_by(desc(Message.created_at)).limit(120)
    )
    messages = messages_result.scalars().all()

    schedule_result = await db.execute(select(ScheduleContext).where(ScheduleContext.user_id == user_id))
    schedule = schedule_result.scalar_one_or_none()

    metric_map = {m.trait_name: _safe_float(m.score) for m in metrics}

    comm_style = metric_map.get("communication_style", 0.5)
    emotional_expr = metric_map.get("emotional_expressiveness", 0.5)
    decision_framing = metric_map.get("decision_framing", 0.5)
    reflection_depth = metric_map.get("reflection_depth", 0.5)

    texts = [m.content for m in messages if m.content] + [r.response for r in reflections if r.response]
    communication_traits = _derive_communication_traits(texts, comm_style, decision_framing)

    personality_dimensions = {
        "Analytical": _clamp((reflection_depth * 0.6) + (decision_framing * 0.4)),
        "Creative": _clamp((emotional_expr * 0.55) + (comm_style * 0.45)),
        "Structured": _clamp((decision_framing * 0.7) + ((1 - comm_style) * 0.3)),
        "Expressive": _clamp(emotional_expr),
        "Decisive": _clamp(decision_framing),
    }

    tags_counter = Counter()
    for insight in insights:
        for tag in (insight.tags or []):
            if not tag:
                continue
            normalized = tag.strip().lower()
            if normalized in {"behavioral-pattern", "trait-drift", "workload-context", "stress-signal"}:
                continue
            tags_counter[normalized] += 1

    if not tags_counter:
        tags_counter.update({"self-reflection": 3, "decision-making": 2, "growth": 2, "communication": 2})

    top_tags = [name for name, _ in tags_counter.most_common(8)]
    interests_distribution = _normalize_distribution(tags_counter, max_items=6)
    timeline_points = _build_timeline_points(snapshots)

    inferred_tags = _humanize_tags(top_tags)
    insight_cards = _build_insight_cards(communication_traits, personality_dimensions, schedule)

    archetype_name, archetype_tagline, archetype_summary = _build_archetype(communication_traits, personality_dimensions)
    overall_score = int((
        communication_traits.get("Curiosity", 0.5) +
        communication_traits.get("Directness", 0.5) +
        communication_traits.get("Detail Level", 0.5) +
        personality_dimensions.get("Expressive", 0.5)
    ) / 4.0 * 100)

    emotional_identity_line = _build_emotional_identity_line(communication_traits, personality_dimensions, archetype_name)
    why_this_score = _build_why_this_score(communication_traits, personality_dimensions, overall_score)
    about_this_report = _build_about_this_report()
    how_to_read_report = _build_how_to_read_report()

    strengths = _build_strengths(communication_traits, personality_dimensions)
    blind_spots = _build_blind_spots(communication_traits, personality_dimensions)
    dos, donts = _build_optimization_rules(communication_traits, personality_dimensions)

    chart_interpretations = {
        "pie": _interpret_pie(interests_distribution),
        "bar": _interpret_bar(communication_traits),
        "radar": _interpret_radar(personality_dimensions),
        "timeline": _interpret_timeline(timeline_points),
    }

    display_name = (user.display_name if user and user.display_name else "User").strip() or "User"

    return ReportPayload(
        display_name=display_name,
        generated_at=datetime.now(timezone.utc).strftime("%B %d, %Y"),
        overall_score=overall_score,
        emotional_identity_line=emotional_identity_line,
        why_this_score=why_this_score,
        archetype_name=archetype_name,
        archetype_tagline=archetype_tagline,
        archetype_summary=archetype_summary,
        about_this_report=about_this_report,
        how_to_read_report=how_to_read_report,
        executive_analysis=_build_executive_analysis(communication_traits, personality_dimensions, archetype_name),
        key_findings=_build_key_findings(communication_traits, personality_dimensions),
        what_this_means=_build_what_this_means(communication_traits, personality_dimensions),
        chart_interpretations=chart_interpretations,
        inferred_tags=inferred_tags,
        insight_cards=insight_cards,
        strengths=strengths,
        blind_spots=blind_spots,
        optimization_dos=dos,
        optimization_donts=donts,
        interests_distribution=interests_distribution,
        communication_traits=communication_traits,
        personality_dimensions=personality_dimensions,
        timeline_points=timeline_points,
    )


def _build_executive_analysis(comm: Dict[str, float], pers: Dict[str, float], arch_name: str) -> str:
    cur = comm.get("Curiosity", 0.5)
    _dir = comm.get("Directness", 0.5)
    det = comm.get("Detail Level", 0.5)

    if _dir > 0.6 and det > 0.6:
        insight = "you favor concise, high-signal briefs that convert quickly from problem framing to decision."
    elif cur > 0.6:
        insight = "you consistently expand questions to test causes, alternatives, and trade-offs before committing."
    else:
        insight = "you shift smoothly between exploration and execution as context changes."

    analysis = (
        f"Your operating profile aligns most strongly with {arch_name}. "
        f"Across sessions, {insight} "
        "You consistently reward clarity and structure, so outputs perform best when they are direct, sequenced, and explicit about next actions. "
        "Speed can occasionally obscure edge cases; adding a brief constraint or risk line materially improves precision without reducing momentum. "
        "Overall, your signature is stable enough for high-confidence personalization while remaining adaptable as priorities evolve."
    )
    return _limit_words(analysis, 140)

def _build_about_this_report() -> str:
    text = (
        "This report consolidates recent interaction patterns into a practical operating brief for how the assistant currently models your working style. "
        "It is a performance lens, not a psychological diagnosis. Scores and labels are inferred from language signals, decision behavior, and consistency over time. "
        "Use it to improve prompt quality, accelerate outcomes, and deliberately switch response modes when needed."
    )
    return _limit_words(text, 95)

def _build_how_to_read_report() -> List[Tuple[str, str]]:
    return [
        ("Start with the score", _limit_words("Treat the score as a calibration snapshot of current operating rhythm, not a fixed judgment.", 18)),
        ("Use findings as levers", _limit_words("Key findings surface repeat behaviors you can amplify or rebalance for stronger output quality.", 18)),
        ("Read charts in order", _limit_words("Move from signal, to interpretation, to action you can apply in the next prompt.", 19)),
    ]

def _build_why_this_score(comm: Dict[str, float], pers: Dict[str, float], overall_score: int) -> str:
    directness = int(comm.get("Directness", 0.5) * 100)
    detail = int(comm.get("Detail Level", 0.5) * 100)
    expressive = int(pers.get("Expressive", 0.5) * 100)
    curiosity = int(comm.get("Curiosity", 0.5) * 100)
    text = (
        f"This score is derived from four weighted signals: Directness ({directness}), Detail ({detail}), Expressiveness ({expressive}), and Curiosity ({curiosity}). "
        f"Together, they position your current engagement baseline at {overall_score}."
    )
    return _limit_words(text, 45)

def _build_emotional_identity_line(comm: Dict[str, float], pers: Dict[str, float], archetype_name: str) -> str:
    if comm.get("Directness", 0.5) > 0.62:
        text = f"You lead with intent and momentum. {archetype_name} reflects a decisive, execution-first rhythm."
    elif pers.get("Expressive", 0.5) > 0.6:
        text = f"You lead with tone and meaning. {archetype_name} reflects a nuanced, human-centered cognitive style."
    else:
        text = f"You lead with balance and range. {archetype_name} reflects a steady blend of exploration and delivery."
    return _limit_words(text, 28)

def _build_key_findings(comm: Dict[str, float], pers: Dict[str, float]) -> List[Tuple[str, str]]:
    findings = []

    if comm.get("Directness", 0.5) > 0.55:
        findings.append(("High Directness", _limit_words("You often skip ceremony and move quickly toward action, decisions, and concrete output formats.", 20)))
    else:
        findings.append(("Context-Heavy Framing", _limit_words("You front-load context to reduce ambiguity and improve alignment before execution starts.", 18)))

    if comm.get("Curiosity", 0.5) > 0.55:
        findings.append(("Exploratory Curiosity", _limit_words("Your prompts frequently probe causes and alternatives, signaling a preference for understanding over quick surface answers.", 20)))

    if pers.get("Analytical", 0.5) > 0.55:
        findings.append(("Analytical Rigor", _limit_words("You engage best when reasoning is explicit, sequential, and transparent from assumptions to conclusion.", 18)))

    if pers.get("Expressive", 0.5) > 0.55:
        findings.append(("Expressive Resonance", _limit_words("You respond well to language with tone and nuance, especially when ideas are framed in a human way.", 21)))

    if len(findings) < 4:
        findings.append(("Systemic Rhythm", _limit_words("Your pacing stays consistent across sessions, which improves personalization reliability over time.", 17)))
        findings.append(("Detail Orientation", _limit_words("You increasingly specify output structure, which helps produce high-fit answers faster.", 14)))

    return findings[:4]

def _build_what_this_means(comm: Dict[str, float], pers: Dict[str, float]) -> str:
    text = (
        "Your behavior now acts as a reusable operating layer for response configuration. "
        "Because the system recognizes your preferred pace, tone, and information density, you can write shorter prompts without sacrificing quality. "
        "When you need a different style, one explicit instruction can temporarily override your default baseline."
    )
    return _limit_words(text, 75)

def _build_archetype(comm: Dict[str, float], pers: Dict[str, float]) -> Tuple[str, str, str]:
    if pers.get("Structured", 0) > 0.6 and comm.get("Directness", 0) > 0.6:
        return (
            "The Clarity-Driven Operator",
            "You prioritize clarity, speed, and practical outcomes.",
            "Your profile reflects structured decision-making and a bias toward clear execution. You likely use AI to reduce ambiguity and move quickly into action."
        )
    elif comm.get("Curiosity", 0) > 0.6 and pers.get("Creative", 0) > 0.5:
        return (
            "The Outcome-Focused Thinker",
            "You explore broadly, then converge on what works.",
            "You naturally investigate why and how before committing to a direction. You use AI for both exploration and practical synthesis that leads to outcomes."
        )
    elif pers.get("Analytical", 0) > 0.6:
        return (
            "The Decisive Strategist",
            "You rely on logic, patterns, and deliberate reasoning.",
            "You break down complex problems systematically and make deliberate trade-offs. You prefer responses that are nuanced, evidence-based, and context aware."
        )
    elif pers.get("Expressive", 0) > 0.6:
        return (
            "The Precision Executor",
            "Your ideas flow freely with creativity and emotional resonance.",
            "You communicate with nuance while keeping strong intent. You value thoughtful framing but still expect practical structure and follow-through."
        )
    else:
        return (
            "The Adaptive Pragmatist",
            "You adapt your style seamlessly based on the context at hand.",
            "Your interactions show a highly balanced approach. You can dive into details when necessary, but remain comfortable with high-level summaries."
        )

def _build_strengths(comm: Dict[str, float], pers: Dict[str, float]) -> List[str]:
    s = []
    if comm.get("Directness", 0.5) > 0.6: s.append("Clear and unambiguous in expressing needs, saving time and friction.")
    else: s.append("Provides rich, contextual detail allowing for highly personalized AI responses.")
    if pers.get("Analytical", 0.5) > 0.6: s.append("Strong ability to structure complex problems logically.")
    if pers.get("Creative", 0.5) > 0.6: s.append("Highly imaginative; pushes the boundaries of standard solutions.")
    if not s: s.extend(["Highly adaptable communication style.", "Consistently provides balanced context."])
    return s[:3]

def _build_blind_spots(comm: Dict[str, float], pers: Dict[str, float]) -> List[str]:
    b = []
    if comm.get("Directness", 0.5) > 0.65: b.append("May occasionally sacrifice deeper exploratory thinking for speed.")
    if comm.get("Curiosity", 0.5) < 0.4: b.append("Could benefit from asking more open-ended 'what if' questions to unlock broader insights.")
    if pers.get("Structured", 0.5) > 0.7: b.append("High structure preference might limit lateral or purely creative brainstorming sessions.")
    if not b: b.append("Interaction rhythm is steady, but could unlock edges by varying prompt structures.")
    return b[:3]

def _build_optimization_rules(comm: Dict[str, float], pers: Dict[str, float]) -> Tuple[List[str], List[str]]:
    dos = ["Do use your natural voice; the AI is actively adapting to your baseline style."]
    donts = ["Don't feel the need to over-explain simple tasks unless you want a deep dive."]
    if comm.get("Directness", 0.5) > 0.6:
        dos.append("Frame your goals as direct execution tasks to trigger immediate action.")
        donts.append("Don't worry about conversational pleasantries; optimize for speed.")
    else:
        dos.append("Share background context and 'why' you are doing something for better alignment.")
        donts.append("Don't assume the AI will guess your constraints—state them clearly.")
    return dos[:3], donts[:3]

def _interpret_pie(dist: Dict[str, float]) -> Dict[str, str]:
    if not dist:
        return _chart_story(
            "This chart shows your recurring conversation theme mix.",
            "There is not enough topic data yet to identify a dominant focus.",
            "More usage will make personalization recommendations sharper and more reliable.",
        )
    items = list(dist.items())
    top_label, top_ratio = items[0]
    concentration = "highly concentrated" if top_ratio >= 0.38 else "fairly distributed"
    return _chart_story(
        "This chart shows where your attention is spent most often.",
        f"{top_label} leads at about {top_ratio:.0%}, and your mix is {concentration}.",
        "Use this focus to prioritize examples, depth, and default response framing.",
    )

def _interpret_bar(traits: Dict[str, float]) -> Dict[str, str]:
    top_trait = max(traits, key=traits.get) if traits else "Directness"
    top_val = traits.get(top_trait, 0.5)
    return _chart_story(
        "This chart compares curiosity, directness, and detail in your prompt style.",
        f"{top_trait} is strongest at {top_val:.2f}, driving most of your interaction tone.",
        "Match prompts to this lead trait first, then tune the other two.",
    )

def _interpret_radar(dims: Dict[str, float]) -> Dict[str, str]:
    if not dims:
        return _chart_story(
            "This chart maps your profile across core behavior dimensions.",
            "There is not enough stable data yet to identify a dominant dimension.",
            "A clearer shape improves fit for response tone and structure.",
        )
    top = max(dims, key=dims.get)
    spread = max(dims.values()) - min(dims.values())
    shape = "specialized" if spread > 0.25 else "balanced"
    return _chart_story(
        "This chart shows your multi-axis behavioral signature in one shape.",
        f"{top} is highest, and your overall profile currently looks {shape}.",
        "The shape guides optimization for precision, creativity, structure, and tone.",
    )

def _interpret_timeline(points: List[Tuple[str, float, float]]) -> Dict[str, str]:
    if not points or len(points) < 2:
        return _chart_story(
            "This chart tracks consistency and reflection depth over time.",
            "There are not enough sessions yet to detect meaningful movement.",
            "More history increases confidence in long-range personalization decisions.",
        )
    delta = points[-1][1] - points[0][1]
    direction = "upward" if delta > 0.08 else "stable"
    return _chart_story(
        "This chart tracks how steady your interaction baseline stays across sessions.",
        f"Consistency trend is {direction}, indicating how stable your interaction rhythm is.",
        "Higher stability enables faster personalization with fewer clarifying questions.",
    )

def _humanize_tags(tags: List[str]) -> List[str]:
    mapping = {
        "self-reflection": "Introspective Thinker 🪞",
        "decision-making": "Decisive Executor 🎯",
        "growth": "Growth Mindset 🌱",
        "communication": "Clear Communicator 💬",
        "planning": "Strategic Planner 📅",
        "creativity": "Creative Explorer 🎨",
    }
    return [mapping.get(t.lower(), f"{t.replace('-', ' ').title()} 📌") for t in tags]

def _normalize_distribution(counter: Counter, max_items: int = 6) -> Dict[str, float]:
    most_common = counter.most_common(max_items)
    if not most_common: return {"General": 1.0}
    total = sum(count for _, count in most_common)
    if total <= 0: return {name.title(): 1 / len(most_common) for name, _ in most_common}
    return {name.replace("-", " ").title(): count / total for name, count in most_common}

def _derive_communication_traits(texts: List[str], comm: float, dec: float) -> Dict[str, float]:
    if not texts: return {"Curiosity": 0.5, "Directness": 0.5, "Detail Level": comm}
    total_words, question_hits, qualifier_hits = 0, 0, 0
    q_words = {"why", "how", "what", "when", "where", "could", "can", "should", "would"}
    c_words = {"maybe", "perhaps", "kind of", "sort of", "i think", "possibly", "not sure", "might"}
    for t in texts:
        l = t.lower()
        w = l.split()
        total_words += len(w)
        for q in q_words:
            if f" {q} " in f" {l} ": question_hits += 1
        for c in c_words:
            if c in l: qualifier_hits += 1
    d_level = _clamp((total_words / max(len(texts), 1) / 35.0) * 0.55 + comm * 0.45)
    cur = _clamp((question_hits / max(len(texts), 1)) * 0.8)
    dr = _clamp((1.0 - (qualifier_hits / max(len(texts), 1) * 0.28)) * 0.55 + dec * 0.45)
    return {"Curiosity": cur, "Directness": dr, "Detail Level": d_level}

def _build_timeline_points(snapshots: List[PersonaSnapshot]) -> List[Tuple[str, float, float]]:
    pts = []
    for s in snapshots[-12:]:
        dt = _to_utc(s.created_at)
        lbl = dt.strftime("%b %d") if dt else "Session"
        stab = _safe_float(s.stability_index, 0.5)
        prof = (s.persona_vector or {}).get("behavioral_profile", {})
        refl = 0.5
        if isinstance(prof, dict):
            tp = prof.get("reflection_depth", {})
            if isinstance(tp, dict): refl = _safe_float(tp.get("score"), 0.5)
        pts.append((lbl, _clamp(stab), _clamp(refl)))
    return pts

def _build_insight_cards(comm: Dict[str, float], pers: Dict[str, float], sched: ScheduleContext | None) -> List[Tuple[str, str, str]]:
    cards = []
    if comm.get("Curiosity", 0.0) >= 0.62: cards.append(("🧐", "Highly Curious", "Regularly asks exploratory questions and seeks context."))
    if comm.get("Directness", 0.0) >= 0.62: cards.append(("⚡", "Action-Oriented", "Responds strongly to clear, actionable guidance."))
    if pers.get("Expressive", 0.0) >= 0.62: cards.append(("🌟", "Expressive Mind", "Comfortable with richer emotional language/nuance."))
    if pers.get("Analytical", 0.0) >= 0.62: cards.append(("🛠️", "Analytical Thinker", "Reasons through patterns before committing to decisions."))
    if sched and _safe_float(sched.stress_level, 0.0) >= 0.7: cards.append(("⚠️", "High Workload", "Periods benefit from concise planning and priority framing."))
    if not cards: cards.append(("⚖️", "Balanced Profile", "Interaction style is robust, broad, and still forming."))
    return cards[:4]

def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor="white", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

def _style_matplotlib():
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans", "Liberation Sans", "Arial", "sans-serif"], "font.size": 11,
        "axes.edgecolor": "#E2E8F0", "axes.labelcolor": "#475569", "axes.titleweight": "bold",
        "axes.titlesize": 13, "xtick.color": "#94A3B8", "ytick.color": "#94A3B8",
        "figure.facecolor": "none", "axes.facecolor": "none"
    })

def _build_pie_chart(dist: Dict[str, float]) -> str:
    _style_matplotlib()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    palette = ["#6366F1", "#8B5CF6", "#A855F7", "#D946EF", "#EC4899", "#F43F5E"]
    ax.pie(dist.values(), labels=dist.keys(), colors=palette[:len(dist)], autopct=lambda p: f"{p:.0f}%", startangle=140, wedgeprops={"linewidth": 3, "edgecolor": "white"})
    ax.axis("equal")
    return _fig_to_b64(fig)

def _build_bar_chart(traits: Dict[str, float]) -> str:
    _style_matplotlib()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.bar(traits.keys(), traits.values(), color=["#6366F1", "#8B5CF6", "#EC4899"], width=0.45)
    ax.set_ylim(0, 1)
    ax.grid(axis="y", alpha=0.25, color="#CBD5E1")
    ax.set_axisbelow(True)
    for bar, val in zip(bars, traits.values()):
        ax.text(bar.get_x() + bar.get_width()/2, val + 0.04, f"{val:.2f}", ha="center", va="bottom", fontsize=10, fontweight="bold", color="#334155")
    return _fig_to_b64(fig)

def _build_radar_chart(dims: Dict[str, float]) -> str:
    _style_matplotlib()
    labels, values = list(dims.keys()), list(dims.values())
    angles = np.linspace(0, 2*math.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]; values += values[:1]
    fig, ax = plt.subplots(figsize=(6, 3.8), subplot_kw={"polar": True})
    ax.plot(angles, values, color="#8B5CF6", linewidth=2.5)
    ax.fill(angles, values, color="#A855F7", alpha=0.25)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(labels, fontsize=10, color="#64748B")
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels([""]*5)
    ax.set_ylim(0, 1)
    return _fig_to_b64(fig)

def _build_timeline_chart(points: List[Tuple[str, float, float]]) -> str:
    _style_matplotlib()
    if not points: points = [("Intro", 0.5, 0.5), ("Latest", 0.52, 0.5)]
    labels, stab, depth = [p[0] for p in points], [p[1] for p in points], [p[2] for p in points]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(labels, stab, marker="o", lw=2.5, color="#6366F1", label="Consistency")
    ax.plot(labels, depth, marker="o", lw=2.5, color="#EC4899", label="Reflection Depth")
    ax.set_ylim(0, 1)
    ax.grid(axis="y", alpha=0.25, color="#CBD5E1")
    ax.legend(loc="lower right", frameon=True, fontsize=9, facecolor="#F8FAFC", edgecolor="#E2E8F0")
    ax.tick_params(axis="x", rotation=25)
    ax.set_axisbelow(True)
    return _fig_to_b64(fig)

def _render_html(p: ReportPayload, pie_b64: str, bar_b64: str, radar_b64: str, timeline_b64: str, brand_icon_uri: str | None = None) -> str:
    import jinja2

    template = """<!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <title>Persona Intelligence Report</title>
    <style>
        /* A4 Page dimensions strictly defined */
        @page {
            size: A4;
            margin: 15mm 20mm;
            background: #F8FAFC;
            counter-increment: report_page;
            @bottom-center {
                content: "Page " counter(report_page);
                font-size: 9px;
                color: #94A3B8;
            }
        }
        @page cover {
            background:
                radial-gradient(circle at 16% 18%, rgba(56, 189, 248, 0.20) 0%, rgba(56, 189, 248, 0.00) 42%),
                radial-gradient(circle at 82% 78%, rgba(167, 139, 250, 0.18) 0%, rgba(167, 139, 250, 0.00) 44%),
                linear-gradient(145deg, #0B1220 0%, #1A2140 56%, #121A34 100%);
            margin: 0;
            counter-increment: none;
            @bottom-center {
                content: none;
            }
        }
        
        body {
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            color: #1E293B;
            line-height: 1.5;
            margin: 0;
            padding: 0;
            font-size: 12px;
        }

        /* PAGE 1: COVER PAGE */
        .cover-wrapper {
            page: cover;
            page-break-after: always;
            position: relative;
            height: 297mm; /* Absolute height for WeasyPrint */
            width: 210mm;
            box-sizing: border-box;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 44px 40px 88px 40px;
        }
        .cover-wrapper::before {
            content: "";
            position: absolute;
            inset: 26px;
            border-radius: 14px;
            border: 1px solid rgba(148, 163, 184, 0.12);
            background: linear-gradient(165deg, rgba(15, 23, 42, 0.16), rgba(30, 27, 75, 0.04));
            pointer-events: none;
        }
        .cover-wrapper::after {
            content: "";
            position: absolute;
            top: -80px;
            right: -120px;
            width: 340px;
            height: 340px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.20) 0%, rgba(56, 189, 248, 0) 70%);
            pointer-events: none;
        }
        .cover-content {
            position: relative;
            width: 100%;
            max-width: 760px;
            text-align: center;
            color: #FFFFFF;
            z-index: 2;
        }
        .cover-brand-icon {
            width: 34px;
            height: 34px;
            margin: 0 auto 18px auto;
            display: block;
            border-radius: 10px;
            border: 1px solid rgba(148, 163, 184, 0.35);
            background: rgba(15, 23, 42, 0.55);
            padding: 6px;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.34);
        }
        .cover-title-small { font-size: 12px; color: #93C5FD; text-transform: uppercase; letter-spacing: 2.2px; margin-bottom: 24px; font-weight: 700; }
        .cover-main-title { font-size: 60px; font-weight: 900; line-height: 1.06; margin: 0 0 14px 0; letter-spacing: -1.4px; text-wrap: balance; }
        .cover-subtitle { font-size: 27px; font-weight: 600; color: #D6E4FF; margin: 0 0 22px 0; letter-spacing: -0.2px; }
        .cover-tagline { font-size: 18px; color: #C4B5FD; margin: 0 auto 36px auto; line-height: 1.5; max-width: 620px; }
        .cover-badge {
            display: inline-block;
            background: linear-gradient(160deg, rgba(56, 189, 248, 0.16), rgba(99, 102, 241, 0.12));
            border: 1px solid rgba(125, 211, 252, 0.38);
            border-radius: 10px;
            padding: 22px 46px;
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.36), inset 0 1px 0 rgba(255, 255, 255, 0.12);
        }
        .cover-val { font-size: 48px; font-weight: 800; color: #38BDF8; line-height: 1; margin-bottom: 8px; }
        .cover-label { font-size: 12px; text-transform: uppercase; font-weight: 700; color: #E0F2FE; letter-spacing: 1px; }
        .cover-why {
            margin: 24px auto 0 auto;
            max-width: 560px;
            font-size: 12px;
            color: #E2E8F0;
            line-height: 1.5;
            padding: 14px 16px;
            border-radius: 8px;
            background: rgba(15, 23, 42, 0.34);
            border: 1px solid rgba(148, 163, 184, 0.30);
        }

        .cover-footer {
            position: absolute;
            bottom: 40px;
            left: 50px;
            right: 50px;
            border-top: 1px solid rgba(255,255,255,0.15);
            padding-top: 20px;
            font-size: 11px;
            color: #94A3B8;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .cover-fl { float: left; }
        .cover-fr { float: right; }
        .clear { clear: both; }

        .report-pages {
            counter-reset: report_page 0;
        }

        /* ANALYTICAL REPORT CONTENT */
        .section-block {
            margin-bottom: 32px;
            page-break-inside: avoid;
        }
        .section-heading {
            font-size: 18px; font-weight: 800; color: #0F172A; text-transform: uppercase; letter-spacing: -0.5px;
            margin: 0 0 6px 0; border-bottom: 2px solid #E2E8F0; padding-bottom: 8px;
            page-break-after: avoid;
        }
        .section-sub {
            font-size: 11px; color: #64748B; margin: 12px 0 20px 0; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
            page-break-after: avoid;
        }

        .grid-2-col {
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
        }
        .col-half {
            width: calc(50% - 10px);
            box-sizing: border-box;
        }

        .premium-card {
            background: #FFFFFF;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 2px 4px rgba(15, 23, 42, 0.03);
            border: 1px solid #E2E8F0;
            margin-bottom: 20px;
            page-break-inside: avoid;
        }

        .card-title {
            font-weight: 800; font-size: 12px; color: #1E293B; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px;
        }
        .list-item { margin-bottom: 8px; font-size: 11.5px; color: #334155; line-height: 1.5; }

        /* Exec Block */
        .exec-block {
            background: #FFFFFF; border-left: 4px solid #6366F1; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
            font-size: 12.5px; color: #334155; line-height: 1.7; page-break-inside: avoid; margin-bottom: 12px;
        }

        /* Pills */
        .pill-grid { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; }
        .pill { 
            background: #FFFFFF; border: 1px solid #CBD5E1; padding: 10px 18px; border-radius: 6px; 
            font-size: 11px; font-weight: 700; color: #0F172A; text-transform: uppercase; letter-spacing: 0.5px; 
            box-shadow: 0 1px 2px rgba(0,0,0,0.02);
            page-break-inside: avoid;
        }

        /* Charts */
        .chart-img { width: 100%; border-radius: 4px; margin-bottom: 16px; border: 1px solid #F1F5F9; }
        .chart-caption { font-size: 10.5px; color: #475569; padding-top: 8px; border-top: 1px solid #F1F5F9; line-height: 1.32; }
        .chart-tier { margin-bottom: 5px; }
        .chart-tier:last-child { margin-bottom: 0; }
        .chart-tier-label {
            display: block;
            font-size: 8.5px;
            letter-spacing: 0.7px;
            text-transform: uppercase;
            font-weight: 800;
            color: #64748B;
            margin-bottom: 1px;
        }

        .how-item {
            margin-bottom: 8px;
            font-size: 11.5px;
            color: #334155;
            line-height: 1.5;
        }
        .how-item:last-child { margin-bottom: 0; }

        .card-green { border-top: 4px solid #10B981; }
        .card-green .card-title { color: #047857; }
        .card-red { border-top: 4px solid #EF4444; }
        .card-red .card-title { color: #B91C1C; }
        .card-neutral { border-top: 4px solid #38BDF8; }
        .card-neutral .card-title { color: #0369A1; }

        .footer-disclaimer {
            text-align: center; color: #94A3B8; font-size: 9px; padding: 24px 40px; line-height: 1.5; 
            text-transform: uppercase; letter-spacing: 0.5px; border-top: 1px solid #E2E8F0; margin-top: 20px;
        }
    </style>
    </head>
    <body>

    <!-- PAGE 1: COVER PAGE -->
    <div class="cover-wrapper">
        <div class="cover-content">
            {% if brand_icon_uri %}
            <img class="cover-brand-icon" src="{{ brand_icon_uri }}" alt="Brand">
            {% endif %}
            <div class="cover-title-small">Reflectra</div>
            <div class="cover-main-title">Persona Report Summary</div>
            <div class="cover-subtitle">Your AI Interaction Profile</div>
            <div class="cover-tagline">You prioritize clarity, speed, and practical outcomes.</div>
            
            <div class="cover-badge">
                <div class="cover-val">{{ p.overall_score }}</div>
                <div class="cover-label">Engagement Baseline</div>
            </div>
            <div class="cover-why"><b>Why This Score:</b> {{ p.why_this_score }}</div>
        </div>
        
        <div class="cover-footer">
            <div class="cover-fl">User: <b>{{ p.display_name }}</b></div>
            <div class="cover-fr">Generated: <b>{{ p.generated_at }}</b></div>
            <div class="clear"></div>
        </div>
    </div>

    <!-- PAGE 2+: ANALYTICAL CONTENT -->
    <div class="report-pages">

    <div class="section-block">
        <h2 class="section-heading">Before You Read</h2>
        <p class="section-sub">Context to interpret the report quickly and correctly.</p>

        <div class="premium-card">
            <div class="card-title">About This Report</div>
            <p style="margin: 0; font-size: 11.5px; color: #475569; line-height: 1.6;">{{ p.about_this_report }}</p>
        </div>

        <div class="premium-card">
            <div class="card-title">How To Read This Report</div>
            {% for title, desc in p.how_to_read_report %}
            <div class="how-item"><b>{{ title }}:</b> {{ desc }}</div>
            {% endfor %}
        </div>

        <div class="premium-card">
            <div class="card-title">Why This Score</div>
            <p style="margin: 0; font-size: 11.5px; color: #475569; line-height: 1.6;">{{ p.why_this_score }}</p>
        </div>
    </div>
    
    <div class="section-block">
        <h2 class="section-heading">Executive Analysis</h2>
        <p class="section-sub">High-level synthesis of your interaction footprint.</p>
        
        <div class="exec-block">
            <b>Primary Cognitive Footprint:</b> {{ p.executive_analysis }}
        </div>
        <div class="exec-block" style="border-left-color: #38BDF8;">
            <b>Operational Translation:</b> {{ p.what_this_means }}
        </div>
    </div>

    <div class="section-block">
        <h2 class="section-heading">Behavioral Mechanics</h2>
        <p class="section-sub">Foundational cognitive signatures driving engagement.</p>
        
        <div class="pill-grid">
            <div class="pill">Action-Oriented</div>
            <div class="pill">Structured Thinker</div>
            <div class="pill">Outcome Driven</div>
            <div class="pill">Expressive Communicator</div>
        </div>
    </div>

    <div class="section-block">
        <h2 class="section-heading">Capability Assessment</h2>
        <p class="section-sub">Strengths and limitations inferred from behavior.</p>

        <div class="grid-2-col">
            <div class="premium-card card-green col-half">
                <div class="card-title">Operational Strengths</div>
                {% for item in p.strengths %}
                <div class="list-item">- {{ item }}</div>
                {% endfor %}
            </div>
            <div class="premium-card card-red col-half">
                <div class="card-title">Blind Spots</div>
                {% for item in p.blind_spots %}
                <div class="list-item">- {{ item }}</div>
                {% endfor %}
            </div>
        </div>
    </div>

    <div class="section-block">
        <h2 class="section-heading">Key Findings</h2>
        <p class="section-sub">Critical mechanisms shaping your AI alignment.</p>

        <div class="grid-2-col">
            {% for title, desc in p.key_findings %}
            <div class="premium-card col-half" style="border-left: 4px solid #8B5CF6;">
                <div class="card-title">{{ title }}</div>
                <p style="margin: 0; font-size: 11.5px; color: #475569;">{{ desc }}</p>
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="section-block">
        <h2 class="section-heading">Data Storytelling</h2>
        <p class="section-sub">Premium visual analytics representing your baseline.</p>

        <div class="grid-2-col">
            <div class="premium-card col-half">
                <div class="card-title">Interests & Topic Gravity</div>
                <img class="chart-img" src="data:image/png;base64,{{ pie_b64 }}" alt="Chart">
                <div class="chart-caption">
                    <div class="chart-tier"><span class="chart-tier-label">What This Shows</span>{{ p.chart_interpretations.pie.what_it_shows }}</div>
                    <div class="chart-tier"><span class="chart-tier-label">What Your Data Means</span>{{ p.chart_interpretations.pie.what_your_data_means }}</div>
                    <div class="chart-tier"><span class="chart-tier-label">Why This Matters</span>{{ p.chart_interpretations.pie.why_this_matters }}</div>
                </div>
            </div>

            <div class="premium-card col-half">
                <div class="card-title">Interaction Vectors</div>
                <img class="chart-img" src="data:image/png;base64,{{ bar_b64 }}" alt="Chart">
                <div class="chart-caption">
                    <div class="chart-tier"><span class="chart-tier-label">What This Shows</span>{{ p.chart_interpretations.bar.what_it_shows }}</div>
                    <div class="chart-tier"><span class="chart-tier-label">What Your Data Means</span>{{ p.chart_interpretations.bar.what_your_data_means }}</div>
                    <div class="chart-tier"><span class="chart-tier-label">Why This Matters</span>{{ p.chart_interpretations.bar.why_this_matters }}</div>
                </div>
            </div>

            <div class="premium-card col-half">
                <div class="card-title">Multi-Axis Signature</div>
                <img class="chart-img" src="data:image/png;base64,{{ radar_b64 }}" alt="Chart">
                <div class="chart-caption">
                    <div class="chart-tier"><span class="chart-tier-label">What This Shows</span>{{ p.chart_interpretations.radar.what_it_shows }}</div>
                    <div class="chart-tier"><span class="chart-tier-label">What Your Data Means</span>{{ p.chart_interpretations.radar.what_your_data_means }}</div>
                    <div class="chart-tier"><span class="chart-tier-label">Why This Matters</span>{{ p.chart_interpretations.radar.why_this_matters }}</div>
                </div>
            </div>

            <div class="premium-card col-half">
                <div class="card-title">Rhythm Over Time</div>
                <img class="chart-img" src="data:image/png;base64,{{ timeline_b64 }}" alt="Chart">
                <div class="chart-caption">
                    <div class="chart-tier"><span class="chart-tier-label">What This Shows</span>{{ p.chart_interpretations.timeline.what_it_shows }}</div>
                    <div class="chart-tier"><span class="chart-tier-label">What Your Data Means</span>{{ p.chart_interpretations.timeline.what_your_data_means }}</div>
                    <div class="chart-tier"><span class="chart-tier-label">Why This Matters</span>{{ p.chart_interpretations.timeline.why_this_matters }}</div>
                </div>
            </div>
        </div>
    </div>

    <div class="section-block">
        <h2 class="section-heading">Persona Playbook</h2>
        <p class="section-sub">AI Optimization Mode: Proven prompt framing techniques.</p>

        <div class="grid-2-col">
            <div class="premium-card card-green col-half">
                <div class="card-title">Do This</div>
                {% for d in p.optimization_dos %}
                <div class="list-item">- {{ d }}</div>
                {% endfor %}
            </div>
            <div class="premium-card card-red col-half">
                <div class="card-title">Avoid This</div>
                {% for d in p.optimization_donts %}
                <div class="list-item">- {{ d }}</div>
                {% endfor %}
            </div>
            <div class="premium-card card-neutral" style="width: 100%;">
                <div class="card-title">Strategic Adjustments</div>
                <p style="margin: 0; font-size: 11.5px; color: #475569; line-height: 1.5;">The system maps firmly to your <b>{{ p.archetype_name }}</b> baseline. It filters out irrelevant boilerplate automatically. If you want to break out of this operational mold to explore horizontally, simply instruct: <i>"Give me an exploratory, completely unrestricted summary."</i></p>
            </div>
        </div>
    </div>

    <div class="footer-disclaimer">
        Disclaimer: The insights presented in this report are algorithmically inferred based on historical interaction patterns and linguistic analysis. They reflect probability clusters rather than absolute psychological profiles and represent a snapshot in time. Your cognitive footprint is dynamic and will naturally evolve as your usage scales. Use this intelligence strictly as an operational optimization layer.
    </div>

    </div>

    </body>
    </html>"""
    
    t = jinja2.Template(template)
    return t.render(p=p, pie_b64=pie_b64, bar_b64=bar_b64, radar_b64=radar_b64, timeline_b64=timeline_b64, brand_icon_uri=brand_icon_uri)
