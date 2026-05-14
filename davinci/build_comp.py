#!/usr/bin/env python3
"""
Builds Mindheist_Launch.comp — a DaVinci Resolve Fusion composition file
re-creating the 7-scene noir launch video as a node graph that can be
imported into DaVinci Resolve and tweaked freely.

Run:   python3 build_comp.py
Output: Mindheist_Launch.comp  (next to this script)

Spec : 1920x1080, 30 fps, 175 s (5250 frames).
       Frame range and fps are emitted into the comp — you can change
       project fps in Resolve later; keyframe times stay where they are.
"""
from __future__ import annotations
from textwrap import indent
import os

# ── canvas / timing ────────────────────────────────────────────────────────
FPS         = 30
DURATION_S  = 175
FRAMES      = FPS * DURATION_S         # 5250
W, H        = 1920, 1080

# ── NOIR palette (Fusion uses 0-1 RGB) ─────────────────────────────────────
INK         = (0.0392, 0.0314, 0.0196)   # #0a0805
INK2        = (0.0824, 0.0667, 0.0392)   # #15110a
PAPER       = (0.9373, 0.9098, 0.8392)   # #efe8d6
PAPER_DARK  = (0.8510, 0.8196, 0.7333)   # #d9d1bb
PAPER_EDGE  = (0.7412, 0.7020, 0.6039)   # #bdb39a
RED         = (0.7804, 0.2431, 0.1843)   # ~ oklch(58% 0.18 25)
RED_DEEP    = (0.5490, 0.1647, 0.1216)
AMBER       = (0.8784, 0.6510, 0.3529)   # ~ oklch(78% 0.14 70)
AMBER_DIM   = (0.6275, 0.4784, 0.2078)
REDACT      = (0.1020, 0.0863, 0.0667)
ASH         = (0.4784, 0.4431, 0.3725)
TAPE_YELLOW = (0.8863, 0.6706, 0.0941)   # crime tape

# ── fonts (must be installed on the OS for Fusion to render) ───────────────
F_DISPLAY = "Anton"
F_COND    = "Oswald"
F_SERIF   = "Playfair Display"
F_TYPE    = "Special Elite"
F_MONO    = "IBM Plex Mono"

# ── scene starts in frames ─────────────────────────────────────────────────
S = {1: 0, 2: 600, 3: 1350, 4: 2100, 5: 2850, 6: 3450, 7: 4350, "end": FRAMES}

# ── helpers ────────────────────────────────────────────────────────────────
_tool_pos_y = 0  # ViewInfo position counter for layout in the node graph

tools: list[str] = []
spline_id = 0

def tool(name: str, body: str, x: int = 0) -> str:
    """Register a top-level tool. Auto-assigns a ViewInfo pos."""
    global _tool_pos_y
    pos_y = _tool_pos_y
    _tool_pos_y += 1
    tools.append(f"""\
        {name} = {body.rstrip()},
            ViewInfo = OperatorInfo {{ Pos = {{ {x*220.0}, {pos_y*40.0} }} }}
        }},""")
    return name

def spline(keys: list[tuple[int, float]]) -> str:
    """Create a BezierSpline tool and return its node name."""
    global spline_id
    spline_id += 1
    name = f"Spline{spline_id}"
    rows = ",\n".join(
        f"                [{f}] = {{ {v}, RH = {{ {f+5}, {v} }}, LH = {{ {f-5}, {v} }}, Flags = {{ Linear = true }} }}"
        for f, v in keys
    )
    body = f"""BezierSpline {{
            SplineColor = {{ Red = 255, Green = 128, Blue = 0 }},
            NameSet = true,
            KeyFrames = {{
{rows}
            }}
        """
    tool(name, body, x=10)
    return name

def anim(default: float, keys: list[tuple[int, float]]) -> str:
    """Return an Input { } line that animates via a new BezierSpline."""
    s = spline(keys)
    return f'Input {{ Value = {default}, SourceOp = "{s}", Source = "Value" }}'

def fade_in(start: int, dur: int = 9) -> str:
    """0 → 1 fade over `dur` frames starting at `start`."""
    return anim(0, [(start, 0.0), (start + dur, 1.0)])

def fade_out(end: int, dur: int = 9) -> str:
    """1 → 0 fade ending at `end`."""
    return anim(0, [(end - dur, 1.0), (end, 0.0)])

def fade_in_out(start: int, end: int, in_dur: int = 9, out_dur: int = 12) -> str:
    """Hold 0, ramp to 1 at start, hold, ramp back to 0 at end."""
    return anim(0, [
        (start - 1, 0.0),
        (start + in_dur, 1.0),
        (end - out_dur, 1.0),
        (end, 0.0),
    ])

def text_plus(name: str, text: str, font: str = F_DISPLAY,
              style: str = "Regular",
              size: float = 0.06,
              color = PAPER,
              center = (0.5, 0.5),
              line_spacing: float = 1.0,
              h_just: str = "Center",
              v_just: str = "Center",
              global_in: int = 0,
              global_out: int = FRAMES - 1,
              blend = None,
              x: int = 0,
              extra: str = "",
              angle: float = 0.0) -> str:
    """Add a TextPlus tool with sensible defaults."""
    r, g, b = color
    blend_in = blend if blend else "Input { Value = 1, }"
    # Escape backslashes and quotes in the styled text
    encoded = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    body = f"""TextPlus {{
            CtrlWZoom = false,
            Inputs = {{
                GlobalIn = Input {{ Value = {global_in}, }},
                GlobalOut = Input {{ Value = {global_out}, }},
                Width = Input {{ Value = {W}, }},
                Height = Input {{ Value = {H}, }},
                UseFrameFormatSettings = Input {{ Value = 1, }},
                ["Gamut.SLogVersion"] = Input {{ Value = FuID {{ "SLog2" }}, }},
                LayoutRotation = Input {{ Value = 1, }},
                TransformRotation = Input {{ Value = 1, }},
                Center = Input {{ Value = {{ {center[0]}, {center[1]} }}, }},
                StyledText = Input {{ Value = "{encoded}", }},
                Font = Input {{ Value = "{font}", }},
                Style = Input {{ Value = "{style}", }},
                Size = Input {{ Value = {size}, }},
                VerticalJustificationNew = Input {{ Value = 1, }},
                HorizontalJustificationNew = Input {{ Value = 0, }},
                LineSpacingClamp = Input {{ Value = 1, }},
                LineSpacing = Input {{ Value = {line_spacing}, }},
                Red1 = Input {{ Value = {r}, }},
                Green1 = Input {{ Value = {g}, }},
                Blue1 = Input {{ Value = {b}, }},
                ManualFontKerningPlacement = Input {{ Value = {{}}, }},
                Blend = {blend_in},
                Angle = Input {{ Value = {angle}, }},
                {extra}
            }}
        """
    return tool(name, body, x)

def background(name: str, color, size = (1.0, 1.0), center = (0.5, 0.5),
               global_in: int = 0, global_out: int = FRAMES - 1,
               blend = None, x: int = 0, mask = None,
               width: int = W, height: int = H, angle: float = 0.0) -> str:
    r, g, b = color
    blend_in = blend if blend else "Input { Value = 1, }"
    mask_line = ""
    if mask:
        mask_line = f'EffectMask = Input {{ SourceOp = "{mask}", Source = "Mask" }},'
    body = f"""Background {{
            CtrlWZoom = false,
            Inputs = {{
                GlobalIn = Input {{ Value = {global_in}, }},
                GlobalOut = Input {{ Value = {global_out}, }},
                Width = Input {{ Value = {width}, }},
                Height = Input {{ Value = {height}, }},
                UseFrameFormatSettings = Input {{ Value = 1, }},
                ["Gamut.SLogVersion"] = Input {{ Value = FuID {{ "SLog2" }}, }},
                Type = Input {{ Value = 0, }},
                TopLeftRed = Input {{ Value = {r}, }},
                TopLeftGreen = Input {{ Value = {g}, }},
                TopLeftBlue = Input {{ Value = {b}, }},
                TopLeftAlpha = Input {{ Value = 1, }},
                Blend = {blend_in},
                {mask_line}
            }}
        """
    return tool(name, body, x)

