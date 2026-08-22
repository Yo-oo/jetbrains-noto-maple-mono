"""Generate this project's own plain-text tag ligature badges (`[INFO]`, `[WARN]`, ...).

Unlike the old approach (copying Maple Mono's hand-drawn badge artwork
verbatim), this draws the badge itself: a filled rounded rect spanning the
full width of the trigger text (one 600-unit column per character, flush to
the cell edges -- verified against Maple's own tag_info.liga: its box is
exactly len(text)*600 wide and exactly hhea ascent-to-descent tall, zero
outer margin), with the trigger text cut through it as background-colored
holes, using the caller-supplied `letter_font`'s own glyph outlines.

No contour reversal is needed to make the holes appear: verified empirically
that a freshly hand-drawn rectangle's contour winding is already opposite a
real font's own letter contours (both JetBrains Mono's and Maple Mono's),
so nonzero-fill already punches the hole through as-is. (An earlier draft of
this module added a ReverseContourPen on the letters "to be safe" -- that
canceled the existing opposition back to *same* winding and silently
produced solid, hole-less badges instead.)

`letter_font` is deliberately a caller-chosen font/weight, not necessarily
whatever weight is being built: measured Maple Mono's own tag_info.liga
across every weight file and found byte-identical data in each -- Maple
always uses one fixed (bolder) weight for badge lettering regardless of the
surrounding text's own weight, because a badge cut from very thin strokes
reads poorly against a solid background. config.jsonc's tags.badge_weight
controls this (default "SemiBold"); passing the base font's own weight
instead is also valid if that look is preferred.
"""

from __future__ import annotations

import math

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph


def resolve_corner_radius(value: str | float, ascent: float, descent: float) -> float:
    if value is None:
        raise ValueError(
            "tags.corner_radius cannot be null -- use \"pill\" or a number "
            '0-660. To disable tag ligatures entirely, set tags.list to '
            "null instead."
        )
    if value == "pill":
        return (ascent - descent) / 2
    return float(value)


def _display_text(trigger: str) -> str:
    """Strip leading/trailing non-alphanumeric characters -- those are the
    framing delimiter ("[", "]", ":", ...), not part of what's actually
    drawn inside the badge. Verified against Maple Mono's own tag_info.liga:
    its trigger is "[INFO]" (6 columns) but the visible cutout text is just
    "INFO", not "[INFO]" -- the brackets are consumed as match/width but
    never rendered."""
    start = 0
    end = len(trigger)
    while start < end and not trigger[start].isalnum():
        start += 1
    while end > start and not trigger[end - 1].isalnum():
        end -= 1
    return trigger[start:end]


def check_tag_boundaries(tags: list[str]) -> list[str]:
    """Return one warning per tag whose first/last character isn't a delimiter.

    A tag with a plain letter/digit at either end can false-positive match as
    a substring of ordinary text -- e.g. "FIXME:" would also trigger inside
    "PREFIXME:", since the GSUB rule just matches the literal glyph sequence
    wherever it occurs, with no word-boundary check. Bracket-style tags
    ([INFO]) are naturally immune since '[' practically never appears
    mid-word. Not a hard error: the caller decides whether to accept the risk.
    """
    warnings = []
    for tag in tags:
        if tag[0].isalnum() or tag[-1].isalnum():
            warnings.append(
                f"tag {tag!r} has no delimiter character at one or both ends -- "
                "it may false-positive match as a substring of ordinary text "
                "(e.g. a bare 'FIXME:' would also fire inside 'PREFIXME:')"
            )
    return warnings


def _draw_rounded_rect(pen, x0: float, y0: float, x1: float, y1: float, radius: float) -> None:
    radius = max(0.0, min(radius, (x1 - x0) / 2, (y1 - y0) / 2))
    if radius <= 0:
        pen.moveTo((x0, y0))
        pen.lineTo((x1, y0))
        pen.lineTo((x1, y1))
        pen.lineTo((x0, y1))
        pen.closePath()
        return
    k = radius * 0.5523  # cubic-Bezier quarter-circle approximation constant
    pen.moveTo((x0 + radius, y0))
    pen.lineTo((x1 - radius, y0))
    pen.curveTo((x1 - radius + k, y0), (x1, y0 + radius - k), (x1, y0 + radius))
    pen.lineTo((x1, y1 - radius))
    pen.curveTo((x1, y1 - radius + k), (x1 - radius + k, y1), (x1 - radius, y1))
    pen.lineTo((x0 + radius, y1))
    pen.curveTo((x0 + radius - k, y1), (x0, y1 - radius + k), (x0, y1 - radius))
    pen.lineTo((x0, y0 + radius))
    pen.curveTo((x0, y0 + radius - k), (x0 + radius - k, y0), (x0 + radius, y0))
    pen.closePath()


