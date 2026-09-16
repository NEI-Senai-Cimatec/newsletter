# gui/theme/charts.py
"""Theming helpers for the QuIIN dashboard matplotlib charts.

Pure figure/axes styling: no Tk, repository or I/O imports, so the
helpers stay unit-testable headless (Agg backend). Colors stay stable
per area across the bar and donut charts.
"""
from __future__ import annotations

# Área order follows ``core.repository.AREAS``:
# Negócio/Economia, Tecnológico, Científico, Outros.
QUIIN_PALETTE = ["#2E75B6", "#F28E2B", "#59A14F", "#E15759"]

AREA_COLORS = {
    "Negócio/Economia": QUIIN_PALETTE[0],
    "Tecnológico": QUIIN_PALETTE[1],
    "Científico": QUIIN_PALETTE[2],
    "Outros": QUIIN_PALETTE[3],
}

PANEL_COLOR = "#1A1D21"
TEXT_COLOR = "#E6E6E6"
FIGURE_DPI = 140
DONUT_WIDTH = 0.42
DONUT_MIN_PCT = 5.0

# Subplot margins sized so value labels (bars) and the external
# legend (donut) stay inside the figure on a 5x3 canvas.
BAR_ADJUST = dict(left=0.12, right=0.95, top=0.90, bottom=0.22)
DONUT_ADJUST = dict(left=0.02, right=0.55, top=0.96, bottom=0.04)


def apply_theme(fig, ax, panel_color: str = PANEL_COLOR,
                text_color: str = TEXT_COLOR) -> None:
    """Apply the QuIIN dark panel theme to ``fig``/``ax`` in place.

    Figure and axes backgrounds match the dashboard card color (no
    white box), top/right spines are removed, grid is faint, and any
    existing legend becomes frameless on the panel color.
    """
    fig.set_dpi(FIGURE_DPI)
    fig.patch.set_facecolor(panel_color)
    ax.set_facecolor(panel_color)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(text_color)
    ax.grid(True, axis="y", alpha=0.15, color=text_color)
    ax.tick_params(colors=text_color, labelsize=9)
    for label in (ax.xaxis.get_label(), ax.yaxis.get_label(),
                  ax.title):
        try:
            label.set_color(text_color)
        except AttributeError:
            pass
    legend = ax.get_legend()
    if legend is not None:
        legend.set_frame_on(False)
        try:
            legend.get_frame().set_facecolor(panel_color)
        except AttributeError:
            pass
        for text in legend.get_texts():
            text.set_color(text_color)


def style_bars(ax) -> None:
    """Add centered value labels above every bar; set X rotation.

    Zero-height bars get no label (avoids "0" clutter). The Y axis is
    forced to integer ticks since counts are whole documents. X tick
    labels stay horizontal when there are up to 6 categories
    (``stats_monthly`` returns at most 6), rotating past that.
    """
    from matplotlib.ticker import MaxNLocator

    for container in ax.containers:
        try:
            values = list(getattr(container, "datavalues", []))
            labels = ["" if value == 0 else f"{value:g}"
                      for value in values] or None
            ax.bar_label(container, labels=labels, fontsize=9, padding=2,
                         color=TEXT_COLOR)
        except (ValueError, AttributeError, TypeError):
            continue
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    labels = [tick.get_text() for tick in ax.get_xticklabels()]
    if labels and len(labels) <= 6:
        for tick in ax.get_xticklabels():
            tick.set_rotation(0)
            tick.set_ha("center")
    else:
        for tick in ax.get_xticklabels():
            tick.set_rotation(30)
            tick.set_ha("right")


def style_donut(ax, shares: dict, panel_color: str = PANEL_COLOR) -> None:
    """Draw the area-share donut on ``ax`` from ``shares``.

    Wedges are ``DONUT_WIDTH`` thick with the panel color as edge.
    Percentage is printed (white, bold) only on slices >=
    ``DONUT_MIN_PCT``; smaller slices appear in the external legend
    only (``"Área — XX%"``), avoiding label overlap. Zero-share areas
    are omitted from both pie and legend.
    """
    items = [(area, float(value)) for area, value in shares.items()
             if float(value or 0.0) > 0.0]
    if not items:
        return
    labels = [area for area, _ in items]
    values = [value for _, value in items]
    colors = [AREA_COLORS.get(area, QUIIN_PALETTE[i % len(QUIIN_PALETTE)])
              for i, area in enumerate(labels)]

    def _autopct(pct: float) -> str:
        return f"{pct:.0f}%" if pct >= DONUT_MIN_PCT else ""

    ax.pie(values,
           autopct=_autopct,
           startangle=90,
           colors=colors,
           wedgeprops=dict(width=DONUT_WIDTH, edgecolor=panel_color,
                           linewidth=2),
           pctdistance=0.8,
           textprops={"color": "white", "weight": "bold"})
    ax.legend([f"{area} — {value:.0f}%" for area, value in items],
              loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, fontsize=9)