def rect_mask(name: str, w: float, h: float, center = (0.5, 0.5),
              solid: int = 1, border: float = 0.0,
              global_in: int = 0, global_out: int = FRAMES - 1,
              x: int = 0, angle: float = 0.0) -> str:
    body = f"""RectangleMask {{
            CtrlWZoom = false,
            Inputs = {{
                Filter = Input {{ Value = FuID {{ "Fast Gaussian" }}, }},
                MaskWidth = Input {{ Value = {W}, }},
                MaskHeight = Input {{ Value = {H}, }},
                PixelAspect = Input {{ Value = {{ 1, 1 }}, }},
                ClippingMode = Input {{ Value = FuID {{ "None" }}, }},
                Center = Input {{ Value = {{ {center[0]}, {center[1]} }}, }},
                Width = Input {{ Value = {w}, }},
                Height = Input {{ Value = {h}, }},
                Angle = Input {{ Value = {angle}, }},
                BorderWidth = Input {{ Value = {border}, }},
                Solid = Input {{ Value = {solid}, }},
                GlobalIn = Input {{ Value = {global_in}, }},
                GlobalOut = Input {{ Value = {global_out}, }},
            }}
        """
    return tool(name, body, x)

def transform(name: str, src: str, center = (0.5, 0.5),
              size: float = 1.0, angle: float = 0.0,
              global_in: int = 0, global_out: int = FRAMES - 1,
              size_anim = None, center_x_anim = None, center_y_anim = None,
              angle_anim = None, x: int = 0) -> str:
    size_in   = size_anim if size_anim else f"Input {{ Value = {size}, }}"
    angle_in  = angle_anim if angle_anim else f"Input {{ Value = {angle}, }}"
    if center_x_anim or center_y_anim:
        # If we need to animate just one axis, use a XYPath
        cx = center_x_anim if center_x_anim else f"Input {{ Value = {center[0]}, }}"
        cy = center_y_anim if center_y_anim else f"Input {{ Value = {center[1]}, }}"
        center_block = f"Center = Input {{ Value = {{ {center[0]}, {center[1]} }}, }}"
        # Use Path for animated center
    else:
        center_block = f"Center = Input {{ Value = {{ {center[0]}, {center[1]} }}, }}"
    body = f"""Transform {{
            CtrlWZoom = false,
            Inputs = {{
                GlobalIn = Input {{ Value = {global_in}, }},
                GlobalOut = Input {{ Value = {global_out}, }},
                Input = Input {{ SourceOp = "{src}", Source = "Output", }},
                {center_block},
                Size = {size_in},
                Angle = {angle_in},
                FlattenTransform = Input {{ Value = 0, }},
            }}
        """
    return tool(name, body, x)

# Merge stack — chained into a single output
merge_chain: list[str] = []
def merge(fg: str, name: str | None = None, op: int = 0,
          x: int = 5) -> str:
    """Add a Merge node on top of the running chain."""
    global merge_chain
    if name is None:
        name = f"M{len(merge_chain)+1:03d}"
    bg = merge_chain[-1] if merge_chain else None
    bg_line = f'Background = Input {{ SourceOp = "{bg}", Source = "Output", }},' if bg else ""
    body = f"""Merge {{
            CtrlWZoom = false,
            Inputs = {{
                {bg_line}
                Foreground = Input {{ SourceOp = "{fg}", Source = "Output", }},
                PerformDepthMerge = Input {{ Value = 0, }},
                Operator = Input {{ Value = {op}, }},
            }}
        """
    tool(name, body, x)
    merge_chain.append(name)
    return name

# ═══════════════════════════════════════════════════════════════════════════
# 0. Master background (ink black, full duration)
# ═══════════════════════════════════════════════════════════════════════════
master = background("Master_BG", INK, x=0)
merge_chain.append(master)

# ═══════════════════════════════════════════════════════════════════════════
# SCENE 1 — Problem  (frames 0–600)
# ═══════════════════════════════════════════════════════════════════════════
S1, S1e = S[1], S[2]

# faint CCTV background overlay
s1_cctv = background("S1_CCTV_Tone", INK2, global_in=S1, global_out=S1+255,
                     blend=fade_in_out(S1+6, S1+255, 12, 18))
merge(s1_cctv)

s1_cam_hud = text_plus("S1_Cam_HUD",
    "CAM-04B  •  FEED LIVE  •  AUDIO MUTED",
    font=F_MONO, size=0.0145, color=RED,
    center=(0.18, 0.92),
    global_in=S1+12, global_out=S1+255,
    blend=fade_in_out(S1+12, S1+255, 9, 15))
merge(s1_cam_hud)

s1_subjects = text_plus("S1_Subjects",
    "SUBJECTS: 28  •  ENGAGED: 7",
    font=F_MONO, size=0.0145, color=PAPER,
    center=(0.82, 0.92),
    global_in=S1+12, global_out=S1+255,
    blend=fade_in_out(S1+12, S1+255, 9, 15))
merge(s1_subjects)

# Crime scene tape — wide yellow band sweeping across, rotated -7°
s1_tape_bg = background("S1_Tape_BG", TAPE_YELLOW,
    width=2600, height=88,
    global_in=S1+36, global_out=S1+600,
    blend=fade_out(S1+600, 18))
s1_tape_text = text_plus("S1_Tape_Text",
    "DO NOT CROSS  •  EVIDENCE  •  DO NOT CROSS  •  EVIDENCE  •  DO NOT CROSS  •  EVIDENCE",
    font=F_DISPLAY, size=0.045, color=INK,
    center=(0.5, 0.518),
    global_in=S1+36, global_out=S1+600,
    blend=fade_out(S1+600, 18))
# Sweep transform — slide from off-screen left to centered
sweep_x = anim(-1.0, [(S1+36, -0.6), (S1+66, 0.5)])
s1_tape_merge = merge(s1_tape_bg, name="S1_Tape_BG_M")
s1_tape_t = transform("S1_Tape_BG_T", s1_tape_bg,
    center=(0.5, 0.518), size=1.0, angle=-7.0,
    center_x_anim=sweep_x,
    global_in=S1+36, global_out=S1+600)
# replace last bg-only merge with transformed
merge_chain.pop()  # remove tape bg from chain
merge(s1_tape_t)
merge(s1_tape_text)

# Stat 1 — 73 % zone out
s1_stat73_num = text_plus("S1_Stat73_Num",
    "73", font=F_DISPLAY, size=0.30, color=PAPER,
    center=(0.18, 0.42),
    global_in=S1+78, global_out=S1+315,
    blend=fade_in_out(S1+78, S1+315, 12, 18))
s1_stat73_pct = text_plus("S1_Stat73_Pct",
    "%", font=F_DISPLAY, size=0.135, color=RED,
    center=(0.305, 0.46),
    global_in=S1+78, global_out=S1+315,
    blend=fade_in_out(S1+78, S1+315, 12, 18))
s1_stat73_lbl = text_plus("S1_Stat73_Lbl",
    "OF STUDENTS ZONE OUT IN CLASS",
    font=F_COND, style="Bold", size=0.022, color=PAPER,
    center=(0.245, 0.27),
    global_in=S1+78, global_out=S1+315,
    blend=fade_in_out(S1+78, S1+315, 12, 18))
s1_stat73_src = text_plus("S1_Stat73_Src",
    "SOURCE: EDTECH 2024 STUDY  •  UNIVERSITY OF CHICAGO",
    font=F_MONO, size=0.012, color=PAPER,
    center=(0.245, 0.075),
    global_in=S1+78, global_out=S1+315,
    blend=fade_in_out(S1+78, S1+315, 12, 18))
# red underline bar — animated width
s1_under1_w = anim(0.0, [(S1+96, 0.0), (S1+128, 0.32)])
s1_under1 = background("S1_Under73", RED,
    width=W, height=H,
    global_in=S1+78, global_out=S1+315,
    blend=fade_in_out(S1+78, S1+315, 12, 18))
s1_under1_mask = rect_mask("S1_Under73_Mask",
    w=anim(0.32, [(S1+96, 0.0), (S1+128, 0.32)]) if False else 0.32,
    h=0.008, center=(0.245, 0.31),
    global_in=S1+78, global_out=S1+315)
# (the mask is static — width animation requires a path; we keep simple)
s1_under1m = background("S1_Under73_C", RED,
    global_in=S1+78, global_out=S1+315,
    blend=fade_in_out(S1+78, S1+315, 12, 18),
    mask=s1_under1_mask)

merge(s1_stat73_num)
merge(s1_stat73_pct)
merge(s1_stat73_lbl)
merge(s1_under1m)
merge(s1_stat73_src)

# Stamp ZONED OUT — punches in with scale overshoot + rotation
zoned_scale = anim(1.6, [(S1+120, 1.6), (S1+128, 1.05), (S1+135, 1.0)])
s1_stamp1_main = text_plus("S1_Stamp1_Tx",
    "ZONED OUT", font=F_DISPLAY, size=0.085, color=RED,
    center=(0.62, 0.62),
    global_in=S1+120, global_out=S1+315,
    blend=fade_in_out(S1+120, S1+315, 6, 12),
    angle=-9.0)
