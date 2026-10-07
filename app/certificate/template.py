"""Visual layout constants for the PDF certificate template.

All visual decisions (colors, margins, font sizes, positions) live here.
The generator imports these constants and must not embed raw numbers.
"""
from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm

# ── Page ─────────────────────────────────────────────────────────────────────
PAGE_WIDTH, PAGE_HEIGHT = A4          # 210 × 297 mm (landscape on longer axis)
LANDSCAPE_WIDTH, LANDSCAPE_HEIGHT = PAGE_HEIGHT, PAGE_WIDTH  # 297 × 210 mm

# We render in landscape
CANVAS_WIDTH = LANDSCAPE_WIDTH
CANVAS_HEIGHT = LANDSCAPE_HEIGHT

# ── Margins ───────────────────────────────────────────────────────────────────
MARGIN_LEFT = 2.5 * cm
MARGIN_RIGHT = 2.5 * cm
MARGIN_TOP = 2.0 * cm
MARGIN_BOTTOM = 2.0 * cm

CONTENT_WIDTH = CANVAS_WIDTH - MARGIN_LEFT - MARGIN_RIGHT

# ── Colors (R, G, B) 0-1 range ───────────────────────────────────────────────
COLOR_BACKGROUND = (0.05, 0.05, 0.12)       # deep navy
COLOR_BORDER_OUTER = (0.85, 0.72, 0.25)     # gold
COLOR_BORDER_INNER = (0.75, 0.62, 0.18)     # darker gold
COLOR_TITLE = (0.95, 0.85, 0.30)            # bright gold
COLOR_SUBTITLE = (0.80, 0.80, 0.90)         # muted lavender
COLOR_RECIPIENT = (1.0, 1.0, 1.0)           # white
COLOR_BODY = (0.85, 0.85, 0.95)             # light lavender
COLOR_LINE = (0.85, 0.72, 0.25)             # gold

# ── Border geometry ───────────────────────────────────────────────────────────
BORDER_OUTER_INSET = 8 * mm
BORDER_INNER_INSET = 11 * mm
BORDER_OUTER_WIDTH = 3
BORDER_INNER_WIDTH = 1

# ── Fonts ─────────────────────────────────────────────────────────────────────
# These names must match registered font names in generator.py.
# We use Helvetica-Bold / Helvetica as safe built-ins.
# If CERTIFICATE_FONT_PATH is set to a TTF we register it as "CertFont".
FONT_TITLE = "Helvetica-Bold"
FONT_SUBTITLE = "Helvetica"
FONT_RECIPIENT_BASE = "Helvetica-Bold"  # may shrink for long names
FONT_BODY = "Helvetica"

# ── Font sizes ────────────────────────────────────────────────────────────────
SIZE_TITLE = 28
SIZE_SUBTITLE = 13
SIZE_RECIPIENT_MAX = 36       # largest allowed
SIZE_RECIPIENT_MIN = 18       # shrink floor
SIZE_BODY = 12
SIZE_LABEL = 10

# ── Vertical layout (Y positions from bottom) ─────────────────────────────────
Y_TITLE = CANVAS_HEIGHT - MARGIN_TOP - 3.5 * cm
Y_PRESENTED_TO = Y_TITLE - 1.8 * cm
Y_RECIPIENT = Y_PRESENTED_TO - 2.2 * cm
Y_DIVIDER = Y_RECIPIENT - 1.0 * cm
Y_EVENT_LABEL = Y_DIVIDER - 1.0 * cm
Y_EVENT_NAME = Y_EVENT_LABEL - 0.7 * cm
Y_FOOTER_LINE = MARGIN_BOTTOM + 2.5 * cm
Y_ISSUER_LABEL = Y_FOOTER_LINE - 0.5 * cm
Y_DATE_LABEL = Y_FOOTER_LINE - 0.5 * cm

# ── Recipient name wrapping ───────────────────────────────────────────────────
RECIPIENT_WRAP_CHARS = 30       # characters per line before font reduction kicks in
RECIPIENT_MAX_LINES = 2

# ── Decorative corner box size ────────────────────────────────────────────────
CORNER_SIZE = 1.5 * cm
