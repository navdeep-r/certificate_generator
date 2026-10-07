"""PDF certificate generator.

Public API:
    generate_certificate_pdf(data: CertificateData) -> bytes

This module knows nothing about HTTP, Celery, or PostgreSQL.
It receives a plain dataclass and returns PDF bytes.
"""
from __future__ import annotations

import io
import textwrap
from dataclasses import dataclass
from datetime import date

from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas as rl_canvas

from app.certificate import template as T
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CertificateData:
    """Plain data passed to the generator — no ORM, no HTTP objects."""

    recipient_name: str
    certificate_title: str
    event_name: str
    issuer_name: str
    issue_date: date


class CertificateGenerationError(Exception):
    """Raised when PDF creation fails unrecoverably."""


def generate_certificate_pdf(data: CertificateData) -> bytes:
    """Generate a PDF for a single recipient and return the bytes.

    Raises:
        CertificateGenerationError: if the PDF cannot be produced.
    """
    try:
        return _render(data)
    except Exception as exc:
        logger.error(
            "certificate_generation_failed | recipient=%s | error=%s",
            data.recipient_name[:20],
            exc,
        )
        raise CertificateGenerationError(str(exc)) from exc


# ── Internal rendering ────────────────────────────────────────────────────────

def _color(rgb: tuple[float, float, float]) -> Color:
    return Color(*rgb)


def _draw_background(c: rl_canvas.Canvas) -> None:
    c.setFillColor(_color(T.COLOR_BACKGROUND))
    c.rect(0, 0, T.CANVAS_WIDTH, T.CANVAS_HEIGHT, fill=1, stroke=0)


def _draw_borders(c: rl_canvas.Canvas) -> None:
    # Outer border
    c.setStrokeColor(_color(T.COLOR_BORDER_OUTER))
    c.setLineWidth(T.BORDER_OUTER_WIDTH)
    inset = T.BORDER_OUTER_INSET
    c.rect(
        inset, inset,
        T.CANVAS_WIDTH - 2 * inset,
        T.CANVAS_HEIGHT - 2 * inset,
        fill=0, stroke=1,
    )
    # Inner border
    c.setStrokeColor(_color(T.COLOR_BORDER_INNER))
    c.setLineWidth(T.BORDER_INNER_WIDTH)
    inset2 = T.BORDER_INNER_INSET
    c.rect(
        inset2, inset2,
        T.CANVAS_WIDTH - 2 * inset2,
        T.CANVAS_HEIGHT - 2 * inset2,
        fill=0, stroke=1,
    )


def _draw_corner_ornaments(c: rl_canvas.Canvas) -> None:
    """Draw small gold squares at each corner inside the outer border."""
    c.setFillColor(_color(T.COLOR_BORDER_OUTER))
    sz = T.CORNER_SIZE
    inset = T.BORDER_OUTER_INSET
    corners = [
        (inset, inset),
        (T.CANVAS_WIDTH - inset - sz, inset),
        (inset, T.CANVAS_HEIGHT - inset - sz),
        (T.CANVAS_WIDTH - inset - sz, T.CANVAS_HEIGHT - inset - sz),
    ]
    for x, y in corners:
        c.rect(x, y, sz, sz, fill=1, stroke=0)


def _fit_recipient_name(name: str) -> tuple[str, float]:
    """Return (possibly-wrapped name, font size) that fits within the content area."""
    if len(name) <= T.RECIPIENT_WRAP_CHARS:
        return name, T.SIZE_RECIPIENT_MAX

    # Try wrapping first
    wrapped = textwrap.fill(name, width=T.RECIPIENT_WRAP_CHARS, max_lines=T.RECIPIENT_MAX_LINES)
    if wrapped == name or "\n" not in wrapped:
        # Name doesn't wrap well — reduce font size instead
        font_size = max(
            T.SIZE_RECIPIENT_MIN,
            int(T.SIZE_RECIPIENT_MAX * T.RECIPIENT_WRAP_CHARS / len(name)),
        )
        return name, float(font_size)

    return wrapped, T.SIZE_RECIPIENT_MAX


def _draw_centered_text(
    c: rl_canvas.Canvas,
    text: str,
    y: float,
    font: str,
    size: float,
    color: tuple[float, float, float],
) -> None:
    c.setFont(font, size)
    c.setFillColor(_color(color))
    c.drawCentredString(T.CANVAS_WIDTH / 2, y, text)