s1_stamp1_sub = text_plus("S1_Stamp1_Sub",
    "EXHIBIT  A", font=F_MONO, size=0.018, color=RED,
    center=(0.62, 0.555),
    global_in=S1+120, global_out=S1+315,
    blend=fade_in_out(S1+120, S1+315, 6, 12),
    angle=-9.0)
s1_stamp1_t = transform("S1_Stamp1_T", s1_stamp1_main,
    center=(0.62, 0.62),
    size_anim=zoned_scale,
    global_in=S1+120, global_out=S1+315)
merge(s1_stamp1_t)
merge(s1_stamp1_sub)

# Hard cut transition flash at frame 315
s1_flash = background("S1_Flash", (0, 0, 0),
    global_in=S1+309, global_out=S1+321,
    blend=anim(0, [(S1+309, 0.0), (S1+312, 0.85), (S1+321, 0.0)]))
merge(s1_flash)

# Stat 2 — 87 % schools ban cloud apps
s1_stat87_num = text_plus("S1_Stat87_Num",
    "87", font=F_DISPLAY, size=0.275, color=PAPER,
    center=(0.62, 0.55),
    global_in=S1+318, global_out=S1+594,
    blend=fade_in_out(S1+318, S1+594, 12, 18))
s1_stat87_pct = text_plus("S1_Stat87_Pct",
    "%", font=F_DISPLAY, size=0.122, color=RED,
    center=(0.74, 0.59),
    global_in=S1+318, global_out=S1+594,
    blend=fade_in_out(S1+318, S1+594, 12, 18))
s1_stat87_lbl = text_plus("S1_Stat87_Lbl",
    "OF SCHOOLS BAN CLOUD APPS",
    font=F_COND, style="Bold", size=0.022, color=PAPER,
    center=(0.68, 0.40),
    global_in=S1+318, global_out=S1+594,
    blend=fade_in_out(S1+318, S1+594, 12, 18))
s1_stat87_quote = text_plus("S1_Stat87_Quote",
    "\"Passive learning doesn't stick.\\nCloud apps don't stick either.\"".replace("\\n", "\n"),
    font=F_SERIF, style="Italic", size=0.034, color=PAPER,
    center=(0.68, 0.22), line_spacing=1.25,
    global_in=S1+318, global_out=S1+594,
    blend=fade_in_out(S1+318, S1+594, 12, 18))
s1_stat87_src = text_plus("S1_Stat87_Src",
    "SOURCE: EDSURGE, 2025  •  K-12 PRIVACY REVIEW",
    font=F_MONO, size=0.012, color=PAPER,
    center=(0.68, 0.075),
    global_in=S1+318, global_out=S1+594,
    blend=fade_in_out(S1+318, S1+594, 12, 18))
# School network placeholder
s1_net_box = background("S1_NetBox", REDACT,
    width=620, height=520,
    global_in=S1+318, global_out=S1+594,
    blend=fade_in_out(S1+318, S1+594, 12, 18))
s1_net_box_mask = rect_mask("S1_NetBox_M", w=0.323, h=0.482,
    center=(0.215, 0.42),
    global_in=S1+318, global_out=S1+594)
s1_net_box_m = background("S1_NetBox_C", REDACT,
    global_in=S1+318, global_out=S1+594,
    blend=fade_in_out(S1+318, S1+594, 12, 18),
    mask=s1_net_box_mask)
s1_net_lbl = text_plus("S1_NetLbl", "SCHOOL NETWORK",
    font=F_MONO, size=0.014, color=ASH,
    center=(0.215, 0.45),
    global_in=S1+318, global_out=S1+594,
    blend=fade_in_out(S1+318, S1+594, 12, 18))
merge(s1_net_box_m)
merge(s1_net_lbl)
merge(s1_stat87_num)
merge(s1_stat87_pct)
merge(s1_stat87_lbl)
merge(s1_stat87_quote)
merge(s1_stat87_src)

# BANNED stamp — punches in
banned_scale = anim(1.8, [(S1+360, 1.8), (S1+368, 1.05), (S1+375, 1.0)])
s1_banned = text_plus("S1_Banned",
    "BANNED", font=F_DISPLAY, size=0.115, color=RED,
    center=(0.30, 0.50),
    global_in=S1+360, global_out=S1+594,
    blend=fade_in_out(S1+360, S1+594, 6, 12),
    angle=-6.0)
s1_banned_sub = text_plus("S1_Banned_Sub",
    "ALL  DISTRICTS", font=F_MONO, size=0.018, color=RED,
    center=(0.30, 0.43),
    global_in=S1+360, global_out=S1+594,
    blend=fade_in_out(S1+360, S1+594, 6, 12),
    angle=-6.0)
s1_banned_t = transform("S1_Banned_T", s1_banned,
    center=(0.30, 0.50),
    size_anim=banned_scale,
    global_in=S1+360, global_out=S1+594)
merge(s1_banned_t)
merge(s1_banned_sub)

# Scene slug + REC HUD overlays
s1_slug = text_plus("S1_Slug",
    "—— EVIDENCE  No 001  —  THE BORED LEARNER",
    font=F_MONO, size=0.013, color=PAPER,
    center=(0.22, 0.94),
    global_in=S1, global_out=S1e-1,
    blend=fade_in_out(S1+6, S1e-1, 12, 18))
merge(s1_slug)

# ═══════════════════════════════════════════════════════════════════════════
# SCENE 2 — Solution Hook  (frames 600–1350)
# ═══════════════════════════════════════════════════════════════════════════
S2, S2e = S[2], S[3]

# Notes paper — drifts in from right, holds, then exits
s2_paper = background("S2_Paper", PAPER,
    width=720, height=760,
    global_in=S2+6, global_out=S2+870,
    blend=fade_in_out(S2+6, S2+870, 9, 15))
paper_x = anim(0.68, [(S2+6, 0.95), (S2+30, 0.32)])
s2_paper_mask = rect_mask("S2_Paper_M", w=0.375, h=0.704,
    center=(0.32, 0.53), angle=-2.5,
    global_in=S2+6, global_out=S2+870)
s2_paper_c = background("S2_Paper_C", PAPER,
    global_in=S2+6, global_out=S2+870,
    blend=fade_in_out(S2+6, S2+870, 9, 15),
    mask=s2_paper_mask)
merge(s2_paper_c)

# Note header (Algebra II — Mr. Halloran)
s2_n_h = text_plus("S2_N_H", "Algebra II — Mr. Halloran",
    font=F_SERIF, style="Bold", size=0.028, color=INK,
    center=(0.32, 0.79),
    global_in=S2+12, global_out=S2+870,
    blend=fade_in_out(S2+12, S2+870, 6, 15),
    angle=-2.5)
merge(s2_n_h)

# Note math lines — stagger in (handwritten typewriter feel)
for i, line in enumerate([
    "Suspect A leaves 7:42 PM",
    "Train: 38 mph  •  d = 4.5 mi",
    "t  =  d / v  =  4.5 / 38",
    "    =  0.1184 h  ~~  7 min 6s",
    "Arrives 7:49 PM ✗",
    "...alibi says 7:45 PM ???",
]):
    in_f = S2+24 + i*12
    n = text_plus(f"S2_N_L{i}", line,
        font=F_TYPE, size=0.022, color=INK,
        center=(0.32, 0.72 - i*0.05),
        global_in=in_f, global_out=S2+870,
        blend=fade_in_out(in_f, S2+870, 4, 15),
        angle=-2.5)
    merge(n)

# Right-side caption: "We were stuck in boring classes..."
s2_cap = text_plus("S2_Cap",
    "We were stuck in boring classes...\nso we built a way out.",
    font=F_SERIF, style="Italic", size=0.034, color=PAPER,
    center=(0.78, 0.72), line_spacing=1.25,
    global_in=S2+42, global_out=S2+855,
    blend=fade_in_out(S2+42, S2+855, 18, 24))
merge(s2_cap)

# Viewfinder reticle (red brackets) appearing while camera frames the notes
for i, (cx, cy) in enumerate([(0.18, 0.78), (0.52, 0.78), (0.18, 0.20), (0.52, 0.20)]):
    bm = rect_mask(f"S2_VF_Mask{i}", w=0.032, h=0.055,
        center=(cx, cy), border=0.0027, solid=0,
        global_in=S2+195, global_out=S2+315)
    bb = background(f"S2_VF{i}", RED,
        global_in=S2+195, global_out=S2+315,
        blend=fade_in_out(S2+195, S2+315, 9, 15),
        mask=bm)
    merge(bb)
