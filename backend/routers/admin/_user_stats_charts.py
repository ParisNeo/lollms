"""
Server-side chart rendering for per-user statistics exports.

Renders PNG charts from the already-computed ``UserStats`` payload (the same
data the admin modal displays) so the DOCX and PDF exports can embed real
graphs instead of tables only.

Rendering strategy (resolved lazily, in priority order):
  1. **matplotlib** (Agg backend) — highest quality, used when installed.
  2. **Pillow (PIL)** — dependency-light bar/line drawing that works on any
     host. Automatically chosen when matplotlib is unavailable so exports are
     never silently chart-less just because a heavyweight plotting stack is
     missing.

When neither backend is importable, ``is_available()`` returns False and
``build_charts`` returns an empty list — callers fall back to plain tables
instead of raising. No GUI backend is ever required (headless-safe) and every
figure/canvas is released after rendering to avoid leaks.
"""
from __future__ import annotations

import base64
import io
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ── Shared palette (kept in sync with the frontend modal) ───────────────────
_COLOR_WEBUI = "#6366f1"   # indigo
_COLOR_API = "#f59e0b"     # amber
_COLOR_TOTAL = "#10b981"   # emerald
_COLOR_INPUT = "#0ea5e9"   # sky
_COLOR_OUTPUT = "#f43f5e"  # rose
_COLOR_GRID = "#e5e7eb"
_COLOR_TEXT = "#374151"
_COLOR_BG = "#ffffff"

# ── Backend discovery (resolved once) ───────────────────────────────────────
# "_BACKEND" is one of "matplotlib", "pillow", or "" (unavailable).
_BACKEND: Optional[str] = None
_plt = None
_mdates = None
_PIL_Image = None
_PIL_ImageDraw = None
_PIL_ImageFont = None


def _load_backend() -> Optional[str]:
    """Import an available charting backend once; return its identifier."""
    global _BACKEND, _plt, _mdates, _PIL_Image, _PIL_ImageDraw, _PIL_ImageFont
    if _BACKEND is not None:
        return _BACKEND or None

    # 1) matplotlib (preferred): force the non-interactive Agg backend.
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt  # noqa: WPS433 (lazy by design)
        import matplotlib.dates as mdates  # noqa: WPS433
        _plt = plt
        _mdates = mdates
        _BACKEND = "matplotlib"
        return _BACKEND
    except Exception:
        pass

    # 2) Pillow fallback: draw bar/line charts by hand.
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: WPS433
        _PIL_Image = Image
        _PIL_ImageDraw = ImageDraw
        _PIL_ImageFont = ImageFont
        _BACKEND = "pillow"
        return _BACKEND
    except Exception:
        pass

    _BACKEND = ""
    return None


def is_available() -> bool:
    """True when charts can be rendered on this host (matplotlib or Pillow)."""
    return bool(_load_backend())


# ── Series normalisation ────────────────────────────────────────────────────
def _parse_day(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _daily_series_map(series: Any) -> Dict[str, int]:
    """Normalise a ``[{date, count}]`` series into an ordered ``{iso_day: n}``."""
    result: Dict[str, int] = {}
    for entry in (series or []):
        if not isinstance(entry, dict):
            continue
        day = _parse_day(entry.get("date"))
        if day is None:
            continue
        try:
            result[day.strftime("%Y-%m-%d")] = int(entry.get("count") or 0)
        except (TypeError, ValueError):
            result[day.strftime("%Y-%m-%d")] = 0
    return result


def _aligned_days(*maps: Dict[str, int], window_days: int = 30) -> List[str]:
    """Union of all series' days, sorted; falls back to a trailing 30-day window."""
    keys = set()
    for m in maps:
        keys.update(m.keys())
    if not keys:
        today = datetime.utcnow().date()
        return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(window_days - 1, -1, -1)]
    return sorted(keys)


