"""Renderer SVG natif pour les graphiques inseres dans les livrables EVKHA.

Claude emet un bloc code fence ```chart contenant un JSON minimal decrivant
le graphique a produire. Le pipeline de rendu extrait ce bloc et le remplace
par un SVG inline dans le HTML final. WeasyPrint gere nativement le SVG, ce
qui donne un rendu vectoriel imprimable sans dependance externe.

Types supportes :
- ``bar`` : histogramme vertical simple (categories x valeurs)
- ``hbar`` : barres horizontales (classement, parts de marche)
- ``pie`` : camembert (segmentation, repartition)
- ``radar`` : radar comparatif (positionnement concurrentiel, evaluation
  multi-critere) — la signature "cabinet" classique

Le format JSON accepte est deliberement minimal :
    {
      "type": "bar" | "hbar" | "pie" | "radar",
      "title": "Titre affiche au-dessus",
      "labels": ["cat1", "cat2", ...],
      "series": [
        {"name": "Serie 1", "values": [10, 20, 30]},
        ...
      ],
      "unit": " %"   // optionnel, suffixe des valeurs
    }

Pour un pie, on n'accepte qu'une seule serie. Pour un radar, chaque serie
represente un profil evalue sur les memes axes (labels). Pour bar/hbar,
plusieurs series produisent un groupement.

Palette : couleurs officielles EVKHA (Bloc 6 Consignes mai 2026).
"""
from __future__ import annotations

import json
import math
import re
from html import escape
from typing import Any

# Palette EVKHA (dupliquee de rendering.py pour ne pas creer d'import
# circulaire — ces constantes ne changent que sur decision de marque).
_PRIMARY = "#1A1A1A"
_SECONDARY = "#C9A227"
_SECONDARY_ALT = "#E4C65B"
_GRAY = "#5A5A5A"
_CREAM = "#FBF8EF"
_CREAM_DARK = "#EFEAD8"

# Ordre de la palette utilisee pour les series multiples (radar / bar groupes).
# L'or est en premier car c'est la couleur de marque : la premiere serie
# est toujours celle du client / du projet analyse.
_SERIES_COLORS: tuple[str, ...] = (
    _SECONDARY,       # or (client / projet analyse)
    _PRIMARY,         # noir (concurrent principal ou reference)
    _SECONDARY_ALT,   # or clair (concurrent secondaire)
    _GRAY,            # gris (concurrent tertiaire)
    "#8B6E1A",        # or fonce (variation supplementaire si besoin)
    "#3A3A3A",        # gris fonce
)


# Dimensions cibles SVG (viewBox). WeasyPrint met a l'echelle sur la largeur
# du bloc html parent — ces valeurs definissent seulement le ratio interne.
_W = 640
_H = 360


# Fence markdown ```chart ... ``` extractible partout dans le contenu.
_CHART_FENCE_RE = re.compile(
    r"^```chart\s*$([\s\S]*?)^```\s*$",
    re.MULTILINE,
)


def render_chart_svg(spec: dict[str, Any]) -> str:
    """Genere le SVG inline pour la spec fournie.

    Retourne une chaine vide si la spec est invalide — jamais d'exception :
    un graphique defaillant ne doit pas casser le PDF entier.
    """
    try:
        ctype = str(spec.get("type", "")).lower()
        title = str(spec.get("title", "")).strip()
        labels = [str(x) for x in spec.get("labels", [])]
        raw_series = spec.get("series", [])
        unit = str(spec.get("unit", "")).strip()
        series: list[tuple[str, list[float]]] = []
        for s in raw_series:
            name = str(s.get("name", "")).strip()
            values = [float(v) for v in s.get("values", [])]
            if values:
                series.append((name, values))

        if not series or not labels:
            return ""

        if ctype == "bar":
            body = _render_bar(labels, series, unit)
        elif ctype == "hbar":
            body = _render_hbar(labels, series, unit)
        elif ctype == "pie":
            body = _render_pie(labels, series[0][1], unit)
        elif ctype == "radar":
            body = _render_radar(labels, series)
        else:
            return ""

        if not body:
            return ""
        return _wrap_svg(title, body, series if ctype != "pie" else [])
    except (ValueError, TypeError, KeyError, IndexError):
        return ""