# Shutter flash @ S2+249 (S2 8.3s relative not 1.8 — placed within VF window)
s2_flash = background("S2_Flash", (1, 1, 1),
    global_in=S2+249, global_out=S2+258,
    blend=anim(0, [(S2+249, 0.0), (S2+251, 0.95), (S2+258, 0.0)]))
merge(s2_flash)

# Clue card panel — flies in from top, lands at slight angle
s2_clue_bg = background("S2_Clue_BG", INK2,
    width=760, height=580,
    global_in=S2+300, global_out=S2+735,
    blend=fade_in_out(S2+300, S2+735, 12, 18))
clue_y = anim(1.2, [(S2+300, 1.2), (S2+321, 0.52)])
s2_clue_mask = rect_mask("S2_Clue_Mask", w=0.397, h=0.537,
    center=(0.625, 0.48), angle=-3.5,
    global_in=S2+300, global_out=S2+735)
s2_clue_c = background("S2_Clue_C", INK2,
    global_in=S2+300, global_out=S2+735,
    blend=fade_in_out(S2+300, S2+735, 12, 18),
    mask=s2_clue_mask)
merge(s2_clue_c)

s2_clue_kicker = text_plus("S2_Clue_Kicker",
    "CASE  •  THE 7:45 ALIBI",
    font=F_MONO, size=0.012, color=RED,
    center=(0.625, 0.68),
    global_in=S2+312, global_out=S2+735,
    blend=fade_in_out(S2+312, S2+735, 9, 15),
    angle=-3.5)
s2_clue_h = text_plus("S2_Clue_H",
    "THE SUSPECT'S\nALIBI IS WRONG.",
    font=F_DISPLAY, size=0.046, color=PAPER,
    center=(0.625, 0.56), line_spacing=0.95,
    global_in=S2+324, global_out=S2+735,
    blend=fade_in_out(S2+324, S2+735, 9, 15),
    angle=-3.5)
s2_clue_b = text_plus("S2_Clue_B",
    "The math doesn't add up. A train at 38 mph\ncannot cover 4.5 miles in 3 minutes.\nWhere was Suspect A really at 7:45?",
    font=F_SERIF, style="Italic", size=0.020, color=PAPER,
    center=(0.625, 0.40), line_spacing=1.3,
    global_in=S2+342, global_out=S2+735,
    blend=fade_in_out(S2+342, S2+735, 9, 15),
    angle=-3.5)
merge(s2_clue_kicker)
merge(s2_clue_h)
merge(s2_clue_b)

# Gemma 4 tag — small mono badge
s2_tag = text_plus("S2_Tag",
    "GEMMA 4  •  LOCAL MULTIMODAL AI",
    font=F_MONO, size=0.018, color=RED,
    center=(0.25, 0.18),
    global_in=S2+345, global_out=S2+555,
    blend=fade_in_out(S2+345, S2+555, 9, 15))
s2_tag_sub = text_plus("S2_Tag_Sub",
    "OLLAMA  •  M4 MAX  •  ON-DEVICE",
    font=F_MONO, size=0.013, color=PAPER,
    center=(0.55, 0.18),
    global_in=S2+345, global_out=S2+555,
    blend=fade_in_out(S2+345, S2+555, 9, 15))
merge(s2_tag)
merge(s2_tag_sub)

# MINDHEIST wordmark slam — fade-in dark overlay + huge title
s2_mh_dim = background("S2_MH_Dim", INK,
    global_in=S2+570, global_out=S2+750,
    blend=anim(0, [(S2+570, 0.0), (S2+580, 0.78), (S2+742, 0.78), (S2+750, 0.0)]))
merge(s2_mh_dim)
mh_scale_2 = anim(1.25, [(S2+570, 1.25), (S2+585, 1.05), (S2+595, 1.0)])
s2_mh_kicker = text_plus("S2_MH_Kicker",
    "INTRODUCING",
    font=F_MONO, size=0.018, color=RED,
    center=(0.5, 0.78),
    global_in=S2+570, global_out=S2+750,
    blend=fade_in_out(S2+570, S2+750, 9, 15))
s2_mh_title = text_plus("S2_MH_Title",
    "MINDHEIST", font=F_DISPLAY, size=0.30, color=PAPER,
    center=(0.5, 0.52),
    global_in=S2+570, global_out=S2+750,
    blend=fade_in_out(S2+570, S2+750, 9, 15))
s2_mh_title_t = transform("S2_MH_Title_T", s2_mh_title,
    center=(0.5, 0.52), size_anim=mh_scale_2,
    global_in=S2+570, global_out=S2+750)
s2_mh_sub = text_plus("S2_MH_Sub",
    "where your notes become a mystery.",
    font=F_SERIF, style="Italic", size=0.030, color=PAPER,
    center=(0.5, 0.28),
    global_in=S2+570, global_out=S2+750,
    blend=fade_in_out(S2+585, S2+750, 9, 15))
merge(s2_mh_kicker)
merge(s2_mh_title_t)
merge(s2_mh_sub)

s2_slug = text_plus("S2_Slug",
    "—— CASE  No 002  —  THE ALIBI",
    font=F_MONO, size=0.013, color=PAPER,
    center=(0.22, 0.94),
    global_in=S2, global_out=S2e-1,
    blend=fade_in_out(S2+6, S2e-1, 12, 18))
merge(s2_slug)

# ═══════════════════════════════════════════════════════════════════════════
# SCENE 3 — Tech Demo  (frames 1350–2100)
# ═══════════════════════════════════════════════════════════════════════════
S3, S3e = S[3], S[4]

# Terminal window background
s3_term_mask = rect_mask("S3_Term_Mask", w=0.563, h=0.574,
    center=(0.343, 0.48),
    global_in=S3, global_out=S3+435)
s3_term = background("S3_Term", INK,
    global_in=S3, global_out=S3+435,
    blend=fade_in_out(S3, S3+435, 12, 18),
    mask=s3_term_mask)
s3_term_bar_mask = rect_mask("S3_TermBar_Mask", w=0.563, h=0.0352,
    center=(0.343, 0.751),
    global_in=S3, global_out=S3+435)
s3_term_bar = background("S3_TermBar", INK2,
    global_in=S3, global_out=S3+435,
    blend=fade_in_out(S3, S3+435, 12, 18),
    mask=s3_term_bar_mask)
merge(s3_term)
merge(s3_term_bar)

# Title bar dot — red/amber/green
for i, c in enumerate([RED, AMBER_DIM, (0.227, 0.541, 0.333)]):
    dm = rect_mask(f"S3_Dot{i}_M", w=0.0052, h=0.0093,
        center=(0.084 + i*0.012, 0.751),
        global_in=S3, global_out=S3+435)
    db = background(f"S3_Dot{i}", c,
        global_in=S3, global_out=S3+435,
        blend=fade_in_out(S3+3, S3+435, 9, 15),
        mask=dm)
    merge(db)
s3_term_title = text_plus("S3_TermTitle",
    "terminal — ~/mindheist  •  zsh",
    font=F_MONO, size=0.011, color=PAPER,
    center=(0.20, 0.751),
    global_in=S3, global_out=S3+435,
    blend=fade_in_out(S3+3, S3+435, 9, 15))
merge(s3_term_title)

# Terminal prompt + command (typewriter via Write On animation)
s3_cmd = text_plus("S3_Cmd",
    "$  ollama run gemma4-turbo --multimodal --local",
    font=F_MONO, size=0.018, color=PAPER,
    center=(0.343, 0.71),
    global_in=S3+12, global_out=S3+435,
    blend=fade_in_out(S3+15, S3+435, 6, 15),
    extra='WriteOnEnd = ' + anim(0, [(S3+15, 0.0), (S3+72, 1.0), (S3+435, 1.0)]) + ',',
    h_just="Left")
merge(s3_cmd)

# Terminal output lines — pop in sequentially
for i, line in enumerate([
    "* loading model gemma4-turbo (4.7B params)",
    "* device: Apple M4 Max  *  16 GB unified",
    "* vision encoder: ready",
    "* audio encoder: ready",
    "v model up  *  context 128k  *  no network calls",
    ">>> awaiting input...",
]):
    in_f = S3+96 + i*15
    color = (0.494, 0.776, 0.608) if line.startswith("v") else (AMBER if line.startswith(">>>") else PAPER)
    n = text_plus(f"S3_Out{i}", line,
        font=F_MONO, size=0.018, color=color,
        center=(0.343, 0.65 - i*0.035),
        global_in=in_f, global_out=S3+435,
        blend=fade_in_out(in_f, S3+435, 5, 15),
        h_just="Left")
    merge(n)

