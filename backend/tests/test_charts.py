"""Verrous du renderer SVG et du pipeline d'extraction ```chart."""
from __future__ import annotations

from generation.charts import render_chart_svg, replace_chart_fences


def test_render_chart_svg_returns_empty_on_unknown_type() -> None:
    # Type inconnu : jamais d'exception, on renvoie une chaine vide pour ne
    # pas casser le PDF entier a cause d'un chart mal specifie.
    assert render_chart_svg({"type": "unknown", "labels": ["a"], "series": [
        {"name": "s", "values": [1]}
    ]}) == ""


def test_render_chart_svg_returns_empty_on_malformed_spec() -> None:
    # Payload sans series : rien a dessiner.
    assert render_chart_svg({"type": "bar", "labels": ["a"], "series": []}) == ""
    # Values non numeriques : la coercition float lance une ValueError, on
    # renvoie "" plutot que de propager (le renderer est fail-safe).
    assert render_chart_svg({
        "type": "bar", "labels": ["a"],
        "series": [{"name": "s", "values": ["not-a-number"]}],
    }) == ""


def test_render_chart_svg_bar_produces_svg() -> None:
    svg = render_chart_svg({
        "type": "bar",
        "title": "Chiffres cles",
        "labels": ["A", "B", "C"],
        "series": [{"name": "Marche", "values": [10, 20, 30]}],
        "unit": " %",
    })
    assert "<svg" in svg
    assert "Chiffres cles" in svg
    # Chaque categorie doit apparaitre dans les etiquettes.
    for cat in ("A", "B", "C"):
        assert f">{cat}<" in svg


def test_render_chart_svg_radar_needs_min_3_axes() -> None:
    # Radar avec 2 axes seulement : refuse (impossible de tracer un polygone
    # visuellement pertinent).
    assert render_chart_svg({
        "type": "radar", "labels": ["a", "b"],
        "series": [{"name": "X", "values": [3, 4]}],
    }) == ""


def test_render_chart_svg_radar_produces_polygons_per_series() -> None:
    svg = render_chart_svg({
        "type": "radar",
        "title": "Positionnement",
        "labels": ["Prix", "Qualite", "Notoriete", "Digital"],
        "series": [
            {"name": "Projet", "values": [4, 5, 3, 4]},
            {"name": "Concurrent", "values": [5, 3, 5, 4]},
        ],
    })
    assert "<svg" in svg
    # Une polygon de donnees par serie (en plus des polygones de grille) :
    # on doit trouver au moins 2 polygones avec fill-opacity (attribut
    # specifique aux polygones de series, pas a la grille).
    assert svg.count("fill-opacity") == 2
    # Legende avec les deux noms de series
    assert "Projet" in svg
    assert "Concurrent" in svg


def test_render_chart_svg_pie_shows_labels_with_percentages() -> None:
    svg = render_chart_svg({
        "type": "pie",
        "labels": ["Segment A", "Segment B"],
        "series": [{"name": "Repartition", "values": [30, 70]}],
    })
    assert "<svg" in svg
    assert "Segment A" in svg
    assert "70%" in svg or "70 %" in svg or "(70%)" in svg


def test_replace_chart_fences_inserts_svg_in_text() -> None:
    md = (
        "Paragraphe 1.\n\n"
        "```chart\n"
        '{"type":"bar","title":"Test","labels":["A","B"],'
        '"series":[{"name":"s","values":[1,2]}]}\n'
        "```\n\n"
        "Paragraphe 2."
    )
    out = replace_chart_fences(md)
    assert "```chart" not in out
    assert "<svg" in out
    assert "Paragraphe 1." in out
    assert "Paragraphe 2." in out


def test_replace_chart_fences_removes_invalid_json_silently() -> None:
    # JSON invalide : le fence est retire pour ne pas polluer le rendu, mais
    # le reste du texte est preserve. On ne veut jamais d'exception.
    md = (
        "Avant.\n\n"
        "```chart\n"
        "ceci n'est pas du JSON\n"
        "```\n\n"
        "Apres."
    )
    out = replace_chart_fences(md)
    assert "```chart" not in out
    assert "Avant." in out
    assert "Apres." in out
    assert "<svg" not in out


def test_replace_chart_fences_leaves_other_code_fences_intact() -> None:
    # Un fence ```html ou ```python ne doit pas etre touche par le remplaceur.
    md = "```html\n<p>hello</p>\n```"
    assert replace_chart_fences(md) == md