def replace_chart_fences(markdown: str) -> str:
    """Remplace chaque bloc ```chart ...``` par le SVG correspondant.

    Utilise en post-processing avant la conversion Markdown -> HTML. Un bloc
    dont le JSON est invalide est retire silencieusement (log dans stderr
    sinon).
    """
    def _sub(match: re.Match[str]) -> str:
        payload = match.group(1).strip()
        try:
            spec = json.loads(payload)
        except json.JSONDecodeError:
            return ""
        svg = render_chart_svg(spec)
        # Une ligne vide autour du SVG pour que le parseur markdown ne le colle
        # pas au paragraphe suivant.
        return f"\n\n{svg}\n\n" if svg else ""

    return _CHART_FENCE_RE.sub(_sub, markdown)


# ---------------------------------------------------------------------------
# Renderers par type
# ---------------------------------------------------------------------------


def _wrap_svg(
    title: str, body: str, series: list[tuple[str, list[float]]]
) -> str:
    """Enveloppe le body dans un <svg> + titre + legende eventuelle."""
    legend = _legend(series) if len(series) > 1 else ""
    title_html = ""
    if title:
        title_html = (
            f'<text x="{_W // 2}" y="24" text-anchor="middle" '
            f'font-family="Georgia, serif" font-size="15" fill="{_PRIMARY}" '
            f'font-weight="600">{escape(title)}</text>'
        )
    return (
        f'<div class="evkha-chart" style="margin:4mm 0;text-align:center">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" '
        f'style="max-width:100%;height:auto;font-family:Georgia,serif">'
        f'{title_html}{body}'
        f'</svg>{legend}</div>'
    )


def _legend(series: list[tuple[str, list[float]]]) -> str:
    """Legende horizontale sous le SVG, sans emojis, style cabinet."""
    if not series:
        return ""
    items = []
    for i, (name, _) in enumerate(series):
        color = _SERIES_COLORS[i % len(_SERIES_COLORS)]
        items.append(
            f'<span style="display:inline-flex;align-items:center;'
            f'margin:0 8px;font-size:9.5pt;color:{_PRIMARY}">'
            f'<span style="display:inline-block;width:10px;height:10px;'
            f'background:{color};margin-right:4px;border-radius:2px"></span>'
            f'{escape(name)}</span>'
        )
    return (
        f'<div style="text-align:center;margin-top:2mm">{"".join(items)}</div>'
    )


def _fmt(value: float, unit: str = "") -> str:
    """Formatage compact des valeurs d'axe / d'etiquette."""
    if abs(value) >= 1000:
        text = f"{value:,.0f}".replace(",", " ")
    elif value == int(value):
        text = str(int(value))
    else:
        text = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text}{unit}"


def _nice_max(values: list[float]) -> float:
    """Borne haute d'axe arrondie a une valeur agreable."""
    vmax = max(values) if values else 1.0
    if vmax <= 0:
        return 1.0
    # float() explicite : typeshed declare `int.__pow__` avec un exposant
    # non-litteral comme renvoyant Any (le resultat peut etre int ou float).
    # Sans ce cast, `candidate` devient Any et la fonction ne garantit plus
    # son type de retour.
    magnitude = float(10 ** math.floor(math.log10(vmax)))
    for step in (1, 2, 2.5, 5, 10):
        candidate = step * magnitude
        if candidate >= vmax:
            return candidate
    return vmax