# Side caption — RUNS LOCALLY
s3_rl_k = text_plus("S3_RL_Kicker",
    "THE TOOL — GEMMA 4",
    font=F_MONO, size=0.016, color=RED,
    center=(0.78, 0.74),
    global_in=S3+96, global_out=S3+435,
    blend=fade_in_out(S3+96, S3+435, 12, 15))
s3_rl_h = text_plus("S3_RL_Headline",
    "RUNS\nLOCALLY.",
    font=F_DISPLAY, size=0.12, color=PAPER,
    center=(0.78, 0.55), line_spacing=0.85,
    global_in=S3+96, global_out=S3+435,
    blend=fade_in_out(S3+96, S3+435, 12, 15))
# red underline accent
s3_rl_under_m = rect_mask("S3_RL_Under_M", w=0.167, h=0.0074,
    center=(0.78, 0.39),
    global_in=S3+96, global_out=S3+435)
s3_rl_under = background("S3_RL_Under", RED,
    global_in=S3+96, global_out=S3+435,
    blend=fade_in_out(S3+105, S3+435, 9, 15),
    mask=s3_rl_under_m)
s3_rl_sub = text_plus("S3_RL_Sub",
    "No cloud. No API key.\nNo data leaves your device.",
    font=F_SERIF, style="Italic", size=0.026, color=PAPER,
    center=(0.78, 0.30), line_spacing=1.3,
    global_in=S3+96, global_out=S3+435,
    blend=fade_in_out(S3+108, S3+435, 12, 15))
merge(s3_rl_k)
merge(s3_rl_h)
merge(s3_rl_under)
merge(s3_rl_sub)

# Pipeline diagram (after terminal exit)
PIPELINE_BASE = S3+438  # ~14.6s into S3
s3_pipe_h = text_plus("S3_Pipe_H",
    "THE PIPELINE — END TO END, ON DEVICE.",
    font=F_DISPLAY, size=0.065, color=PAPER,
    center=(0.5, 0.80),
    global_in=PIPELINE_BASE, global_out=S3+750,
    blend=fade_in_out(PIPELINE_BASE, S3+750, 12, 18))
merge(s3_pipe_h)

# Four pipeline boxes (outlines + label) and connecting arrows
def pipeline_node(name: str, cx: float, w: float, label_top: str, title: str,
                  color, start_offset: int):
    in_f = PIPELINE_BASE + start_offset
    ob_m = rect_mask(f"{name}_OM", w=w, h=0.185,
        center=(cx, 0.46), border=0.0023, solid=0,
        global_in=in_f, global_out=S3+750)
    ob = background(f"{name}_O", color,
        global_in=in_f, global_out=S3+750,
        blend=fade_in_out(in_f, S3+750, 9, 15),
        mask=ob_m)
    merge(ob)
    lt = text_plus(f"{name}_Lbl", label_top,
        font=F_MONO, size=0.011, color=color,
        center=(cx, 0.535),
        global_in=in_f, global_out=S3+750,
        blend=fade_in_out(in_f, S3+750, 9, 15))
    tt = text_plus(f"{name}_T", title,
        font=F_DISPLAY, size=0.036, color=color,
        center=(cx, 0.43),
        global_in=in_f, global_out=S3+750,
        blend=fade_in_out(in_f+6, S3+750, 9, 15))
    merge(lt)
    merge(tt)

pipeline_node("S3_P1", cx=0.155, w=0.177, label_top="INPUT  *  VISION",
              title="SNAP NOTES", color=PAPER, start_offset=0)
# Arrow 1
a1_m = rect_mask("S3_A1_M", w=0.057, h=0.002,
    center=(0.27, 0.46),
    global_in=PIPELINE_BASE+18, global_out=S3+750)
a1 = background("S3_A1", RED,
    global_in=PIPELINE_BASE+18, global_out=S3+750,
    blend=fade_in_out(PIPELINE_BASE+18, S3+750, 6, 15),
    mask=a1_m)
merge(a1)

pipeline_node("S3_P2", cx=0.40, w=0.198, label_top="LOCAL  MULTIMODAL",
              title="GEMMA 4", color=AMBER, start_offset=18)
# Sub-label under P2
gtag = text_plus("S3_P2_Sub", "VISION  +  AUDIO  +  REASONING",
    font=F_MONO, size=0.013, color=AMBER,
    center=(0.40, 0.33),
    global_in=PIPELINE_BASE+30, global_out=S3+750,
    blend=fade_in_out(PIPELINE_BASE+30, S3+750, 9, 15))
merge(gtag)
# Arrow 2
a2_m = rect_mask("S3_A2_M", w=0.057, h=0.002,
    center=(0.52, 0.46),
    global_in=PIPELINE_BASE+36, global_out=S3+750)
a2 = background("S3_A2", RED,
    global_in=PIPELINE_BASE+36, global_out=S3+750,
    blend=fade_in_out(PIPELINE_BASE+36, S3+750, 6, 15),
    mask=a2_m)
merge(a2)

pipeline_node("S3_P3", cx=0.66, w=0.177, label_top="VOICE  *  STT",
              title="SPEAK ANSWER", color=PAPER, start_offset=42)
# Arrow 3
a3_m = rect_mask("S3_A3_M", w=0.057, h=0.002,
    center=(0.785, 0.46),
    global_in=PIPELINE_BASE+60, global_out=S3+750)
a3 = background("S3_A3", RED,
    global_in=PIPELINE_BASE+60, global_out=S3+750,
    blend=fade_in_out(PIPELINE_BASE+60, S3+750, 6, 15),
    mask=a3_m)
merge(a3)

pipeline_node("S3_P4", cx=0.89, w=0.135, label_top="VERDICT",
              title="EVALUATED", color=RED, start_offset=66)

# 100 % LOCAL stamp
stamp_scale_3 = anim(1.6, [(PIPELINE_BASE+150, 1.6),
                           (PIPELINE_BASE+159, 1.05),
                           (PIPELINE_BASE+165, 1.0)])
s3_local_main = text_plus("S3_Local_Tx",
    "100% LOCAL", font=F_DISPLAY, size=0.058, color=RED,
    center=(0.50, 0.15),
    global_in=PIPELINE_BASE+150, global_out=S3+750,
    blend=fade_in_out(PIPELINE_BASE+150, S3+750, 9, 15),
    angle=-4.0)
s3_local_sub = text_plus("S3_Local_Sub",
    "ZERO  CLOUD  CALLS", font=F_MONO, size=0.013, color=RED,
    center=(0.50, 0.10),
    global_in=PIPELINE_BASE+150, global_out=S3+750,
    blend=fade_in_out(PIPELINE_BASE+150, S3+750, 9, 15),
    angle=-4.0)
s3_local_t = transform("S3_Local_T", s3_local_main,
    center=(0.50, 0.15),
    size_anim=stamp_scale_3,
    global_in=PIPELINE_BASE+150, global_out=S3+750)
merge(s3_local_t)
merge(s3_local_sub)

s3_slug = text_plus("S3_Slug",
    "—— EXHIBIT B  —  THE TOOLKIT",
    font=F_MONO, size=0.013, color=PAPER,
    center=(0.22, 0.94),
    global_in=S3, global_out=S3e-1,
    blend=fade_in_out(S3+6, S3e-1, 12, 18))
merge(s3_slug)

# ═══════════════════════════════════════════════════════════════════════════
# SCENE 4 — Privacy  (frames 2100–2850)
# ═══════════════════════════════════════════════════════════════════════════
S4, S4e = S[4], S[5]

s4_kicker = text_plus("S4_Kicker",
    "K-12  CYBERSECURITY  REPORT  •  2025",
    font=F_MONO, size=0.014, color=RED,
    center=(0.22, 0.80),
    global_in=S4, global_out=S4+345,
    blend=fade_in_out(S4+6, S4+345, 12, 18))
merge(s4_kicker)

# 45 % big counter — animated via stepped string substitutions
COUNT_KEYS_45 = [(S4+9, "0"), (S4+15, "8"), (S4+21, "16"), (S4+27, "24"),
                 (S4+33, "32"), (S4+39, "40"), (S4+45, "43"), (S4+51, "45")]
# In Fusion text values don't interpolate — we approximate by 4 sequential TextPlus
# Simpler: just show the final "45" with a brief fade-in.  The counter idea is
# documented in the README; tweakers can swap in Text Step modifier.
s4_stat_num = text_plus("S4_Stat_Num",
    "45", font=F_DISPLAY, size=0.33, color=PAPER,
    center=(0.27, 0.50),
    global_in=S4+12, global_out=S4+345,
    blend=fade_in_out(S4+12, S4+345, 12, 18))