def _draw_multiline_centered(
    c: rl_canvas.Canvas,
    text: str,
    y_top: float,
    font: str,
    size: float,
    color: tuple[float, float, float],
    line_height_factor: float = 1.3,
) -> float:
    """Draw multi-line text centered; returns the Y of the last line."""
    lines = text.split("\n")
    line_height = size * line_height_factor
    y = y_top
    for line in lines:
        _draw_centered_text(c, line, y, font, size, color)
        y -= line_height
    return y


def _draw_horizontal_line(c: rl_canvas.Canvas, y: float, alpha: float = 0.6) -> None:
    c.setStrokeColor(_color(T.COLOR_LINE))
    c.setLineWidth(0.8)
    c.setStrokeAlpha(alpha)
    x_start = T.MARGIN_LEFT + 2
    x_end = T.CANVAS_WIDTH - T.MARGIN_RIGHT - 2
    c.line(x_start, y, x_end, y)
    c.setStrokeAlpha(1.0)


def _render(data: CertificateData) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(
        buf,
        pagesize=(T.CANVAS_WIDTH, T.CANVAS_HEIGHT),
    )

    # ── Background & borders ──────────────────────────────────────────────────
    _draw_background(c)
    _draw_borders(c)
    _draw_corner_ornaments(c)

    # ── Title ─────────────────────────────────────────────────────────────────
    _draw_centered_text(
        c, data.certificate_title,
        T.Y_TITLE, T.FONT_TITLE, T.SIZE_TITLE, T.COLOR_TITLE,
    )

    # ── "This is presented to" subtitle ──────────────────────────────────────
    _draw_centered_text(
        c, "This certificate is proudly presented to",
        T.Y_PRESENTED_TO, T.FONT_SUBTITLE, T.SIZE_SUBTITLE, T.COLOR_SUBTITLE,
    )

    # ── Recipient name ────────────────────────────────────────────────────────
    display_name, name_size = _fit_recipient_name(data.recipient_name)
    last_y = _draw_multiline_centered(
        c, display_name,
        T.Y_RECIPIENT, T.FONT_RECIPIENT_BASE, name_size, T.COLOR_RECIPIENT,
    )

    # ── Divider below name ────────────────────────────────────────────────────
    divider_y = last_y - 0.5 * 28  # half a line below last name line
    _draw_horizontal_line(c, divider_y)

    # ── Event / course ────────────────────────────────────────────────────────
    label_y = divider_y - 0.9 * 28
    _draw_centered_text(
        c, "for successful completion of",
        label_y, T.FONT_SUBTITLE, T.SIZE_LABEL, T.COLOR_SUBTITLE,
    )
    _draw_centered_text(
        c, data.event_name,
        label_y - 0.8 * 28, T.FONT_TITLE, T.SIZE_BODY + 2, T.COLOR_TITLE,
    )

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_y = T.Y_FOOTER_LINE
    _draw_horizontal_line(c, footer_y)

    # Issuer — left side
    c.setFont(T.FONT_BODY, T.SIZE_LABEL)
    c.setFillColor(_color(T.COLOR_SUBTITLE))
    c.drawString(T.MARGIN_LEFT, footer_y - 14, "Issued by")
    c.setFont(T.FONT_TITLE, T.SIZE_BODY)
    c.setFillColor(_color(T.COLOR_BODY))
    c.drawString(T.MARGIN_LEFT, footer_y - 28, data.issuer_name)

    # Date — right side
    date_str = data.issue_date.strftime("%B %d, %Y")
    c.setFont(T.FONT_BODY, T.SIZE_LABEL)
    c.setFillColor(_color(T.COLOR_SUBTITLE))
    c.drawRightString(T.CANVAS_WIDTH - T.MARGIN_RIGHT, footer_y - 14, "Date Issued")
    c.setFont(T.FONT_TITLE, T.SIZE_BODY)
    c.setFillColor(_color(T.COLOR_BODY))
    c.drawRightString(T.CANVAS_WIDTH - T.MARGIN_RIGHT, footer_y - 28, date_str)

    c.showPage()
    c.save()

    buf.seek(0)
    return buf.read()