def _render_bar(
    labels: list[str],
    series: list[tuple[str, list[float]]],
    unit: str,
) -> str:
    """Histogramme vertical, groupe si plusieurs series."""
    n_series = len(series)
    n_cat = len(labels)
    margin_left, margin_right, margin_top, margin_bottom = 60, 20, 50, 60
    chart_w = _W - margin_left - margin_right
    chart_h = _H - margin_top - margin_bottom

    all_values = [v for _, vals in series for v in vals]
    vmax = _nice_max(all_values)

    parts: list[str] = []
    # Grille horizontale + axes Y
    for i in range(5):
        y = margin_top + (chart_h * i / 4)
        value = vmax * (1 - i / 4)
        parts.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left + chart_w}" '
            f'y2="{y:.1f}" stroke="{_CREAM_DARK}" stroke-width="0.5"/>'
        )
        parts.append(
            f'<text x="{margin_left - 6}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="9" fill="{_GRAY}">{_fmt(value, unit)}</text>'
        )

    slot_w = chart_w / max(n_cat, 1)
    bar_w = slot_w * 0.7 / max(n_series, 1)
    for ci, label in enumerate(labels):
        slot_x = margin_left + slot_w * ci
        # Etiquette de categorie
        parts.append(
            f'<text x="{slot_x + slot_w / 2:.1f}" y="{margin_top + chart_h + 18:.1f}" '
            f'text-anchor="middle" font-size="9.5" fill="{_PRIMARY}">'
            f'{escape(label)}</text>'
        )
        for si, (_, values) in enumerate(series):
            if ci >= len(values):
                continue
            value = values[ci]
            h = (value / vmax) * chart_h if vmax > 0 else 0
            x = slot_x + slot_w * 0.15 + bar_w * si
            y = margin_top + chart_h - h
            color = _SERIES_COLORS[si % len(_SERIES_COLORS)]
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                f'height="{h:.1f}" fill="{color}"/>'
            )
            # Valeur au-dessus de la barre (uniquement si serie unique
            # pour eviter la surcharge visuelle)
            if n_series == 1:
                parts.append(
                    f'<text x="{x + bar_w / 2:.1f}" y="{y - 4:.1f}" '
                    f'text-anchor="middle" font-size="9" fill="{_PRIMARY}" '
                    f'font-weight="600">{_fmt(value, unit)}</text>'
                )
    # Axes
    parts.append(
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" '
        f'y2="{margin_top + chart_h}" stroke="{_PRIMARY}" stroke-width="1"/>'
    )
    parts.append(
        f'<line x1="{margin_left}" y1="{margin_top + chart_h}" '
        f'x2="{margin_left + chart_w}" y2="{margin_top + chart_h}" '
        f'stroke="{_PRIMARY}" stroke-width="1"/>'
    )
    return "".join(parts)


def _render_hbar(
    labels: list[str],
    series: list[tuple[str, list[float]]],
    unit: str,
) -> str:
    """Barres horizontales (cas mono-serie prioritaire : classement)."""
    values = series[0][1]
    n = min(len(labels), len(values))
    margin_left, margin_right, margin_top, margin_bottom = 130, 60, 50, 30
    chart_w = _W - margin_left - margin_right
    chart_h = _H - margin_top - margin_bottom
    vmax = _nice_max(values[:n])

    parts: list[str] = []
    slot_h = chart_h / max(n, 1)
    bar_h = slot_h * 0.6
    for i in range(n):
        label = labels[i]
        value = values[i]
        y = margin_top + slot_h * i + (slot_h - bar_h) / 2
        w = (value / vmax) * chart_w if vmax > 0 else 0
        color = _SERIES_COLORS[i % len(_SERIES_COLORS)] if n <= 3 else _SECONDARY
        parts.append(
            f'<text x="{margin_left - 8}" y="{y + bar_h / 2 + 4:.1f}" '
            f'text-anchor="end" font-size="10" fill="{_PRIMARY}">'
            f'{escape(label)}</text>'
        )
        parts.append(
            f'<rect x="{margin_left}" y="{y:.1f}" width="{w:.1f}" '
            f'height="{bar_h:.1f}" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{margin_left + w + 6:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
            f'font-size="10" fill="{_PRIMARY}" font-weight="600">'
            f'{_fmt(value, unit)}</text>'
        )
    parts.append(
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" '
        f'y2="{margin_top + chart_h}" stroke="{_PRIMARY}" stroke-width="1"/>'
    )
    return "".join(parts)