s4_stat_pct = text_plus("S4_Stat_Pct",
    "%", font=F_DISPLAY, size=0.135, color=RED,
    center=(0.395, 0.54),
    global_in=S4+12, global_out=S4+345,
    blend=fade_in_out(S4+12, S4+345, 12, 18))
s4_stat_lbl = text_plus("S4_Stat_Lbl",
    "OF SCHOOLS HAD DATA BREACHES",
    font=F_COND, style="Bold", size=0.024, color=PAPER,
    center=(0.32, 0.30),
    global_in=S4+12, global_out=S4+345,
    blend=fade_in_out(S4+12, S4+345, 12, 18))
s4_stat_quote = text_plus("S4_Stat_Quote",
    "...because they trusted the cloud with student data.",
    font=F_SERIF, style="Italic", size=0.030, color=PAPER,
    center=(0.40, 0.15),
    global_in=S4+12, global_out=S4+345,
    blend=fade_in_out(S4+18, S4+345, 12, 18))
merge(s4_stat_num)
merge(s4_stat_pct)
merge(s4_stat_lbl)
merge(s4_stat_quote)

# Redacted bars — right side leaked-records column
for i, w_norm in enumerate([0.13, 0.20, 0.16, 0.22, 0.12,
                            0.19, 0.14, 0.23, 0.13, 0.17]):
    in_f = S4+18 + i*4
    bm = rect_mask(f"S4_R{i}_M", w=w_norm, h=0.026,
        center=(0.80, 0.68 - i*0.040),
        global_in=in_f, global_out=S4+345)
    bb = background(f"S4_R{i}", REDACT,
        global_in=in_f, global_out=S4+345,
        blend=fade_in_out(in_f, S4+345, 4, 15),
        mask=bm)
    merge(bb)
s4_r_kicker = text_plus("S4_R_Kicker",
    "STUDENT  RECORDS — LEAKED",
    font=F_MONO, size=0.013, color=PAPER,
    center=(0.80, 0.74),
    global_in=S4+18, global_out=S4+345,
    blend=fade_in_out(S4+18, S4+345, 12, 18))
merge(s4_r_kicker)

# Red flash transition
s4_flash = background("S4_Flash", RED,
    global_in=S4+330, global_out=S4+354,
    blend=anim(0, [(S4+330, 0.7), (S4+354, 0.0)]))
merge(s4_flash)

# Phase B — count 45 → 0 (final "0" with checkmark)
s4_mh_kicker = text_plus("S4_MH_Kicker",
    "MINDHEIST",
    font=F_MONO, size=0.018, color=RED,
    center=(0.5, 0.78),
    global_in=S4+348, global_out=S4+744,
    blend=fade_in_out(S4+348, S4+744, 12, 18))
s4_big_zero = text_plus("S4_BigZero",
    "0", font=F_DISPLAY, size=0.42, color=AMBER,
    center=(0.43, 0.54),
    global_in=S4+348, global_out=S4+744,
    blend=fade_in_out(S4+348, S4+744, 12, 18))
# Glow ring around the 0 (small circle drawn by two rect masks)
s4_check_h_m = rect_mask("S4_Check_M", w=0.115, h=0.205,
    center=(0.57, 0.54), border=0.0042, solid=0,
    global_in=S4+360, global_out=S4+744)
s4_check_h = background("S4_Check_Ring", AMBER,
    global_in=S4+360, global_out=S4+744,
    blend=fade_in_out(S4+360, S4+744, 12, 18),
    mask=s4_check_h_m)
s4_check_tx = text_plus("S4_Check_Tx",
    "✓", font=F_DISPLAY, size=0.135, color=AMBER,
    center=(0.57, 0.535),
    global_in=S4+372, global_out=S4+744,
    blend=fade_in_out(S4+372, S4+744, 9, 15))
merge(s4_mh_kicker)
merge(s4_big_zero)
merge(s4_check_h)
merge(s4_check_tx)

s4_b_lbl = text_plus("S4_B_Lbl",
    "CLOUD DATA  •  STORED  •  LEAKED  •  EXPOSED",
    font=F_COND, style="Bold", size=0.04, color=PAPER,
    center=(0.5, 0.22),
    global_in=S4+360, global_out=S4+744,
    blend=fade_in_out(S4+360, S4+744, 12, 18))
s4_b_sub = text_plus("S4_B_Sub",
    "No data leaves your school. Ever.",
    font=F_SERIF, style="Italic", size=0.028, color=AMBER,
    center=(0.5, 0.13),
    global_in=S4+360, global_out=S4+744,
    blend=fade_in_out(S4+372, S4+744, 12, 18))
merge(s4_b_lbl)
merge(s4_b_sub)

s4_slug = text_plus("S4_Slug",
    "—— EXHIBIT C  —  THE BREACH",
    font=F_MONO, size=0.013, color=PAPER,
    center=(0.22, 0.94),
    global_in=S4, global_out=S4e-1,
    blend=fade_in_out(S4+6, S4e-1, 12, 18))
merge(s4_slug)

# ═══════════════════════════════════════════════════════════════════════════
# SCENE 5 — Witnesses  (frames 2850–3450)
# ═══════════════════════════════════════════════════════════════════════════
S5, S5e = S[5], S[6]

# 82 % stat
s5_stat = text_plus("S5_Stat",
    "82", font=F_DISPLAY, size=0.36, color=PAPER,
    center=(0.5, 0.55),
    global_in=S5, global_out=S5+255,
    blend=fade_in_out(S5, S5+255, 12, 18))
s5_pct = text_plus("S5_Pct",
    "%", font=F_DISPLAY, size=0.165, color=AMBER,
    center=(0.59, 0.58),
    global_in=S5, global_out=S5+255,
    blend=fade_in_out(S5, S5+255, 12, 18))
s5_lbl = text_plus("S5_Lbl",
    "PREFER IMMERSIVE LEARNING",
    font=F_COND, style="Bold", size=0.025, color=PAPER,
    center=(0.5, 0.30),
    global_in=S5, global_out=S5+255,
    blend=fade_in_out(S5+6, S5+255, 12, 18))
s5_quote = text_plus("S5_Quote",
    "\"We're students. We built this for us.\"",
    font=F_SERIF, style="Italic", size=0.030, color=PAPER,
    center=(0.5, 0.20),
    global_in=S5, global_out=S5+255,
    blend=fade_in_out(S5+12, S5+255, 12, 18))
s5_src = text_plus("S5_Src",
    "JOURNAL OF EDUCATIONAL TECH  •  2024",
    font=F_MONO, size=0.012, color=PAPER,
    center=(0.5, 0.12),
    global_in=S5, global_out=S5+255,
    blend=fade_in_out(S5+18, S5+255, 12, 18))
merge(s5_stat)
merge(s5_pct)
merge(s5_lbl)
merge(s5_quote)
merge(s5_src)

# Phase B — Two persons of interest
s5_h = text_plus("S5_H",
    "TWO  PERSONS  OF  INTEREST.",
    font=F_DISPLAY, size=0.075, color=PAPER,
    center=(0.5, 0.80),
    global_in=S5+258, global_out=S5+600,
    blend=fade_in_out(S5+258, S5+600, 12, 18))
merge(s5_h)

# LEFT subject (CD)
s5_cd_ph_m = rect_mask("S5_CD_PH_M", w=0.146, h=0.333,
    center=(0.205, 0.45),
    global_in=S5+270, global_out=S5+600)
s5_cd_ph = background("S5_CD_PH", REDACT,
    global_in=S5+270, global_out=S5+600,
    blend=fade_in_out(S5+270, S5+600, 12, 18),
    mask=s5_cd_ph_m)
s5_cd_ph_lbl = text_plus("S5_CD_PH_Lbl",
    "CD — PHOTO",
    font=F_MONO, size=0.012, color=ASH,
    center=(0.205, 0.45),
    global_in=S5+270, global_out=S5+600,
    blend=fade_in_out(S5+270, S5+600, 12, 18))
s5_cd_id = text_plus("S5_CD_Id",
    "SUBJECT  •  CD",
    font=F_MONO, size=0.014, color=RED,
    center=(0.46, 0.61),
    global_in=S5+270, global_out=S5+600,
    blend=fade_in_out(S5+270, S5+600, 12, 18))
s5_cd_h = text_plus("S5_CD_H",
    "THE\nEXPERIENCE.",
    font=F_DISPLAY, size=0.072, color=PAPER,
    center=(0.46, 0.50), line_spacing=0.9,
    global_in=S5+270, global_out=S5+600,
    blend=fade_in_out(S5+276, S5+600, 12, 18))