# ── Backend-agnostic chart specs ─────────────────────────────────────────────
# Each spec fully describes a chart's title + data. Two renderers below turn a
# spec into PNG bytes, so both DOCX and PDF always get identical charts.
def _spec_tokens_over_time(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    webui = _daily_series_map(data.get("webui_tokens_per_day"))
    api = _daily_series_map(data.get("api_tokens_per_day"))
    if not webui and not api:
        return None
    days = _aligned_days(webui, api)
    return {
        "title": "Tokens per day (WebUI vs API)",
        "kind": "stacked_bar",
        "days": days,
        "is_dates": all(_parse_day(d) for d in days),
        "series": [
            {"label": "WebUI", "color": _COLOR_WEBUI, "values": [webui.get(d, 0) for d in days]},
            {"label": "API", "color": _COLOR_API, "values": [api.get(d, 0) for d in days]},
        ],
        "ylabel": "Tokens",
    }


def _spec_input_output(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    prompt = _daily_series_map(data.get("prompt_tokens_per_day"))
    completion = _daily_series_map(data.get("completion_tokens_per_day"))
    if not prompt and not completion:
        return None
    days = _aligned_days(prompt, completion)
    return {
        "title": "Input vs Output tokens",
        "kind": "line",
        "days": days,
        "is_dates": all(_parse_day(d) for d in days),
        "series": [
            {"label": "Input (prompt)", "color": _COLOR_INPUT, "values": [prompt.get(d, 0) for d in days]},
            {"label": "Output (completion)", "color": _COLOR_OUTPUT, "values": [completion.get(d, 0) for d in days]},
        ],
        "ylabel": "Tokens",
    }


def _spec_generations(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    gens = _daily_series_map(data.get("messages_per_day"))
    if not gens:
        return None
    days = _aligned_days(gens)
    return {
        "title": "Generations per day",
        "kind": "bar",
        "days": days,
        "is_dates": all(_parse_day(d) for d in days),
        "series": [
            {"label": "Generations", "color": _COLOR_TOTAL, "values": [gens.get(d, 0) for d in days]},
        ],
        "ylabel": "Generations",
    }


def _spec_top_models(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    models = data.get("top_models") or []
    labelled = []
    for m in models:
        if not isinstance(m, dict):
            continue
        name = str(m.get("model_name") or "unknown")
        try:
            tokens = int(m.get("total_tokens") or 0)
        except (TypeError, ValueError):
            tokens = 0
        labelled.append((name, tokens))
    if not labelled:
        return None
    labelled = labelled[:10]
    return {
        "title": "Top models by tokens",
        "kind": "hbar",
        "labels": [n for n, _ in labelled],
        "values": [v for _, v in labelled],
        "color": _COLOR_WEBUI,
        "xlabel": "Tokens",
    }


def _spec_weekday(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    mean = data.get("weekday_generation_mean") or {}
    if not isinstance(mean, dict) or not mean:
        return None
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    try:
        values = [float(mean.get(d) or 0) for d in order]
    except (TypeError, ValueError):
        values = [0.0] * len(order)
    if not any(values):
        return None
    return {
        "title": "Average generations per weekday",
        "kind": "bar",
        "days": [d[:3] for d in order],
        "is_dates": False,
        "series": [
            {"label": "Avg gens/day", "color": _COLOR_WEBUI, "values": values},
        ],
        "ylabel": "Avg gens / day",
    }


_SPEC_BUILDERS = (
    _spec_tokens_over_time,
    _spec_input_output,
    _spec_generations,
    _spec_top_models,
    _spec_weekday,
)


# ── matplotlib renderer ─────────────────────────────────────────────────────
def _render_matplotlib(spec: Dict[str, Any]) -> Optional[bytes]:
    kind = spec["kind"]
    fig = None
    try:
        if kind == "hbar":
            labels = spec["labels"]
            values = spec["values"]
            names = list(reversed(labels))
            vals = list(reversed(values))
            height = max(2.4, 0.42 * len(names) + 1.0)
            fig, ax = _plt.subplots(figsize=(9, height))
            ax.barh(names, vals, color=spec.get("color", _COLOR_WEBUI))
            ax.set_xlabel(spec.get("xlabel", ""))
            ax.tick_params(axis="y", labelsize=8)
            ax.tick_params(axis="x", labelsize=7)
            ax.grid(axis="x", alpha=0.25)
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)
        else:
            days = spec["days"]
            series = spec["series"]
            is_dates = spec.get("is_dates", False)
            x = [_parse_day(d) for d in days]
            fig, ax = _plt.subplots(figsize=(9, 3.2))
            if kind == "stacked_bar":
                bottoms = [0] * len(days)
                for s in series:
                    ax.bar(x, s["values"], bottom=bottoms, color=s["color"], label=s["label"], width=0.8)
                    bottoms = [b + v for b, v in zip(bottoms, s["values"])]
                ax.legend(fontsize=8, frameon=False)
            elif kind == "line":
                for s in series:
                    ax.plot(x, s["values"], color=s["color"], label=s["label"], linewidth=1.6)
                ax.legend(fontsize=8, frameon=False)
            else:  # bar
                s = series[0]
                if is_dates:
                    ax.bar(x, s["values"], color=s["color"], width=0.8)
                else:
                    xs = list(range(len(days)))
                    ax.bar(xs, s["values"], color=s["color"], width=0.8)
                    ax.set_xticks(xs)
                    ax.set_xticklabels(days, fontsize=8)
            if is_dates:
                ax.xaxis.set_major_formatter(_mdates.DateFormatter("%b %d"))
                fig.autofmt_xdate(rotation=30)
            ax.grid(axis="y", alpha=0.25)
            ax.tick_params(axis="x", labelsize=7)
            ax.tick_params(axis="y", labelsize=7)
            ax.set_ylabel(spec.get("ylabel", ""))
        ax.set_title(spec["title"], fontsize=11, fontweight="bold")
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
        return buffer.getvalue()
    except Exception:
        return None
    finally:
        if fig is not None:
            try:
                _plt.close(fig)
            except Exception:
                pass


# ── Pillow renderer (fallback) ───────────────────────────────────────────────
def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    h = (hex_str or "#888888").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return (128, 128, 128)


def _load_font(size: int):
    try:
        return _PIL_ImageFont.load_default(size=size)  # Pillow >= 10
    except Exception:
        try:
            return _PIL_ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return _PIL_ImageFont.load_default()


def _nice_max(value: float) -> float:
    """Round a positive max up to a readable, round-number axis bound."""
    if value <= 0:
        return 1.0
    magnitude = 10 ** (len(str(int(value))) - 1)
    step = magnitude if magnitude > 0 else 1
    return max(step, ((int(value) // step) + 1) * step)


def _new_canvas(width: int, height: int):
    img = _PIL_Image.new("RGB", (width, height), _hex_to_rgb(_COLOR_BG))
    return img, _PIL_ImageDraw.Draw(img)


def _render_pillow(spec: Dict[str, Any]) -> Optional[bytes]:
    try:
        kind = spec["kind"]
        W = 900
        margin_l, margin_r, margin_t, margin_b = 72, 24, 48, 62

        # ── Horizontal bar (top models) ──────────────────────────────────
        if kind == "hbar":
            labels = spec["labels"]
            values = spec["values"]
            rows = len(labels)
            H = max(260, 42 * rows + 70)
            img, draw = _new_canvas(W, H)
            draw.text((margin_l, 14), spec["title"], fill=_hex_to_rgb(_COLOR_TEXT), font=_load_font(18))
            small = _load_font(12)
            plot_w = W - margin_l - margin_r
            plot_h = H - margin_t - margin_b
            vmax = _nice_max(max(values) if values else 1)
            row_h = plot_h / max(rows, 1)
            for i, (label, value) in enumerate(zip(labels, values)):
                y = margin_t + i * row_h
                bar_h = max(8, row_h * 0.6)
                bw = int(plot_w * (value / vmax)) if vmax else 0
                draw.rectangle([margin_l, int(y), margin_l + bw, int(y + bar_h)],
                               fill=_hex_to_rgb(spec.get("color", _COLOR_WEBUI)))
                draw.text((margin_l - 8, int(y + bar_h / 2)), label[:22],
                          fill=_hex_to_rgb(_COLOR_TEXT), font=small, anchor="rm")
                draw.text((margin_l + bw + 4, int(y + bar_h / 2)), str(value),
                          fill=_hex_to_rgb(_COLOR_TEXT), font=small, anchor="lm")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        # ── Date/category charts ─────────────────────────────────────────
        days = spec["days"]
        series = spec["series"]
        is_dates = spec.get("is_dates", False)
        H = 340
        img, draw = _new_canvas(W, H)
        draw.text((margin_l, 14), spec["title"], fill=_hex_to_rgb(_COLOR_TEXT), font=_load_font(18))
        small = _load_font(12)

        plot_w = W - margin_l - margin_r
        plot_h = H - margin_t - margin_b
        all_vals = [v for s in series for v in s["values"]] or [0]
        vmax = _nice_max(max(all_vals))
        n = max(len(days), 1)

        # Horizontal gridlines + y-axis labels.
        for frac in (0.0, 0.5, 1.0):
            y = int(margin_t + plot_h * (1 - frac))
            draw.line([(margin_l, y), (W - margin_r, y)], fill=_hex_to_rgb(_COLOR_GRID))
            draw.text((margin_l - 8, y), str(int(vmax * frac)),
                      fill=_hex_to_rgb(_COLOR_TEXT), font=small, anchor="rm")

        def x_at(idx: int) -> int:
            if n == 1:
                return margin_l + plot_w // 2
            return margin_l + int(plot_w * idx / (n - 1))

        if kind == "line":
            for s in series:
                pts = [(x_at(i), int(margin_t + plot_h * (1 - (v / vmax if vmax else 0))))
                       for i, v in enumerate(s["values"])]
                if len(pts) >= 2:
                    draw.line(pts, fill=_hex_to_rgb(s["color"]), width=2)
                for p in pts:
                    draw.ellipse([p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2], fill=_hex_to_rgb(s["color"]))
            lx = margin_l
            for s in series:
                draw.rectangle([lx, H - 24, lx + 12, H - 12], fill=_hex_to_rgb(s["color"]))
                draw.text((lx + 16, H - 26), s["label"], fill=_hex_to_rgb(_COLOR_TEXT), font=small)
                lx += 16 + 8 * len(s["label"]) + 20
        else:  # bar / stacked_bar
            bar_w = max(2, int(plot_w / n * 0.7))
            for i in range(n):
                cx = margin_l + int(plot_w * (i + 0.5) / n)
                if kind == "bar":
                    s = series[0]
                    v = s["values"][i]
                    h = int(plot_h * (v / vmax if vmax else 0))
                    draw.rectangle([cx - bar_w // 2, margin_t + plot_h - h, cx + bar_w // 2, margin_t + plot_h],
                                   fill=_hex_to_rgb(s["color"]))
                else:  # stacked_bar
                    acc = 0
                    for s in series:
                        v = s["values"][i]
                        h = int(plot_h * (v / vmax if vmax else 0))
                        top = margin_t + plot_h - acc - h
                        draw.rectangle([cx - bar_w // 2, top, cx + bar_w // 2, margin_t + plot_h - acc],
                                       fill=_hex_to_rgb(s["color"]))
                        acc += h
            # Sparse x labels.
            step = max(1, n // 8)
            for i in range(0, n, step):
                cx = margin_l + int(plot_w * (i + 0.5) / n)
                label = str(days[i])[-6:] if is_dates else str(days[i])
                draw.text((cx, H - margin_b + 8), label,
                          fill=_hex_to_rgb(_COLOR_TEXT), font=small, anchor="mt")
            if kind == "stacked_bar":
                lx = margin_l
                for s in series:
                    draw.rectangle([lx, H - 24, lx + 12, H - 12], fill=_hex_to_rgb(s["color"]))
                    draw.text((lx + 16, H - 26), s["label"], fill=_hex_to_rgb(_COLOR_TEXT), font=small)
                    lx += 16 + 8 * len(s["label"]) + 20

        ylabel = spec.get("ylabel")
        if ylabel:
            draw.text((margin_l, margin_t - 20), ylabel, fill=_hex_to_rgb(_COLOR_TEXT), font=small)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _render(spec: Dict[str, Any]) -> Optional[bytes]:
    backend = _load_backend()
    if backend == "matplotlib":
        return _render_matplotlib(spec)
    if backend == "pillow":
        return _render_pillow(spec)
    return None


def build_charts(data: Dict[str, Any]) -> List[Tuple[str, bytes]]:
    """
    Render all applicable charts for a ``UserStats`` dict payload.

    Returns a list of ``(title, png_bytes)`` tuples in a fixed order. Returns an
    empty list only when *no* rendering backend (matplotlib or Pillow) is
    available, or the payload has no chartable series.
    """
    if not _load_backend():
        return []
    charts: List[Tuple[str, bytes]] = []
    for builder in _SPEC_BUILDERS:
        try:
            spec = builder(data)
        except Exception:
            spec = None
        if not spec:
            continue
        png = _render(spec)
        if png:
            charts.append((spec["title"], png))
    return charts


def png_to_data_uri(png_bytes: bytes) -> str:
    """Encode raw PNG bytes as a ``data:image/png;base64,...`` URI for HTML."""
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"