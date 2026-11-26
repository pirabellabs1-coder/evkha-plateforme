"""Le HTML d'une lettre, réduit à ce qu'un courriel peut porter sans risque.

L'éditeur de l'administration produit du HTML ; il arrive ici par une API, et
une API se croit pas sur parole. Tout corps est passé par `nettoyer` AVANT
d'être enregistré — l'aperçu, l'essai et l'envoi lisent donc la même chose.

Une LISTE BLANCHE, pas une liste de choses interdites (règle 4) : balises,
attributs, propriétés de style et schémas d'adresse sont fermés. Ce qui n'y
figure pas disparaît — un `<script>`, un `onclick`, un `javascript:`, une
`position:fixed` qui recouvrirait le message.
"""
from __future__ import annotations

import re

import nh3

BALISES = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "a", "span", "mark",
    "h1", "h2", "h3", "ul", "ol", "li", "blockquote", "hr", "img",
}

#: `style` partout où l'éditeur pose une couleur ou un alignement.
ATTRIBUTS: dict[str, set[str]] = {
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height"},
    "span": {"style"},
    "mark": {"style"},
    "p": {"style"},
    "h1": {"style"},
    "h2": {"style"},
    "h3": {"style"},
    "li": {"style"},
}

STYLES = {"color", "background-color", "text-align", "font-size"}

#: Les VALEURS admises, propriété par propriété : une couleur s'écrit en
#: hexadécimal ou en `rgb()`, une taille entre 10 et 48 px. Tout le reste —
#: `url(...)`, `var(...)`, `calc(...)`, `99999px` — disparaît avec sa
#: déclaration. Liste blanche, encore (règle 4).
_COULEUR = re.compile(
    r"#[0-9a-f]{3,8}|rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(,\s*[\d.]+\s*)?\)"
)
_VALEURS: dict[str, re.Pattern[str]] = {
    "color": _COULEUR,
    "background-color": _COULEUR,
    "text-align": re.compile(r"left|right|center|justify"),
    "font-size": re.compile(r"(1\d|2\d|3\d|4[0-8])px"),
}

#: Un lien ou une image de courriel désigne une adresse COMPLÈTE : une adresse
#: relative (`/page`) ou sans schéma (`//ailleurs.example`) ne mène nulle part
#: depuis une messagerie, ou mène ailleurs que ce qu'elle laisse croire.
_ADRESSES = ("https://", "http://", "mailto:")


def _style_sur(valeur: str) -> str | None:
    gardees = []
    for declaration in valeur.split(";"):
        nom, _, brute = declaration.partition(":")
        nom, brute = nom.strip().lower(), brute.strip().lower()
        motif = _VALEURS.get(nom)
        if motif is not None and motif.fullmatch(brute):
            gardees.append(f"{nom}:{brute}")
    return ";".join(gardees) or None


def _filtrer(_balise: str, attribut: str, valeur: str) -> str | None:
    if attribut in ("href", "src"):
        return valeur if valeur.strip().lower().startswith(_ADRESSES) else None
    if attribut == "style":
        return _style_sur(valeur)
    return valeur

SCHEMAS = {"http", "https", "mailto"}

#: Styles posés d'office, EN LIGNE : les messageries ignorent les feuilles de
#: style. Une image ne déborde jamais du cadre de 600 px.
_STYLES_IMPOSES: dict[str, dict[str, str]] = {
    "img": {"style": "max-width:100%;height:auto;display:block;margin:12px auto;border:0"},
    "blockquote": {
        "style": "margin:16px 0;padding:4px 16px;border-left:3px solid #c8a24a;color:#555555"
    },
    "hr": {"style": "border:0;border-top:1px solid #e6e6e6;margin:24px 0"},
}

#: Un lien de courriel s'ouvre ailleurs, et n'offre rien à la page qu'il ouvre.
_ATTRIBUTS_DE_LIEN = {"target": "_blank", "rel": "noopener noreferrer"}


def nettoyer(html: str) -> str:
    """Le corps tel qu'il sera enregistré, prévisualisé et envoyé.

    Deux passes : la première filtre ce qui vient de l'éditeur ; la seconde
    pose NOS styles, qui ne doivent pas passer par le filtre des styles
    permis (il viderait `max-width` et `border-left`, absents de la liste
    blanche parce que personne ne doit pouvoir les saisir).
    """
    filtre = nh3.clean(
        html or "",
        tags=BALISES,
        attributes=ATTRIBUTS,
        url_schemes=SCHEMAS,
        filter_style_properties=STYLES,
        attribute_filter=_filtrer,
        link_rel=None,
        strip_comments=True,
    )
    imposes = {balise: dict(valeurs) for balise, valeurs in _STYLES_IMPOSES.items()}
    imposes["a"] = dict(_ATTRIBUTS_DE_LIEN)
    permis = {balise: set(noms) for balise, noms in ATTRIBUTS.items()}
    for balise, valeurs in imposes.items():
        permis.setdefault(balise, set()).update(valeurs)
    return nh3.clean(
        filtre,
        tags=BALISES,
        attributes=permis,
        url_schemes=SCHEMAS,
        set_tag_attribute_values=imposes,
        link_rel=None,
        strip_comments=True,
    )