s5_cd_q = text_plus("S5_CD_Q",
    "\"I craft the immersion: clarity,\nthrills, the case-file feel.\"",
    font=F_SERIF, style="Italic", size=0.020, color=PAPER,
    center=(0.46, 0.31), line_spacing=1.3,
    global_in=S5+282, global_out=S5+600,
    blend=fade_in_out(S5+282, S5+600, 12, 18))
merge(s5_cd_ph)
merge(s5_cd_ph_lbl)
merge(s5_cd_id)
merge(s5_cd_h)
merge(s5_cd_q)

# RIGHT subject (LD)
s5_ld_ph_m = rect_mask("S5_LD_PH_M", w=0.146, h=0.333,
    center=(0.53, 0.45),
    global_in=S5+288, global_out=S5+600)
s5_ld_ph = background("S5_LD_PH", REDACT,
    global_in=S5+288, global_out=S5+600,
    blend=fade_in_out(S5+288, S5+600, 12, 18),
    mask=s5_ld_ph_m)
s5_ld_ph_lbl = text_plus("S5_LD_PH_Lbl",
    "LD — PHOTO",
    font=F_MONO, size=0.012, color=ASH,
    center=(0.53, 0.45),
    global_in=S5+288, global_out=S5+600,
    blend=fade_in_out(S5+288, S5+600, 12, 18))
s5_ld_id = text_plus("S5_LD_Id",
    "SUBJECT  •  LD",
    font=F_MONO, size=0.014, color=AMBER,
    center=(0.795, 0.61),
    global_in=S5+288, global_out=S5+600,
    blend=fade_in_out(S5+288, S5+600, 12, 18))
s5_ld_h = text_plus("S5_LD_H",
    "THE\nTECHNIQUE.",
    font=F_DISPLAY, size=0.072, color=PAPER,
    center=(0.795, 0.50), line_spacing=0.9,
    global_in=S5+288, global_out=S5+600,
    blend=fade_in_out(S5+294, S5+600, 12, 18))
s5_ld_q = text_plus("S5_LD_Q",
    "\"Gemma 4. Ollama. Local privacy.\nThe machinery that holds it up.\"",
    font=F_SERIF, style="Italic", size=0.020, color=PAPER,
    center=(0.795, 0.31), line_spacing=1.3,
    global_in=S5+300, global_out=S5+600,
    blend=fade_in_out(S5+300, S5+600, 12, 18))
merge(s5_ld_ph)
merge(s5_ld_ph_lbl)
merge(s5_ld_id)
merge(s5_ld_h)
merge(s5_ld_q)

# Plus icon between subjects
s5_plus_m = rect_mask("S5_Plus_M", w=0.029, h=0.052,
    center=(0.5, 0.48), border=0.0022, solid=0,
    global_in=S5+306, global_out=S5+600)
s5_plus_bg = background("S5_Plus_BG", INK,
    global_in=S5+306, global_out=S5+600,
    blend=fade_in_out(S5+306, S5+600, 12, 18),
    mask=s5_plus_m)
s5_plus = text_plus("S5_Plus",
    "+", font=F_DISPLAY, size=0.030, color=PAPER,
    center=(0.5, 0.48),
    global_in=S5+306, global_out=S5+600,
    blend=fade_in_out(S5+306, S5+600, 12, 18))
merge(s5_plus_bg)
merge(s5_plus)

s5_slug = text_plus("S5_Slug",
    "—— EXHIBIT D  —  THE WITNESS",
    font=F_MONO, size=0.013, color=PAPER,
    center=(0.22, 0.94),
    global_in=S5, global_out=S5e-1,
    blend=fade_in_out(S5+6, S5e-1, 12, 18))
merge(s5_slug)

# ═══════════════════════════════════════════════════════════════════════════
# SCENE 6 — Verdict  (frames 3450–4350)
# ═══════════════════════════════════════════════════════════════════════════
S6, S6e = S[6], S[7]

# Warmer cork-board tint background
s6_bg = background("S6_CorkTone", (0.165, 0.125, 0.078),
    global_in=S6, global_out=S6+465,
    blend=fade_in_out(S6, S6+465, 18, 24))
merge(s6_bg)

# Polaroid placeholders
for idx, (cx, cy, ang, lbl, cap) in enumerate([
    (0.21, 0.55, -6.0, "LD + CD — SOLVED IT", "Suspect A — 7:49 PM ✓"),
    (0.48, 0.50,  4.0, "MINDHEIST — IN HAND", "Case closed in 4 min."),
]):
    in_f = S6 + 9 + idx*9
    pm = rect_mask(f"S6_Pol{idx}_M", w=0.22, h=0.43,
        center=(cx, cy), angle=ang,
        global_in=in_f, global_out=S6+465)
    pb = background(f"S6_Pol{idx}_BG", (0.965, 0.937, 0.867),
        global_in=in_f, global_out=S6+465,
        blend=fade_in_out(in_f, S6+465, 12, 18),
        mask=pm)
    merge(pb)
    plm = rect_mask(f"S6_Pol{idx}_PH_M", w=0.21, h=0.34,
        center=(cx, cy+0.04), angle=ang,
        global_in=in_f, global_out=S6+465)
    plb = background(f"S6_Pol{idx}_PH", REDACT,
        global_in=in_f, global_out=S6+465,
        blend=fade_in_out(in_f, S6+465, 12, 18),
        mask=plm)
    merge(plb)
    plc = text_plus(f"S6_Pol{idx}_Cap", cap,
        font=F_TYPE, size=0.020, color=INK,
        center=(cx, cy-0.16),
        global_in=in_f, global_out=S6+465,
        blend=fade_in_out(in_f+6, S6+465, 12, 18),
        angle=ang)
    merge(plc)
    pll = text_plus(f"S6_Pol{idx}_Lbl", lbl,
        font=F_MONO, size=0.012, color=ASH,
        center=(cx, cy+0.04),
        global_in=in_f, global_out=S6+465,
        blend=fade_in_out(in_f, S6+465, 12, 18),
        angle=ang)
    merge(pll)

# Right column copy
s6_kick = text_plus("S6_VerdictKick",
    "THE  VERDICT",
    font=F_MONO, size=0.014, color=RED,
    center=(0.78, 0.78),
    global_in=S6+18, global_out=S6+465,
    blend=fade_in_out(S6+18, S6+465, 12, 18))
s6_h = text_plus("S6_VerdictH",
    "SOLVES\nBOTH.",
    font=F_DISPLAY, size=0.11, color=PAPER,
    center=(0.78, 0.65), line_spacing=0.85,
    global_in=S6+18, global_out=S6+465,
    blend=fade_in_out(S6+24, S6+465, 12, 18))
s6_l1 = text_plus("S6_L1", "✓  ENGAGEMENT",
    font=F_COND, style="Bold", size=0.032, color=AMBER,
    center=(0.78, 0.45),
    global_in=S6+30, global_out=S6+465,
    blend=fade_in_out(S6+30, S6+465, 12, 18))
s6_l2 = text_plus("S6_L2", "✓  PRIVACY",
    font=F_COND, style="Bold", size=0.032, color=AMBER,
    center=(0.78, 0.39),
    global_in=S6+36, global_out=S6+465,
    blend=fade_in_out(S6+36, S6+465, 12, 18))
s6_slogan = text_plus("S6_Slogan",
    "\"Because learning shouldn't be a mystery — it should be thrilling.\"",
    font=F_SERIF, style="Italic", size=0.030, color=PAPER,
    center=(0.5, 0.14),
    global_in=S6+42, global_out=S6+465,
    blend=fade_in_out(S6+48, S6+465, 12, 18))
merge(s6_kick)
merge(s6_h)
merge(s6_l1)
merge(s6_l2)
merge(s6_slogan)

# Phase B — LOCAL. PRIVATE. REVOLUTIONARY.
s6_mh_kicker = text_plus("S6_MH_Kicker",
    "MINDHEIST",
    font=F_MONO, size=0.018, color=RED,
    center=(0.5, 0.85),
    global_in=S6+468, global_out=S6+900,
    blend=fade_in_out(S6+468, S6+900, 12, 18))
merge(s6_mh_kicker)

for i, word in enumerate(["LOCAL.", "PRIVATE.", "REVOLUTIONARY."]):
    in_f = S6 + 477 + i*27
    n = text_plus(f"S6_Word{i}", word,
        font=F_DISPLAY, size=0.18, color=PAPER,
        center=(0.5, 0.68 - i*0.165),
        global_in=in_f, global_out=S6+900,
        blend=fade_in_out(in_f, S6+900, 9, 18))
    merge(n)

