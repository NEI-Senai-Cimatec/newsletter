# tests/test_charts.py
import matplotlib

matplotlib.use("Agg")

from matplotlib.figure import Figure

from gui.theme.charts import (AREA_COLORS, DONUT_MIN_PCT, FIGURE_DPI,
                              PANEL_COLOR, QUIIN_PALETTE, TEXT_COLOR,
                              apply_theme, style_bars, style_donut)


def _fig_ax():
    fig = Figure(figsize=(5, 3), dpi=100)
    return fig, fig.add_subplot(111)


def test_palette_has_four_distinct_hex_colors():
    assert len(QUIIN_PALETTE) == 4
    assert len(set(QUIIN_PALETTE)) == 4
    assert all(c.startswith("#") and len(c) == 7 for c in QUIIN_PALETTE)


def test_apply_theme_matches_panel_and_tints_text():
    fig, ax = _fig_ax()
    ax.set_ylabel("Documentos")
    ax.legend(["x"])
    apply_theme(fig, ax)
    assert fig.get_dpi() == FIGURE_DPI
    assert fig.patch.get_facecolor()[:3] == matplotlib.colors.to_rgb(PANEL_COLOR)
    assert ax.get_facecolor()[:3] == matplotlib.colors.to_rgb(PANEL_COLOR)
    assert not ax.spines["top"].get_visible()
    assert not ax.spines["right"].get_visible()
    assert ax.yaxis.get_label().get_color() == TEXT_COLOR
    legend = ax.get_legend()
    assert legend is not None
    assert legend.get_frame_on() is False
    assert all(t.get_color() == TEXT_COLOR for t in legend.get_texts())


def test_style_bars_adds_value_labels_and_horizontal_ticks():
    fig, ax = _fig_ax()
    ax.bar([0, 1, 2], [3, 1, 2], label="Tecnológico")
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["2026-07", "2026-08", "2026-09"])
    style_bars(ax)
    rotations = {t.get_rotation() for t in ax.get_xticklabels()}
    assert rotations == {0.0}
    assert len(ax.texts) >= 3  # one value label per bar


def test_style_donut_hides_small_slice_labels_keeps_legend():
    fig, ax = _fig_ax()
    shares = {"Negócio/Economia": 70.0, "Tecnológico": 25.0,
              "Científico": 3.0, "Outros": 2.0}
    style_donut(ax, shares)
    autotexts = [t.get_text() for t in ax.texts]
    # only slices >= 5% carry a visible percentage; the rest are empty
    assert sorted(t for t in autotexts if t) == ["25%", "70%"]
    # zero-height bars carry no label
    fig2, ax2 = _fig_ax()
    ax2.bar([0, 1], [0, 4], label="x")
    style_bars(ax2)
    assert sorted(t.get_text() for t in ax2.texts if t.get_text()) == ["4"]
    legend = ax.get_legend()
    entries = [t.get_text() for t in legend.get_texts()]
    assert len(entries) == 4
    assert any(e.startswith("Científico —") for e in entries)
    assert any(e.startswith("Outros —") for e in entries)
    assert DONUT_MIN_PCT == 5.0
    assert len(ax.patches) == 4
    assert ax.patches[0].get_facecolor()[:3] == matplotlib.colors.to_rgb(
        AREA_COLORS["Negócio/Economia"])


def test_style_donut_skips_zero_share_areas():
    fig, ax = _fig_ax()
    style_donut(ax, {"Negócio/Economia": 100.0, "Tecnológico": 0.0,
                     "Científico": 0.0, "Outros": 0.0})
    assert len(ax.patches) == 1
    entries = [t.get_text() for t in ax.get_legend().get_texts()]
    assert entries == ["Negócio/Economia — 100%"]


def test_style_donut_legend_stays_inside_figure():
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    from gui.theme.charts import DONUT_ADJUST
    fig = Figure(figsize=(5, 3), dpi=FIGURE_DPI)
    ax = fig.add_subplot(111)
    style_donut(ax, {"Negócio/Economia": 55.5, "Tecnológico": 30.0,
                     "Científico": 12.5, "Outros": 2.0})
    apply_theme(fig, ax)
    fig.subplots_adjust(**DONUT_ADJUST)
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    legend_box = ax.get_legend().get_window_extent(
        renderer=canvas.get_renderer())
    assert legend_box.x1 <= fig.bbox.x1
    assert legend_box.x0 >= 0