def build_badge_glyph(
    text: str,
    letter_font: TTFont,
    corner_radius_value: str | float,
    inner_pad_x: float = 60,
    italic_angle: float = 0.0,
) -> tuple[Glyph, int, int]:
    """Return (glyf Glyph, advance, lsb) for one badge covering len(text) columns.

    `text` is the full trigger (e.g. "[INFO]") -- it determines the badge's
    visual width (one column per character), but the returned advance is
    always a single 600-unit column: this glyph is only ever placed at the
    LAST position of a matched sequence (every earlier position keeps its
    own SPC placeholder advance), and its artwork reaches backward over
    those columns via a negative left side bearing rather than by actually
    advancing further. The returned lsb is that negative value (the box's
    left edge) -- it must be stored as this glyph's hmtx left side bearing,
    not 0: hmtx.lsb is supposed to equal the outline's own xMin, and leaving
    it at 0 while the outline's real xMin is very negative caused real
    rendering stacks (confirmed in Chromium, not just a niche renderer) to
    reposition the ink to start at x=0 instead of the intended negative
    offset, visually shifting every badge to the right by (len(text) - 1)
    columns. Only its stripped core (_display_text) is drawn as visible
    cutout text; the framing delimiter characters are consumed for
    width/matching but never rendered, matching Maple Mono's own
    tag_info.liga (see _display_text's docstring).

    `italic_angle` (degrees) shears the box only, pivoted on the baseline --
    same convention as overlay_cjk.py's synthetic CJK shear. The letters
    themselves are never additionally sheared here: `letter_font` is already
    the real italic weight file when building an italic style, so its own
    outlines carry the correct slant already; shearing them again on top
    would double the lean.
    """
    cmap = letter_font.getBestCmap()
    glyph_set = letter_font.getGlyphSet()
    hmtx = letter_font["hmtx"]
    hhea = letter_font["hhea"]
    ascent, descent = hhea.ascent, hhea.descent

    # This glyph is placed at the LAST position of the matched sequence (every
    # earlier position becomes the blank SPC placeholder, each keeping its own
    # normal 600-unit advance) -- so its own advance must stay a single
    # 600-unit column, and its artwork spans backward from that column's
    # right edge via a negative left side bearing (x0 goes negative) to cover
    # the full width of all the columns it visually replaces.
    width = len(text) * 600
    x1 = 600
    x0 = x1 - width
    y0, y1 = descent, ascent
    radius = resolve_corner_radius(corner_radius_value, ascent, descent)

    rec = RecordingPen()
    box_pen = RecordingPen()
    _draw_rounded_rect(box_pen, x0, y0, x1, y1, radius)
    shear_tan = math.tan(math.radians(italic_angle))
    box_tp = TransformPen(rec, (1, 0, shear_tan, 1, 0, 0))
    for op, args in box_pen.value:
        getattr(box_tp, op)(*args)

    display_text = _display_text(text) or text
    cursor = 0
    positions = []
    for ch in display_text:
        cp = ord(ch)
        if cp not in cmap:
            raise ValueError(f"letter_font has no glyph for {ch!r} (in tag {text!r})")
        positions.append((cmap[cp], cursor))
        cursor += hmtx[cmap[cp]][0]
    natural_text_width = cursor

    # Center the text's own natural vertical extent in the box, rather than
    # a hardcoded cap-height constant -- keeps this correct regardless of
    # which font/weight letter_font turns out to be.
    text_ymin, text_ymax = None, None
    glyf = letter_font["glyf"]
    for glyph_name, _ in positions:
        g = glyf[glyph_name]
        if g.numberOfContours <= 0:
            continue
        text_ymin = g.yMin if text_ymin is None else min(text_ymin, g.yMin)
        text_ymax = g.yMax if text_ymax is None else max(text_ymax, g.yMax)
    text_ymin = text_ymin or 0
    text_ymax = text_ymax or 0

    avail_width = (x1 - x0) - 2 * inner_pad_x
    scale = min(1.0, avail_width / natural_text_width) if natural_text_width else 1.0

    text_width = natural_text_width * scale
    start_x = x0 + ((x1 - x0) - text_width) / 2
    text_center = (text_ymin + text_ymax) / 2 * scale
    box_center = (y0 + y1) / 2
    text_y_shift = box_center - text_center

    tp = TransformPen(rec, (scale, 0, 0, scale, start_x, text_y_shift))
    for glyph_name, x in positions:
        sub_tp = TransformPen(tp, (1, 0, 0, 1, x, 0))
        glyph_set[glyph_name].draw(sub_tp)

    pen = TTGlyphPen(None)
    # No reversal (see module docstring) -- the recorded contours' winding
    # is already correct for a nonzero-fill hole-punch.
    cu2qu_pen = Cu2QuPen(pen, max_err=1.0, reverse_direction=False)
    for op, args in rec.value:
        getattr(cu2qu_pen, op)(*args)

    # The true leftmost x -- not just x0 -- since a sheared (italic) box's
    # bottom-left corner reaches further left than the unsheared x0.
    all_x = [pt[0] for _op, args in rec.value for pt in args]
    lsb = round(min(all_x)) if all_x else round(x0)
    return pen.glyph(), 600, lsb