def _render_pie(labels: list[str], values: list[float], unit: str) -> str:
    """Camembert simple avec etiquettes exterieures."""
    total = sum(values) or 1.0
    cx, cy = _W // 2, _H // 2 + 10
    r = 110
    angle = -math.pi / 2  # commence en haut
    parts: list[str] = []
    label_items: list[str] = []
    for i, (label, value) in enumerate(zip(labels, values, strict=False)):
        if value <= 0:
            continue
        sweep = (value / total) * 2 * math.pi
        end = angle + sweep
        large_arc = 1 if sweep > math.pi else 0
        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        x2 = cx + r * math.cos(end)
        y2 = cy + r * math.sin(end)
        color = _SERIES_COLORS[i % len(_SERIES_COLORS)]
        parts.append(
            f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} '
            f'A {r} {r} 0 {large_arc} 1 {x2:.1f} {y2:.1f} Z" '
            f'fill="{color}" stroke="#ffffff" stroke-width="1.5"/>'
        )
        # Etiquette au centre du secteur
        mid = angle + sweep / 2
        lx = cx + (r + 22) * math.cos(mid)
        ly = cy + (r + 22) * math.sin(mid)
        pct = (value / total) * 100
        anchor = "middle"
        if math.cos(mid) > 0.3:
            anchor = "start"
        elif math.cos(mid) < -0.3:
            anchor = "end"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="10" fill="{_PRIMARY}">{escape(label)} '
            f'({pct:.0f}%)</text>'
        )
        label_items.append(f"{label}: {_fmt(value, unit)}")
        angle = end
    return "".join(parts)


def _render_radar(
    labels: list[str],
    series: list[tuple[str, list[float]]],
) -> str:
    """Radar N-axes, plusieurs series superposees semi-transparentes."""
    n_axes = len(labels)
    if n_axes < 3:
        return ""
    cx, cy = _W // 2, _H // 2 + 10
    r = 130
    all_values = [v for _, vals in series for v in vals]
    vmax = max(_nice_max(all_values), 1.0)

    parts: list[str] = []
    # Grille polygonale (4 niveaux)
    for level in range(1, 5):
        pts = []
        rl = r * level / 4
        for i in range(n_axes):
            angle = -math.pi / 2 + 2 * math.pi * i / n_axes
            x = cx + rl * math.cos(angle)
            y = cy + rl * math.sin(angle)
            pts.append(f"{x:.1f},{y:.1f}")
        parts.append(
            f'<polygon points="{" ".join(pts)}" fill="none" '
            f'stroke="{_CREAM_DARK}" stroke-width="0.5"/>'
        )

    # Axes et etiquettes
    for i, label in enumerate(labels):
        angle = -math.pi / 2 + 2 * math.pi * i / n_axes
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="{_CREAM_DARK}" stroke-width="0.5"/>'
        )
        # Etiquette exterieure
        lx = cx + (r + 18) * math.cos(angle)
        ly = cy + (r + 18) * math.sin(angle)
        anchor = "middle"
        if math.cos(angle) > 0.3:
            anchor = "start"
        elif math.cos(angle) < -0.3:
            anchor = "end"
        # Ajuste verticalement pour les axes du haut et du bas
        dy = 4
        if math.sin(angle) < -0.5:
            dy = -2
        elif math.sin(angle) > 0.5:
            dy = 10
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + dy:.1f}" text-anchor="{anchor}" '
            f'font-size="10" fill="{_PRIMARY}">{escape(label)}</text>'
        )

    # Series superposees
    for si, (_, values) in enumerate(series):
        pts = []
        for i, value in enumerate(values[:n_axes]):
            angle = -math.pi / 2 + 2 * math.pi * i / n_axes
            rv = r * (value / vmax) if vmax > 0 else 0
            x = cx + rv * math.cos(angle)
            y = cy + rv * math.sin(angle)
            pts.append(f"{x:.1f},{y:.1f}")
        color = _SERIES_COLORS[si % len(_SERIES_COLORS)]
        parts.append(
            f'<polygon points="{" ".join(pts)}" fill="{color}" '
            f'fill-opacity="0.25" stroke="{color}" stroke-width="1.8"/>'
        )
    return "".join(parts)