# Red underline accent after REVOLUTIONARY
s6_under_m = rect_mask("S6_Under_M", w=0.27, h=0.0074,
    center=(0.5, 0.20),
    global_in=S6+558, global_out=S6+900)
s6_under = background("S6_Under", RED,
    global_in=S6+558, global_out=S6+900,
    blend=fade_in_out(S6+558, S6+900, 9, 18),
    mask=s6_under_m)
merge(s6_under)

s6_slug = text_plus("S6_Slug",
    "—— EXHIBIT E  —  THE VERDICT",
    font=F_MONO, size=0.013, color=PAPER,
    center=(0.22, 0.94),
    global_in=S6, global_out=S6e-1,
    blend=fade_in_out(S6+6, S6e-1, 12, 18))
merge(s6_slug)

# ═══════════════════════════════════════════════════════════════════════════
# SCENE 7 — End Screen  (frames 4350–5250)
# ═══════════════════════════════════════════════════════════════════════════
S7, S7e = S[7], S["end"]

s7_bg = background("S7_BG", (0.165, 0.122, 0.071),
    global_in=S7, global_out=S7e,
    blend=fade_in_out(S7, S7e, 18, 30))
merge(s7_bg)

# Logo slam — shifts up after 5s so before/after stats can fit
mh_scale_7 = anim(1.15, [(S7+6, 1.15), (S7+18, 1.04), (S7+24, 1.0)])
mh_y_7 = anim(0.62, [(S7+6, 0.62), (S7+150, 0.62), (S7+170, 0.78)])

s7_kicker = text_plus("S7_Kicker",
    "● MINDHEIST",
    font=F_MONO, size=0.018, color=RED,
    center=(0.5, 0.86),
    global_in=S7+6, global_out=S7e,
    blend=fade_in_out(S7+6, S7e, 12, 24))
merge(s7_kicker)

s7_mh = text_plus("S7_MH",
    "MINDHEIST", font=F_DISPLAY, size=0.33, color=PAPER,
    center=(0.5, 0.62),
    global_in=S7+6, global_out=S7e,
    blend=fade_in_out(S7+6, S7e, 12, 30))
s7_mh_t = transform("S7_MH_T", s7_mh,
    center=(0.5, 0.62), size_anim=mh_scale_7,
    global_in=S7+6, global_out=S7e)
merge(s7_mh_t)

s7_mh_sub = text_plus("S7_MH_Sub",
    "where every lesson is a clue.",
    font=F_SERIF, style="Italic", size=0.032, color=PAPER,
    center=(0.5, 0.46),
    global_in=S7+6, global_out=S7+165,
    blend=fade_in_out(S7+24, S7+165, 12, 18))
merge(s7_mh_sub)

# Before / after stats
s7_ba_kick = text_plus("S7_BA_Kicker",
    "THE EVIDENCE — RECONSIDERED",
    font=F_MONO, size=0.013, color=RED,
    center=(0.5, 0.50),
    global_in=S7+180, global_out=S7+660,
    blend=fade_in_out(S7+180, S7+660, 12, 18))
merge(s7_ba_kick)

for i, (frm, to, fl, tl, is_zero) in enumerate([
    ("73%", "100%", "ZONE OUT", "ENGAGED", False),
    ("45%", "0",    "CLOUD BREACHES", "CLOUD DATA", True),
]):
    in_f = S7 + 180 + i*18
    cy = 0.40 - i*0.13
    # FROM (struck-through, dimmed)
    fb = text_plus(f"S7_BA_From{i}", frm,
        font=F_DISPLAY, size=0.072, color=PAPER,
        center=(0.30, cy),
        global_in=in_f, global_out=S7+660,
        blend=fade_in_out(in_f, S7+660, 9, 18))
    fl_t = text_plus(f"S7_BA_FromLbl{i}", fl,
        font=F_MONO, size=0.012, color=PAPER,
        center=(0.30, cy-0.06),
        global_in=in_f, global_out=S7+660,
        blend=fade_in_out(in_f, S7+660, 9, 18))
    arrow = text_plus(f"S7_BA_Arrow{i}", "→",
        font=F_DISPLAY, size=0.05, color=RED,
        center=(0.50, cy),
        global_in=in_f, global_out=S7+660,
        blend=fade_in_out(in_f+3, S7+660, 9, 18))
    to_color = AMBER if is_zero else PAPER
    tb = text_plus(f"S7_BA_To{i}", to,
        font=F_DISPLAY, size=0.082, color=to_color,
        center=(0.70, cy),
        global_in=in_f, global_out=S7+660,
        blend=fade_in_out(in_f+6, S7+660, 9, 18))
    tl_t = text_plus(f"S7_BA_ToLbl{i}", tl,
        font=F_MONO, size=0.012, color=to_color,
        center=(0.70, cy-0.06),
        global_in=in_f, global_out=S7+660,
        blend=fade_in_out(in_f+6, S7+660, 9, 18))
    # red strike-through line across FROM
    sm = rect_mask(f"S7_BA_Strike{i}_M", w=0.10, h=0.005,
        center=(0.30, cy+0.005),
        global_in=in_f+3, global_out=S7+660)
    sb = background(f"S7_BA_Strike{i}", RED,
        global_in=in_f+3, global_out=S7+660,
        blend=fade_in_out(in_f+3, S7+660, 6, 18),
        mask=sm)
    merge(fb); merge(fl_t); merge(arrow); merge(tb); merge(tl_t); merge(sb)

# Final tagline — SOLVE EDUCATION. SOLVE THE FUTURE.
s7_tag = text_plus("S7_Tag",
    "SOLVE EDUCATION.\nSOLVE THE FUTURE.",
    font=F_DISPLAY, size=0.092, color=PAPER,
    center=(0.5, 0.18), line_spacing=0.95,
    global_in=S7+420, global_out=S7e,
    blend=fade_in_out(S7+420, S7e, 18, 30))
merge(s7_tag)

# GitHub URL corner badge
s7_gh = text_plus("S7_GH",
    "● GITHUB.COM/YOUR-TEAM/MINDHEIST",
    font=F_MONO, size=0.014, color=PAPER,
    center=(0.78, 0.07),
    global_in=S7+240, global_out=S7e,
    blend=fade_in_out(S7+240, S7e, 12, 30))
merge(s7_gh)

# Final fade-out on the master chain
final_fade = anim(0, [(S7e-15, 0.0), (S7e, 0.5)])
s7_blackout = background("Final_Blackout", (0, 0, 0),
    global_in=S7e-15, global_out=S7e,
    blend=final_fade)
merge(s7_blackout)

# ═══════════════════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════════════════
final_in = merge_chain[-1]

# Optional film grain overlay (commented out by default — uncomment in Fusion)
# A FilmGrain node can be added by the user via Effects Library.

media_out = tool("MediaOut1", f"""MediaOut {{
            CtrlWZoom = false,
            Inputs = {{
                Index = Input {{ Value = 0, }},
                Input = Input {{ SourceOp = "{final_in}", Source = "Output", }},
            }}
        """, x=15)

# ═══════════════════════════════════════════════════════════════════════════
# Emit the .comp file
# ═══════════════════════════════════════════════════════════════════════════
HEADER = f"""\
Composition {{
    CurrentTime = 0,
    RenderRange = {{ 0, {FRAMES-1} }},
    GlobalRange = {{ 0, {FRAMES-1} }},
    CurrentID = 1,
    Version = "Fusion 18.6",

    Settings = {{
        HiQ = {{ true, true }},
        MotionBlur = {{ true, true }},
        ProxyMode = {{ true, true }},
        ProxyScale = 1,
        AutoProxyEnabled = {{ false, false }},
    }},

    FrameFormat = {{
        Width = {W},
        Height = {H},
        AspectX = 1,
        AspectY = 1,
        Rate = {FPS},
        GuideRatio = 1.7777,
    }},

    Tools = ordered() {{
"""

FOOTER = f"""\
    }},
    ActiveTool = "{media_out}"
}}
"""

body = "\n".join(tools)
output = HEADER + body + "\n" + FOOTER

OUT_PATH = os.path.join(os.path.dirname(__file__), "Mindheist_Launch.comp")
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(output)

print(f"Wrote {OUT_PATH}")
print(f"  - {len(tools)} top-level tools")
print(f"  - {spline_id} BezierSpline curves")
print(f"  - {FRAMES} frames @ {FPS} fps  ({DURATION_S} s, {W}x{H})")
