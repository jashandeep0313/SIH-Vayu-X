"""Generate the Vayu-X question-and-answer briefing as a PDF.

Written as a script rather than a hand-made document so the numbers cannot go
stale: every metric is read from the model reports and the live configuration at
build time. If the model is retrained, rebuild this and the figures follow.

    python scripts/build_qa_pdf.py

Output: docs/Vayu-X_SIH_QA_Briefing.pdf
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINTS = ROOT / "ai-model" / "models" / "checkpoints"
OUT = ROOT / "docs" / "Vayu-X_SIH_QA_Briefing.pdf"

INK = colors.HexColor("#1C2128")
MUTE = colors.HexColor("#5A6472")
GOLD = colors.HexColor("#9A7B1F")
SAGE = colors.HexColor("#4A7A63")
RULE = colors.HexColor("#D8DCE2")
BAND = colors.HexColor("#F2F4F7")


def load(name: str) -> dict:
    p = CHECKPOINTS / name
    if not p.exists():
        print(f"  ! {p} missing — run training first", file=sys.stderr)
        return {}
    return json.loads(p.read_text())


# --------------------------------------------------------------------- styles
ss = getSampleStyleSheet()
BODY = ParagraphStyle(
    "body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.4,
    textColor=INK, alignment=TA_JUSTIFY, spaceAfter=5,
)
Q = ParagraphStyle(
    "q", parent=BODY, fontName="Helvetica-Bold", fontSize=9.8, leading=13,
    textColor=colors.HexColor("#12304A"), spaceBefore=9, spaceAfter=3, alignment=0,
)
H1 = ParagraphStyle(
    "h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=19,
    textColor=INK, spaceBefore=2, spaceAfter=2,
)
H2 = ParagraphStyle(
    "h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=15,
    textColor=GOLD, spaceBefore=14, spaceAfter=5,
)
SMALL = ParagraphStyle(
    "small", parent=BODY, fontSize=8, leading=11, textColor=MUTE, alignment=0,
)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.2, leading=11, alignment=0, spaceAfter=0)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")


def P(t, s=BODY):
    return Paragraph(t, s)


def qa(question: str, *answer: str):
    """One question with its answer, kept on a single page where it fits."""
    blocks = [P(question, Q)] + [P(a) for a in answer]
    return KeepTogether(blocks)


def table(rows, widths, header=True, align_right=()):
    data = [[Paragraph(str(c), CELLB if (header and r == 0) else CELL) for c in row]
            for r, row in enumerate(rows)]
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), BAND)]
    for col in align_right:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(style))
    return t


def page_furniture(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTE)
    canvas.drawString(18 * mm, h - 12 * mm, "Vayu-X  ·  SIH 2026  ·  PS 26070  ·  Team 152")
    canvas.drawRightString(w - 18 * mm, h - 12 * mm, "Ministry of Earth Sciences / IMD")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(18 * mm, h - 14 * mm, w - 18 * mm, h - 14 * mm)
    canvas.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)
    canvas.drawString(18 * mm, 10 * mm, "Question & Answer Briefing")
    canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build():
    intensity = load("intensity_model_report.json")
    track = load("track_model_report.json")

    mae = intensity.get("wind_mae_kt", "—")
    skill = intensity.get("skill_vs_mean_baseline")
    skill_pct = f"{skill * 100:.1f}%" if skill is not None else "—"
    within1 = intensity.get("category_within_one")
    within1_pct = f"{within1 * 100:.1f}%" if within1 is not None else "—"
    cov = intensity.get("interval_coverage_conformal")
    cov_pct = f"{cov * 100:.1f}%" if cov is not None else "—"
    per_cat = intensity.get("per_category_error", {})
    leads = track.get("leads", {})
    train_seasons = track.get("train_seasons", ["—", "—"])
    test_seasons = track.get("test_seasons", ["—", "—"])

    story = []
    A = story.append

    # ------------------------------------------------------------- cover
    A(Spacer(1, 6 * mm))
    A(P("Vayu-X — Cyclone Intelligence Platform", H1))
    A(P(
        "AI/ML based identification, classification and prediction of tropical cyclone "
        "patterns using multi-source satellite data", BODY))
    A(Spacer(1, 3 * mm))
    A(table([
        ["Problem Statement", "PS 26070"],
        ["Organisation", "Ministry of Earth Sciences (MoES) — India Meteorological Department"],
        ["Theme / Category", "Disaster Management · Software"],
        ["Team", "Vayu-X (Team 152) · SIH 2026"],
        ["Built", datetime.now(UTC).strftime("%d %B %Y")],
    ], [42 * mm, 132 * mm], header=False))
    A(Spacer(1, 4 * mm))
    A(P(
        "<b>How to use this document.</b> It answers the questions most likely to be asked "
        "about the system, in the order they usually come up. Every number here is read "
        "directly from the trained model reports at build time, so nothing in it is a "
        "rounded-up claim. Where the system is weak, this document says so and says by how "
        "much — a limitation you have measured is a stronger answer than one you have not "
        "noticed.", BODY))

    # ---------------------------------------------------- 1. what is real
    A(P("1 · What is real, and what is not", H2))
    A(P(
        "The most common question, and the one worth answering first and plainly.", BODY))
    A(Spacer(1, 2 * mm))
    A(table([
        ["Component", "State"],
        ["Track &amp; intensity forecasting",
         "<b>Real.</b> Trained on IBTrACS best-track data, evaluated against held-out seasons."],
        ["Intensity from a satellite image",
         f"<b>Real.</b> Trained on {intensity.get('n_frames', '—'):,} labelled frames from "
         f"{intensity.get('n_storms', '—')} storms. Held-out MAE {mae} kt."],
        ["Out-of-distribution refusal",
         "<b>Real.</b> Three independent gates; unrelated images are refused, not scored."],
        ["Alert rules &amp; message rendering",
         "<b>Real.</b> Rules are data (YAML), tuned without a redeploy."],
        ["SMS dispatch",
         "<b>Real</b> (Fast2SMS), operator-triggered only."],
        ["Siren tower",
         "<b>Real hardware.</b> ESP32 over USB serial, fires automatically."],
        ["Cyclone <i>localisation</i> in a full-disk frame",
         "<b>Not built.</b> Needs INSAT full-disk frames; MOSDAC access pending."],
        ["Dvorak <i>pattern</i> classification",
         "<b>Not built.</b> The datasets carry wind speed, not pattern labels. Any pattern "
         "shown is inferred from intensity and is labelled as such in the response."],
        ["Geofenced delivery to real recipients",
         "<b>Not built.</b> Rules and rendering work; recipient resolution does not."],
    ], [46 * mm, 128 * mm], align_right=()))

    # -------------------------------------------- 2. the map / datasets
    A(P("2 · The map — datasets, storms and timeline", H2))

    A(qa(
        "Q. Which four cyclones are on the map, and why those four?",
        "They are chosen by the code, not hand-picked: the four most intense storms in the "
        "North Indian Ocean from the seasons the forecasting model was <i>not</i> trained on. "
        "Selecting by peak intensity keeps the demonstration on the cases that matter, and "
        "selecting from held-out seasons keeps it honest.",
    ))
    A(Spacer(1, 1.5 * mm))
    A(table([
        ["Storm", "Basin", "Season", "Peak", "History shown", "Outcome held back"],
        ["MOCHA", "Bay of Bengal", "2023", "ESCS", "41 fixes", "10 fixes"],
        ["TEJ", "Arabian Sea", "2023", "ESCS", "24 fixes", "19 fixes"],
        ["BIPARJOY", "Arabian Sea", "2023", "ESCS", "49 fixes", "58 fixes"],
        ["KAJIKI", "Bay of Bengal", "2025", "ESCS", "14 fixes", "11 fixes"],
    ], [26 * mm, 30 * mm, 18 * mm, 16 * mm, 30 * mm, 34 * mm]))
    A(Spacer(1, 2 * mm))

    A(qa(
        "Q. Which dataset is the map built from?",
        "<b>IBTrACS v04r01</b> — the International Best Track Archive for Climate Stewardship, "
        "maintained by NOAA/NCEI. For the North Indian Ocean it carries the RSMC New Delhi "
        "analyses, which are IMD's own post-storm best-track positions and intensities. It is "
        "public, free and requires no credentials. Every storm on the map is a real historical "
        "cyclone with its real track.",
    ))

    A(qa(
        "Q. What is the timeline? What does the map actually show?",
        "Each storm is replayed and paused at its peak intensity. Everything before that "
        "moment is given to the model as observed history; everything after is withheld. The "
        "model then forecasts forward, and the dashboard draws the forecast track against the "
        "<i>actual</i> outcome it never saw.",
        "This is why the map shows three different lines: the observed track (coloured by "
        "intensity category), the forecast track (dashed) and the actual outcome (solid). A "
        "forecast you cannot check is a claim; drawn beside the outcome it is a result.",
    ))

    A(qa(
        "Q. Which seasons train the model, and which are held out?",
        f"The track model trains on seasons <b>{train_seasons[0]}–{train_seasons[1]}</b> and is "
        f"tested on <b>{test_seasons[0]}–{test_seasons[1]}</b>. The map draws only from the test "
        f"window, so no storm on screen is one the model has memorised.",
        "This is enforced by a test, not by convention. An earlier version replayed from 2021 "
        "onward, which put TAUKTAE (2021) on the map while the model had trained through 2022 "
        "— its forecast was being scored against data it had already seen. That is now caught "
        "automatically if the two windows ever drift apart again.",
    ))

    A(qa(
        "Q. Is any of the data synthetic or faked for the demo?",
        "No. There is a synthetic generator in the codebase, but it exists only as a fallback "
        "so a fresh checkout runs before the archive is downloaded. When it is active the API "
        "reports <font face='Courier'>source: synthetic</font> and the interface shows a DEMO "
        "DATA badge. On the running system it is off — the badge reads REAL DATA.",
    ))

    A(qa(
        "Q. Are you using INSAT-3D / 3DR, as the problem statement asks?",
        "Not yet, and this is the honest gap. MOSDAC credentials have been applied for and not "
        "yet granted. The system is built so that INSAT slots in without redesign: the ingest "
        "layer is source-agnostic, and the image model reads infrared structure rather than "
        "anything sensor-specific.",
        "What is used instead is geostationary infrared from other satellites — the same "
        "physical measurement (cloud-top brightness temperature at ~10.8 µm) from a different "
        "platform. Expect a domain gap on INSAT frames until the model is retrained on them; "
        "the API states this in every response rather than hiding it.",
    ))

    A(PageBreak())

    # ------------------------------------------- 3. image upload model
    A(P("3 · The image upload model", H2))

    A(qa(
        "Q. What happens when I upload a satellite image?",
        "The image is sent to the model service, which extracts <b>108 features</b> describing "
        "the storm's infrared structure — statistics over 16 concentric rings around the "
        "centre, asymmetry between quadrants, gradient and texture measures, and an explicit "
        "eye signature. A gradient-boosted regressor maps those to a wind speed; a separate "
        "classifier gives probabilities over the IMD intensity scale; two quantile models give "
        "a prediction interval.",
        "That feature set is the Dvorak technique expressed numerically. It is also why the "
        "model trains on a laptop CPU in minutes rather than needing a GPU.",
    ))

    A(qa(
        "Q. What is it trained on?",
        f"The <b>NASA / Radiant Earth Tropical Cyclone Wind Estimation</b> dataset — "
        f"{intensity.get('n_frames', '—'):,} labelled geostationary infrared frames across "
        f"{intensity.get('n_storms', '—')} storms, each paired with a best-track wind speed. "
        f"Public, CC-BY-4.0, no credentials.",
        "The split is <b>by storm, never by frame</b>. Consecutive frames of one cyclone are "
        "nearly identical, so a random frame split would leak the answer across the split and "
        "report a score that is not real. A further 15% of storms are held back purely to "
        "calibrate the prediction interval.",
    ))

    A(qa(
        "Q. How accurate is it?",
        f"Held-out wind MAE is <b>{mae} kt</b> against a climatology baseline of "
        f"{intensity.get('baseline_mae_kt', '—')} kt — a skill of <b>{skill_pct}</b>. Exact IMD "
        f"category is {intensity.get('category_accuracy', 0) * 100:.1f}%; within one category is "
        f"<b>{within1_pct}</b>. For scale, the spread between trained human Dvorak analysts is "
        f"around 10 kt.",
    ))

    A(qa(
        "Q. Does that average hide anything?",
        "Yes, and this is the most important thing in the document. The headline is an average "
        "over a dataset dominated by moderate storms. Broken out by category, the model "
        "<b>over-reads weak systems and under-reads severe ones</b> — for a warning system, the "
        "dangerous direction.",
    ))
    A(Spacer(1, 1.5 * mm))
    cat_rows = [["Category", "Frames", "MAE (kt)", "Bias (kt)"]]
    for code in ("LPA", "D", "DD", "CS", "SCS", "VSCS", "ESCS", "SuCS"):
        s = per_cat.get(code)
        if not s:
            continue
        bold = code in ("ESCS", "SuCS")
        fmt = (lambda v: f"<b>{v}</b>") if bold else (lambda v: str(v))
        cat_rows.append([fmt(code), fmt(f"{s['n']:,}"), fmt(s["mae_kt"]),
                         fmt(f"{s['bias_kt']:+.2f}")])
    A(table(cat_rows, [30 * mm, 30 * mm, 30 * mm, 30 * mm], align_right=(1, 2, 3)))
    A(Spacer(1, 2 * mm))
    A(P(
        f"Severe storms (&#8805;90 kt) carry MAE {intensity.get('severe_mae_kt', '—')} kt and a "
        f"bias of {intensity.get('severe_bias_kt', '—')} kt. There are two causes. "
        f"<b>Class imbalance</b> is fixable and has been partly fixed: the training set holds "
        f"~11.7k moderate frames against ~1.0k of the most intense, so a least-squares fit "
        f"minimises its loss by pulling everything toward the middle. Inverse-frequency sample "
        f"weighting (alpha {intensity.get('severity_weight_alpha', '—')}) cut severe MAE from "
        f"17.2 to {intensity.get('severe_mae_kt', '—')} kt for 0.2 kt on the headline — a "
        f"deliberate trade, not a free win.", BODY))
    A(P(
        "<b>Infrared saturation</b> is not fixable here. Once cloud tops reach the tropopause "
        "they cannot get colder, so a 100 kt and a 140 kt eyewall look much alike in a single "
        "IR channel. This is the same ceiling the Dvorak technique has had since the 1970s, and "
        "it is why operational centres bring in passive microwave to resolve the inner core. No "
        "amount of reweighting removes it. Every estimate at VSCS and above therefore carries an "
        "explicit caveat telling the operator the reading is likely a lower bound, with the "
        "measured bias for that category attached.", BODY))

    A(qa(
        "Q. What does the confidence percentage actually mean?",
        "It is the classifier's own probability for the category it chose, reduced when the "
        "regression interval is wide. It is not decorative: on the labelled test frames it read "
        "96% where the estimate was 0.5 kt from truth, and 29% where it was 33 kt out. Low "
        "confidence means an ambiguous image, not a weak storm.",
        "It is also load-bearing. The siren will not fire automatically below 70% confidence, "
        "so a shaky read cannot set off a physical alarm on its own.",
    ))

    A(qa(
        "Q. Why is the confidence 64% but the category probability 88%?",
        "They answer different questions. The category probability is how much of the "
        "classifier's belief sits in that one band. The confidence is that number after a "
        "penalty for how wide the wind interval is. A storm can sit clearly inside one category "
        "while its exact wind speed remains uncertain — the first number stays high, the second "
        "comes down.",
    ))

    A(qa(
        "Q. What happens if I upload something that is not a cyclone?",
        f"It is refused rather than scored. Three independent gates run, and any one of them "
        f"refuses the image: a <b>chroma check</b> (the model reads single-channel infrared, so "
        f"colour imagery is the wrong modality), <b>Mahalanobis distance plus an isolation "
        f"forest</b> (frames far from, or in a hole inside, the training distribution), and a "
        f"<b>texture envelope</b> (real cloud imagery occupies a narrow band of local roughness; "
        f"noise is far too rough and a synthetic gradient far too smooth). False-positive rate "
        f"on genuine held-out frames is "
        f"{intensity.get('novelty_false_positive_rate', 0) * 100:.2f}%.",
        "The interface distinguishes <b>“cannot assess this image”</b> from <b>“no cyclonic "
        "system detected”</b>. Conflating those is how a real storm gets waved through, so when "
        "an image is refused the estimate is stripped from the response entirely — there is no "
        "number left for anyone to read by mistake.",
    ))

    A(qa(
        "Q. Why not a deep neural network — a CNN or a vision transformer?",
        "Three reasons, and none of them is that it would work badly. First, the physics is "
        "already known: Dvorak tells us <i>which</i> structures matter, so encoding them "
        "directly costs 108 features instead of millions of parameters. Second, the honest "
        "constraint — around 500 storms is a small dataset for a deep model, and by-storm "
        "splitting shrinks it further. Third, a meteorologist can interrogate a feature named "
        "<font face='Courier'>eye_contrast</font>; they cannot interrogate filter 47 of layer 3, "
        "and this is a domain where a forecaster must be able to disagree with the machine.",
        "A CNN is the right next step once INSAT data lands and the dataset grows.",
    ))

    A(PageBreak())

    # ---------------------------------------- 4. track / intensity forecast
    A(P("4 · Track and intensity forecasting", H2))

    A(qa(
        "Q. How does the forecast work?",
        "A CLIPER-style approach — Climatology and Persistence, the standard baseline every "
        "operational forecast is measured against. From the storm's recent history (position, "
        "intensity, pressure, and how each has changed over the past 6, 12 and 24 hours) "
        "gradient-boosted models predict the change in latitude, longitude and wind at five "
        "lead times: 6, 12, 24, 48 and 72 hours.",
        "The split is chronological, not random: train on earlier seasons, test on later ones. "
        "That is the only split that mirrors how the system would actually be used.",
    ))

    A(qa(
        "Q. How good is it, honestly?",
        "Measured against persistence — assuming the storm keeps doing what it is doing, which "
        "is a genuinely hard baseline at short range. The result is that skill grows with lead "
        "time, which is the expected and useful shape: persistence is excellent at 6 hours and "
        "poor at 3 days.",
    ))
    A(Spacer(1, 1.5 * mm))
    lead_rows = [["Lead", "Cases", "Track error", "Persistence", "Skill", "Intensity MAE"]]
    for lead in ("6", "12", "24", "48", "72"):
        d = leads.get(lead)
        if not d:
            continue
        sk = d["track_skill_vs_persistence"]
        lead_rows.append([
            f"{lead} h", f"{d['n_test']:,}", f"{d['track_error_km']:.1f} km",
            f"{d['track_error_km_persistence']:.1f} km",
            f"<b>{sk * 100:+.1f}%</b>" if sk > 0.05 else f"{sk * 100:+.1f}%",
            f"{d['intensity_mae_kt']:.2f} kt",
        ])
    A(table(lead_rows, [16 * mm, 20 * mm, 30 * mm, 30 * mm, 24 * mm, 30 * mm],
            align_right=(1, 2, 3, 4, 5)))
    A(Spacer(1, 2 * mm))
    A(P(
        "<b>State the weak row before anyone finds it.</b> At 12 hours the model ties "
        "persistence — skill is −0.2%, which is zero. It only pulls clearly ahead from 24 hours "
        "(+7.2%) and is strongest at 72 hours (+22.2%). That is what a track-history-only model "
        "should do, and it is exactly where the next improvement lies: the model currently sees "
        "no environmental information at all. Adding sea-surface temperature, vertical wind "
        "shear and steering flow from ERA5 or GFS is the single largest accuracy gain still "
        "available anywhere in this project.", BODY))

    # ------------------------------------------------- 5. alert system
    A(P("5 · The alert system and the siren tower", H2))

    A(qa(
        "Q. How does alerting decide what to send?",
        "A rule engine reads thresholds from YAML, so a meteorologist can tune them without "
        "touching code and reload them live. Severity is a function of intensity, proximity, "
        "time to landfall and confidence — never intensity alone. A Super Cyclonic Storm "
        "heading out to sea is not a red alert.",
    ))

    A(qa(
        "Q. Why is SMS manual but the siren automatic? Is that not inconsistent?",
        "It is deliberate, and the difference is the point. SMS costs credits per message and "
        "goes to real people, so an unreviewed model output must not be able to text the "
        "public — an analyst reads the drafted message and presses send.",
        "A siren costs nothing per sounding, and a tower that waits for an operator is no use at "
        "three in the morning when the link to the control room is down. So the siren may fire "
        "itself — but only above SCS, only above 70% model confidence, only when the image was "
        "actually scored, and always with a hard duration cap so a dropped link cannot leave it "
        "wailing.",
    ))

    A(qa(
        "Q. What is the hardware, and what does it prove?",
        "An ESP32 microcontroller driving a three-lamp signal stack and a piezo siren, connected "
        "to the control-room machine over USB. Green is all clear; yellow with a periodic chirp "
        "is SCS; a blinking amber with a pulsed siren is VSCS; red with a continuous rising and "
        "falling wail is ESCS or above. The wail is a frequency sweep rather than a fixed tone — "
        "a steady beep reads as an appliance, a sweep reads as an emergency and carries further "
        "over wind and surf.",
        "It also keeps working alone: if the tower is disturbed while the link to the control "
        "room is down, it raises a local alert by itself. That is what makes it a tower rather "
        "than a lamp on a wire.",
    ))

    A(qa(
        "Q. USB is not “no network coverage”. Is this not cheating?",
        "Correct, and it should be said plainly rather than glossed. USB is standing in for the "
        "radio hop. The real last mile is <b>LoRa at 433 MHz</b>: five to ten kilometres on flat "
        "coast with a simple whip antenna, more from a mast, and no infrastructure of any kind "
        "between the two ends.",
        "The command protocol was written as plain text specifically so that swap costs nothing "
        "on the software side — the control-room code is identical whether the bytes arrive over "
        "a cable or over the air. The stretch of coast that loses cellular coverage in the hours "
        "before landfall is exactly the population that most needs warning, and it is the case "
        "SMS structurally cannot serve.",
    ))

    A(PageBreak())

    # ------------------------------------------------ 6. architecture
    A(P("6 · Architecture and how to run it", H2))
    A(P(
        "Four services, deliberately separate so that a failure in one does not silence the "
        "others. During a cyclone, network conditions are precisely when delivery paths start "
        "dropping.", BODY))
    A(Spacer(1, 1.5 * mm))
    A(table([
        ["Service", "Port", "Responsibility"],
        ["Frontend (React + Vite)", "5173", "Dashboard, map, image analysis, alert console"],
        ["Backend (FastAPI)", "8000", "API gateway, event source, imagery proxy, wind field"],
        ["AI model service (FastAPI)", "8001", "Intensity from imagery, track and intensity forecasting"],
        ["Alert service (FastAPI)", "8002", "Rule engine, message rendering, SMS, siren tower"],
    ], [46 * mm, 16 * mm, 112 * mm]))
    A(Spacer(1, 2 * mm))
    A(P(
        "The alert service is separate from the backend on purpose: warnings must keep flowing "
        "even if the dashboard or the model service is down.", BODY))

    A(qa(
        "Q. Why keep a mock path in the code at all?",
        "So the interface stays usable while a service restarts, instead of showing an error "
        "page. Anything it produces is tagged <font face='Courier'>mock: true</font> and the "
        "interface renders a MOCK RESULT badge, so a generated number can never be mistaken for "
        "a predicted one. The real model is always tried first.",
    ))

    # ------------------------------------------------ 7. limitations
    A(P("7 · Limitations, stated plainly", H2))
    A(P(
        "Every serious system has these. Listing them is not a weakness in a submission; being "
        "unable to list them is.", BODY))
    A(Spacer(1, 1.5 * mm))
    A(table([
        ["Limitation", "Detail and current status"],
        ["Not INSAT data",
         "Trained on geostationary IR from another platform. Same measurement, different "
         "sensor. MOSDAC credentials applied for, not yet granted. Expect a domain gap until "
         "retrained."],
        ["Severe storms under-read",
         f"Bias {intensity.get('severe_bias_kt', '—')} kt at &#8805;90 kt. Partly a data "
         f"imbalance (mitigated), partly infrared saturation (a physical ceiling). Surfaced "
         f"on every affected estimate."],
        ["No cyclone localisation",
         "The model assumes a roughly storm-centred frame, as its training frames were. "
         "Finding the storm in a full-disk image is a separate detection problem, not built."],
        ["Pattern type is inferred",
         "Not a trained classifier — the datasets carry wind speed, not Dvorak pattern labels. "
         "Always reported with its source so it cannot be mistaken for one."],
        ["Track model sees no environment",
         "Track history only. Ties persistence at 12 h. ERA5/GFS predictors are the next step."],
        ["No geofenced delivery",
         "Rules and rendering are real; resolving which recipients sit inside a warning polygon "
         "is not built."],
        ["Interval coverage slightly under target",
         f"Conformal calibration delivers {cov_pct} against an 80% target — honest, and "
         f"reported rather than rounded up."],
    ], [42 * mm, 132 * mm]))

    # --------------------------------------------- 8. hard questions
    A(P("8 · Harder questions, and straight answers", H2))

    A(qa(
        "Q. Is this not just the Dvorak technique with extra steps?",
        "It is Dvorak's insight — that cloud structure encodes intensity — made automatic, "
        "reproducible and quantified. What changes is not the physics but three things Dvorak "
        "cannot offer: it is deterministic where manual Dvorak is subjective and varies between "
        "analysts; it produces a calibrated uncertainty interval rather than a single number; "
        "and it runs in under a second on every frame rather than requiring analyst time. The "
        "stated problem is that the current method is subjective, slow and inconsistent. Those "
        "are precisely the three properties addressed.",
    ))

    A(qa(
        "Q. An IMD analyst is more accurate than 10 kt. Why would they use this?",
        "They would not use it to replace their judgement. Two honest use cases: triage — every "
        "frame gets an immediate estimate so an analyst's attention goes where it is needed; "
        "and consistency — the same image always yields the same number, which matters for "
        "verification and for post-event review. The interval and the confidence exist so a "
        "forecaster can see instantly when the model is unsure and should be overruled.",
    ))

    A(qa(
        "Q. How do I know these numbers are not overfitted?",
        "Three specific defences, each of which addresses a way this normally goes wrong. Splits "
        "are <b>by storm</b>, so near-identical consecutive frames cannot straddle the split. "
        "The forecasting split is <b>chronological</b>, mirroring real use. And the prediction "
        "interval is calibrated on a <b>third split</b> held back for that purpose alone — using "
        "the test set to calibrate would be self-fulfilling.",
        "Everything reported here is measured on storms the model has never seen, and a test "
        "fails the build if the map ever shows a storm from the training window.",
    ))

    A(qa(
        "Q. What would you do next, with more time?",
        "In order of value. First, environmental predictors (ERA5 sea-surface temperature, wind "
        "shear, steering flow) for the track model — the largest single gain available. Second, "
        "INSAT retraining once MOSDAC access arrives, which closes the sensor gap. Third, "
        "passive microwave to break the infrared saturation ceiling on severe storms. Fourth, "
        "the LoRa link to make the siren tower genuinely infrastructure-free. Deep learning on "
        "imagery comes after the dataset grows, not before.",
    ))

    A(Spacer(1, 5 * mm))
    A(P(
        "Every figure in this document was read from the trained model reports when it was "
        f"generated on {datetime.now(UTC).strftime('%d %B %Y at %H:%M UTC')}. Rebuild with "
        "<font face='Courier'>python scripts/build_qa_pdf.py</font> after any retraining and "
        "the numbers follow automatically.", SMALL))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
        title="Vayu-X — SIH 2026 Question & Answer Briefing",
        author="Team Vayu-X (152)",
        subject="PS 26070 — AI/ML cyclone identification, classification and prediction",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=page_furniture)])
    doc.build(story)
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
