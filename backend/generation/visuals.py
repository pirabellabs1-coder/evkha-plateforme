"""Visuels de respiration inseres entre certains chapitres (charte EVKHA).

Objectif : casser la monotonie d'un long document rédactionnel en injectant,
à des points strategiques et deterministes, une "page respiration" visuelle
avec icones + mini-schema (grille de cartes, podium 3 blocs, mini
chronologie). Aucun token Claude n'est consomme : tout est genere cote
template, donc aucun risque de troncature max_tokens.

Le style suit la charte EVKHA (fond creme, filet or, bord fin) et l'ADN
graphique observe sur les modeles existants (Kenya4U, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from catalog.models import DeliverableType

# ── Bibliotheque d'icones SVG (~24x24, fill=currentColor pilote par CSS) ─────

_ICONS: dict[str, str] = {
    "growth": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M3 20h18v1H3z"/>'
        '<path d="M4 18l5-6 4 3 6-8 2 2v9z" opacity="0.85"/>'
        "</svg>"
    ),
    "target": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 3a9 9 0 100 18 9 9 0 000-18zm0 3a6 6 0 110 12 6 6 0 010-12z"'
        ' fill-rule="evenodd"/>'
        '<circle cx="12" cy="12" r="2.5"/>'
        "</svg>"
    ),
    "compass": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 2a8 8 0 110 16 8 8 0 010-16z"/>'
        '<path d="M15.5 8.5l-2 5.5-5.5 2 2-5.5z"/>'
        "</svg>"
    ),
    "network": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="12" cy="5" r="2.4"/>'
        '<circle cx="5" cy="18" r="2.4"/>'
        '<circle cx="19" cy="18" r="2.4"/>'
        '<path d="M12 7.4L5.8 16m6.2-8.6L18.2 16M6.5 18h11" '
        'stroke="currentColor" stroke-width="1.4" fill="none"/>'
        "</svg>"
    ),
    "people": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="8" cy="9" r="3"/>'
        '<circle cx="17" cy="10" r="2.5"/>'
        '<path d="M2 20c0-3.3 2.7-6 6-6s6 2.7 6 6zm12-1c0-2.4 1.9-4 4-4s4 1.6 4 4z"/>'
        "</svg>"
    ),
    "location": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 2a7 7 0 00-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 00-7-7z"/>'
        '<circle cx="12" cy="9" r="2.5" fill="#fff"/>'
        "</svg>"
    ),
    "finance": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M12 6.5v11m3-8.2c-.7-.9-1.8-1.4-3-1.4-1.8 0-3 .9-3 2.3 '
        "0 1.2 1 1.9 2.4 2.3l1.4.3c1.4.4 2.4 1 2.4 2.3 0 1.4-1.2 2.3-3 2.3"
        '-1.4 0-2.5-.6-3.1-1.7"'
        ' stroke="#fff" stroke-width="1.4" fill="none" stroke-linecap="round"/>'
        "</svg>"
    ),
    "planning": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="3.5" y="5" width="17" height="15" rx="1.4"/>'
        '<path d="M3.5 9h17" stroke="#fff" stroke-width="1.4" fill="none"/>'
        '<path d="M8 3v4M16 3v4" stroke="currentColor" stroke-width="1.6" '
        'stroke-linecap="round" fill="none"/>'
        '<circle cx="8" cy="14" r="1.3" fill="#fff"/>'
        '<circle cx="12" cy="14" r="1.3" fill="#fff"/>'
        '<circle cx="16" cy="14" r="1.3" fill="#fff"/>'
        "</svg>"
    ),
    "shield": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/>'
        '<path d="M8.5 12l2.5 2.5L16 10" stroke="#fff" stroke-width="1.6" '
        'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    ),
    "spark": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 2l1.8 5.7L19.5 9l-5 3.4L16 19l-4-3.4L8 19l1.5-6.6L4.5 9l5.7-1.3z"/>'
        "</svg>"
    ),
    "lightbulb": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 3a6 6 0 00-4 10.4V17h8v-3.6A6 6 0 0012 3z"/>'
        '<path d="M9 19h6v1a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>'
        "</svg>"
    ),
    "graph": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="3" y="12" width="4" height="9" rx="0.6"/>'
        '<rect x="10" y="7" width="4" height="14" rx="0.6"/>'
        '<rect x="17" y="3" width="4" height="18" rx="0.6"/>'
        "</svg>"
    ),
    "handshake": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M3 12l4-4 3 2 3-2 3 2 5-1v6l-5 3-3-1-3 2-3-1-4 1z"/>'
        "</svg>"
    ),
    "clock": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="12" cy="12" r="9"/>'
        '<path d="M12 7v5l3.5 2" stroke="#fff" stroke-width="1.6" '
        'stroke-linecap="round" fill="none"/>'
        "</svg>"
    ),
}


_ICON_GOLD = "#C9A227"
_ICON_WHITE = "#ffffff"


def _icon(name: str, *, color: str = _ICON_GOLD) -> str:
    """Retourne le SVG inline de l'icone avec fill hardcode.

    WeasyPrint (au moins 62.x) ne resout pas `currentColor` ni `fill: currentColor`
    en CSS via la propriete color du parent HTML : les paths SVG restent noirs.
    Contournement fiable : injecter le hex de la couleur directement dans le SVG
    via un <g fill="HEX"> englobant. Les enfants avec fill explicite (blanc,
    none...) conservent leur override.
    """
    body = _ICONS.get(name, _ICONS["spark"])
    open_tag_end = body.find(">") + 1
    inner = body[open_tag_end : -len("</svg>")]
    return f'{body[:open_tag_end]}<g fill="{color}">{inner}</g></svg>'


# ── Modele de donnees ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VisualItem:
    icon: str
    title: str
    description: str = ""


@dataclass(frozen=True)
class VisualBreak:
    after_chapter_number: int
    variant: str  # "icon_cards" | "podium" | "chronology"
    title: str
    subtitle: str
    items: tuple[VisualItem, ...] = field(default_factory=tuple)


# ── Rendu HTML par variante ──────────────────────────────────────────────────


def _render_icon_cards(vb: VisualBreak) -> str:
    # Badges en cercle dore -> icones blanches.
    cards = "".join(
        (
            '<div class="evkha-visual__card">'
            f'<div class="evkha-visual__icon">{_icon(item.icon, color=_ICON_WHITE)}</div>'
            f'<div class="evkha-visual__card-title">{escape(item.title)}</div>'
            f'<div class="evkha-visual__card-desc">{escape(item.description)}</div>'
            "</div>"
        )
        for item in vb.items
    )
    return (
        '<div class="evkha-visual evkha-visual--cards">'
        f'<div class="evkha-visual__title">{escape(vb.title)}</div>'
        f'<div class="evkha-visual__subtitle">{escape(vb.subtitle)}</div>'
        f'<div class="evkha-visual__grid">{cards}</div>'
        "</div>"
    )


def _render_podium(vb: VisualBreak) -> str:
    # Ordre visuel : gauche (bas), centre (haut), droite (milieu).
    items = list(vb.items)[:3]
    while len(items) < 3:
        items.append(VisualItem("spark", "", ""))
    # Podium : cercles blancs avec bord or -> icones dorees dans tous les cas.
    blocks = "".join(
        (
            f'<div class="evkha-visual__pillar evkha-visual__pillar--{position}">'
            f'<div class="evkha-visual__pillar-icon">{_icon(item.icon, color=_ICON_GOLD)}</div>'
            f'<div class="evkha-visual__pillar-title">{escape(item.title)}</div>'
            f'<div class="evkha-visual__pillar-desc">{escape(item.description)}</div>'
            "</div>"
        )
        for item, position in zip(items, ("left", "center", "right"), strict=False)
    )
    return (
        '<div class="evkha-visual evkha-visual--podium">'
        f'<div class="evkha-visual__title">{escape(vb.title)}</div>'
        f'<div class="evkha-visual__subtitle">{escape(vb.subtitle)}</div>'
        f'<div class="evkha-visual__podium">{blocks}</div>'
        "</div>"
    )


def _render_chronology(vb: VisualBreak) -> str:
    # Marqueurs en cercle dore -> icones blanches.
    steps = "".join(
        (
            '<div class="evkha-visual__step">'
            f'<div class="evkha-visual__step-marker">{_icon(item.icon, color=_ICON_WHITE)}</div>'
            f'<div class="evkha-visual__step-title">{escape(item.title)}</div>'
            f'<div class="evkha-visual__step-desc">{escape(item.description)}</div>'
            "</div>"
        )
        for item in vb.items
    )
    return (
        '<div class="evkha-visual evkha-visual--chrono">'
        f'<div class="evkha-visual__title">{escape(vb.title)}</div>'
        f'<div class="evkha-visual__subtitle">{escape(vb.subtitle)}</div>'
        f'<div class="evkha-visual__chrono">{steps}</div>'
        "</div>"
    )


def _render_icon_cards_left(vb: VisualBreak) -> str:
    """Grille 2 colonnes : icone a gauche, titre + description a droite.

    Style inspire de la charte des livrables strategiques haut de gamme (voir
    modele "Typologie clients"). Chaque item occupe une cellule de tableau,
    2 par ligne.
    """
    cells = "".join(
        (
            '<div class="evkha-visual__row">'
            f'<div class="evkha-visual__row-icon">{_icon(item.icon, color=_ICON_GOLD)}</div>'
            '<div class="evkha-visual__row-body">'
            f'<div class="evkha-visual__row-title">{escape(item.title)}</div>'
            f'<div class="evkha-visual__row-desc">{escape(item.description)}</div>'
            "</div>"
            "</div>"
        )
        for item in vb.items
    )
    return (
        '<div class="evkha-visual evkha-visual--cards-left">'
        f'<div class="evkha-visual__title">{escape(vb.title)}</div>'
        f'<div class="evkha-visual__subtitle">{escape(vb.subtitle)}</div>'
        f'<div class="evkha-visual__rows">{cells}</div>'
        "</div>"
    )


def _render_chevron_flow(vb: VisualBreak) -> str:
    """Flow de chevrons numerotes horizontaux (style Kenya4U "Frequence d'achat").

    Chaque chevron = 1 case avec numero en gros, titre + description dessous.
    Aspect fleche via clip-path CSS (supporte par WeasyPrint) sur le bloc SVG.
    Rendu robuste : polygones SVG en fond, pas de clip-path (fallback CSS).
    """
    items = list(vb.items)[:5]
    steps = "".join(
        (
            f'<div class="evkha-visual__chevron evkha-visual__chevron--{idx}">'
            '<div class="evkha-visual__chevron-shape">'
            '<svg viewBox="0 0 100 60" xmlns="http://www.w3.org/2000/svg" '
            'preserveAspectRatio="none">'
            f'<polygon points="0,0 85,0 100,30 85,60 0,60 15,30" fill="{_ICON_GOLD}"/>'
            "</svg>"
            f'<div class="evkha-visual__chevron-number">{idx + 1}</div>'
            "</div>"
            f'<div class="evkha-visual__chevron-title">{escape(item.title)}</div>'
            f'<div class="evkha-visual__chevron-desc">{escape(item.description)}</div>'
            "</div>"
        )
        for idx, item in enumerate(items)
    )
    return (
        '<div class="evkha-visual evkha-visual--chevrons">'
        f'<div class="evkha-visual__title">{escape(vb.title)}</div>'
        f'<div class="evkha-visual__subtitle">{escape(vb.subtitle)}</div>'
        f'<div class="evkha-visual__chevrons">{steps}</div>'
        "</div>"
    )


def _render_process_circles(vb: VisualBreak) -> str:
    """Cercles connectes horizontaux (style Kenya4U "Processus de vente").

    Chaque etape = 1 cercle avec icone + label dessous. Les cercles sont
    relies visuellement par un filet horizontal or (via ::before absolu).
    """
    steps = "".join(
        (
            '<div class="evkha-visual__circle">'
            f'<div class="evkha-visual__circle-shape">{_icon(item.icon, color=_ICON_GOLD)}</div>'
            f'<div class="evkha-visual__circle-label">{escape(item.title)}</div>'
            f'<div class="evkha-visual__circle-desc">{escape(item.description)}</div>'
            "</div>"
        )
        for item in vb.items
    )
    return (
        '<div class="evkha-visual evkha-visual--circles">'
        f'<div class="evkha-visual__title">{escape(vb.title)}</div>'
        f'<div class="evkha-visual__subtitle">{escape(vb.subtitle)}</div>'
        f'<div class="evkha-visual__circles">{steps}</div>'
        "</div>"
    )


_RENDERERS = {
    "icon_cards": _render_icon_cards,
    "icon_cards_left": _render_icon_cards_left,
    "podium": _render_podium,
    "chronology": _render_chronology,
    "chevron_flow": _render_chevron_flow,
    "process_circles": _render_process_circles,
}


def render_visual_break(vb: VisualBreak) -> str:
    renderer = _RENDERERS.get(vb.variant, _render_icon_cards)
    return renderer(vb)


# ── Table d'insertion par type de livrable ───────────────────────────────────
# Chaque visuel est genere APRES le chapitre indique (avant le suivant). Les
# contenus sont volontairement generiques-strategiques : ils s'inserent dans
# n'importe quel projet du meme type de livrable sans risquer d'inventer des
# faits.

_MARKET_STUDY_BREAKS: tuple[VisualBreak, ...] = (
    VisualBreak(
        after_chapter_number=0,
        variant="icon_cards",
        title="Ce que cette étude va explorer",
        subtitle="Les quatre dimensions clés d'une lecture de marché EVKHA",
        items=(
            VisualItem("graph", "Le marché", "Taille, croissance et dynamiques observables"),
            VisualItem("target", "La cible", "Profils, besoins réels et critères de décision"),
            VisualItem(
                "network", "La concurrence",
                "Acteurs installés, substituts et zones libres",
            ),
            VisualItem("spark", "Les opportunités", "Signaux favorables et fenêtres à saisir"),
        ),
    ),
    VisualBreak(
        after_chapter_number=5,
        variant="chevron_flow",
        title="Le rythme d'analyse d'un marché",
        subtitle="Trois temps pour construire une lecture opérationnelle",
        items=(
            VisualItem("compass", "Cadrer", "Définir périmètre, cible et zone géographique"),
            VisualItem("graph", "Quantifier", "Chiffrer volumes, dynamiques et segments"),
            VisualItem("lightbulb", "Décider", "Traduire l'analyse en priorités concrètes"),
        ),
    ),
    VisualBreak(
        after_chapter_number=9,
        variant="icon_cards_left",
        title="Trois familles de clientèle à distinguer",
        subtitle="Les registres d'achat que l'on retrouve dans presque tous les marchés",
        items=(
            VisualItem(
                "people", "Le cœur de marché",
                "Volume principal, standards attendus, sensibilité au rapport qualité/prix",
            ),
            VisualItem(
                "spark", "Les early adopters",
                "Curiosité forte, tolérance à l'imperfection, prescription précieuse",
            ),
            VisualItem(
                "shield", "La clientèle premium",
                "Attentes fortes en expérience et personnalisation, moins sensible au prix",
            ),
            VisualItem(
                "location", "Les segments périphériques",
                "Usages ponctuels ou de niche, potentiel réel mais moins prioritaire",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=11,
        variant="podium",
        title="Trois leviers d'opportunité à activer",
        subtitle="Les axes récurrents des projets qui prennent leur place",
        items=(
            VisualItem(
                "compass", "Différenciation",
                "Un positionnement clair, défendable et lisible du premier contact",
            ),
            VisualItem(
                "growth", "Croissance",
                "Une trajectoire alignée avec les dynamiques réelles du marché",
            ),
            VisualItem(
                "clock", "Timing",
                "Un lancement calé sur les signaux favorables identifiés",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=15,
        variant="process_circles",
        title="La séquence d'achat observée sur ce marché",
        subtitle="Quatre étapes typiques du parcours client",
        items=(
            VisualItem("target", "Prise de conscience", "Le besoin devient explicite"),
            VisualItem("compass", "Recherche", "Comparaison, avis, prescription"),
            VisualItem("handshake", "Décision", "Choix d'un acteur ou d'une offre"),
            VisualItem("spark", "Fidélisation", "Renouvellement et recommandation"),
        ),
    ),
    VisualBreak(
        after_chapter_number=19,
        variant="chronology",
        title="Trois phases après cette étude",
        subtitle="La lecture stratégique passe à l'exécution",
        items=(
            VisualItem(
                "shield", "1. Confirmer",
                "Valider les hypothèses critiques par des tests concrets",
            ),
            VisualItem(
                "spark", "2. Lancer",
                "Mettre en marché avec une offre calibrée et un canal prioritaire",
            ),
            VisualItem(
                "growth", "3. Consolider",
                "Fidéliser, industrialiser, préparer la montée en puissance",
            ),
        ),
    ),
)

_COMPETITOR_STUDY_BREAKS: tuple[VisualBreak, ...] = (
    VisualBreak(
        after_chapter_number=0,
        variant="icon_cards",
        title="Le paysage concurrentiel en quatre lectures",
        subtitle="Ce qu'une étude concurrentielle EVKHA regarde en priorité",
        items=(
            VisualItem(
                "handshake", "Concurrents directs",
                "Mêmes offres, mêmes cibles : les 8 plus influents",
            ),
            VisualItem(
                "network", "Concurrents indirects",
                "Substituts et alternatives : les 3 plus stratégiques",
            ),
            VisualItem(
                "target", "Zones libres",
                "Territoires où personne ne se positionne encore vraiment",
            ),
            VisualItem(
                "spark", "Signaux faibles",
                "Nouveaux entrants et modèles émergents à surveiller",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=2,
        variant="chevron_flow",
        title="La lecture qualitative en trois temps",
        subtitle="La méthode utilisée pour évaluer chaque concurrent identifié",
        items=(
            VisualItem("target", "Identifier", "Repérer les acteurs pertinents pour le projet"),
            VisualItem("compass", "Analyser", "Décrypter positionnement, offre et clientèle"),
            VisualItem("lightbulb", "Positionner", "En déduire un territoire à occuper"),
        ),
    ),
    VisualBreak(
        after_chapter_number=5,
        variant="podium",
        title="Trois axes de positionnement défendables",
        subtitle="Les grandes familles de différenciation qui tiennent dans la durée",
        items=(
            VisualItem(
                "finance", "Prix / accessibilité",
                "Offrir plus de valeur perçue à niveau de tarif équivalent",
            ),
            VisualItem(
                "spark", "Expérience",
                "Sortir du lot par la qualité du parcours et de la relation",
            ),
            VisualItem(
                "compass", "Spécialisation",
                "S'imposer sur un segment précis mal servi par les leaders",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=6,
        variant="icon_cards_left",
        title="Comment lire les parts de marché estimées",
        subtitle="Les quatre angles qui rendent la lecture opérationnelle",
        items=(
            VisualItem(
                "graph", "La taille du gâteau",
                "Ordre de grandeur du chiffre d'affaires total accessible",
            ),
            VisualItem(
                "handshake", "La concentration",
                "Nombre d'acteurs qui captent l'essentiel du marché",
            ),
            VisualItem(
                "spark", "Les zones de vitalité",
                "Segments et acteurs qui tirent la croissance",
            ),
            VisualItem(
                "target", "Les fenêtres d'entrée",
                "Écarts entre offre existante et demande réelle",
            ),
        ),
    ),
)

_BUSINESS_PLAN_BREAKS: tuple[VisualBreak, ...] = (
    VisualBreak(
        after_chapter_number=0,
        variant="icon_cards",
        title="Les quatre piliers de ce business plan",
        subtitle="Ce qu'un lecteur (banquier, financeur, associé) va chercher",
        items=(
            VisualItem("target", "Le marché", "Une demande réelle, quantifiée et accessible"),
            VisualItem("lightbulb", "L'offre", "Une proposition claire, cohérente avec la cible"),
            VisualItem(
                "graph", "Le modèle économique",
                "Des revenus lisibles, une trajectoire crédible",
            ),
            VisualItem(
                "finance", "Le financement",
                "Un besoin chiffré, un plan de retour aligné",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=5,
        variant="chevron_flow",
        title="La logique de construction d'un business plan",
        subtitle="Trois étages qui doivent tenir chacun à part et ensemble",
        items=(
            VisualItem("target", "Le projet", "Ce que l'on veut faire, pour qui, pourquoi"),
            VisualItem("lightbulb", "Le modèle", "Comment ça marche concrètement au quotidien"),
            VisualItem("finance", "Les chiffres", "Ce que ça coûte, ce que ça rapporte, quand"),
        ),
    ),
    VisualBreak(
        after_chapter_number=8,
        variant="process_circles",
        title="Le parcours d'un client type",
        subtitle="Quatre moments décisifs entre la découverte et la fidélisation",
        items=(
            VisualItem("spark", "Découverte", "Premier contact avec l'offre"),
            VisualItem("compass", "Considération", "Comparaison et intention d'achat"),
            VisualItem("handshake", "Achat", "Décision et transaction"),
            VisualItem("shield", "Fidélisation", "Renouvellement et prescription"),
        ),
    ),
    VisualBreak(
        after_chapter_number=11,
        variant="podium",
        title="Trois fondations pour bien démarrer",
        subtitle="Ce qui fait la solidité opérationnelle des dix-huit premiers mois",
        items=(
            VisualItem(
                "people", "L'équipe",
                "Compétences réunies, rôles clairs, capacité d'exécution",
            ),
            VisualItem(
                "planning", "L'organisation",
                "Processus, outils et rythme adaptés à la taille visée",
            ),
            VisualItem(
                "shield", "La sécurisation",
                "Cadre juridique, financier et opérationnel maîtrisé",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=15,
        variant="icon_cards_left",
        title="Les quatre postes qui structurent le budget",
        subtitle="Là où l'essentiel du besoin de financement se joue",
        items=(
            VisualItem(
                "location", "Investissements",
                "Matériel, aménagements, outils digitaux, dépôts de garantie",
            ),
            VisualItem(
                "people", "Ressources humaines",
                "Salaires, charges, recrutement, formation initiale",
            ),
            VisualItem(
                "planning", "Fonctionnement",
                "Loyer, énergie, communication, prestataires récurrents",
            ),
            VisualItem(
                "finance", "Trésorerie de sécurité",
                "Marge de manœuvre pour absorber le démarrage commercial",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=17,
        variant="chronology",
        title="Trois horizons de trajectoire",
        subtitle="La lecture financière projetée sur trois exercices",
        items=(
            VisualItem(
                "spark", "Année 1 · Amorçage",
                "Traction initiale, ajustement de l'offre, premiers clients",
            ),
            VisualItem(
                "growth", "Année 2 · Structuration",
                "Consolidation commerciale, industrialisation, premiers recrutements",
            ),
            VisualItem(
                "target", "Année 3 · Montée en puissance",
                "Volumes stabilisés, rentabilité, préparation du palier suivant",
            ),
        ),
    ),
)

_BUSINESS_STRATEGY_BREAKS: tuple[VisualBreak, ...] = (
    VisualBreak(
        after_chapter_number=0,
        variant="icon_cards",
        title="Quatre territoires stratégiques à travailler",
        subtitle="Les leviers récurrents d'une stratégie business EVKHA",
        items=(
            VisualItem(
                "compass", "Positionnement",
                "Le territoire choisi et la promesse défendue face au marché",
            ),
            VisualItem(
                "lightbulb", "Offre",
                "L'architecture qui rend cette promesse concrète et achetable",
            ),
            VisualItem(
                "network", "Acquisition",
                "Les canaux qui amènent les bons clients, au bon rythme",
            ),
            VisualItem(
                "graph", "Pilotage",
                "Les indicateurs qui rendent la trajectoire lisible mois après mois",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=5,
        variant="chevron_flow",
        title="La séquence stratégique EVKHA",
        subtitle="Trois temps pour bâtir une stratégie qui tient",
        items=(
            VisualItem("compass", "Lire", "Comprendre la position réelle et ses tensions"),
            VisualItem("lightbulb", "Choisir", "Trancher un cap et des priorités claires"),
            VisualItem("planning", "Exécuter", "Traduire en offres, canaux et pilotage"),
        ),
    ),
    VisualBreak(
        after_chapter_number=7,
        variant="podium",
        title="Trois axes de différenciation à ancrer",
        subtitle="Les registres de valeur sur lesquels bâtir une position claire",
        items=(
            VisualItem(
                "spark", "Expertise",
                "Un savoir-faire reconnu, difficile à répliquer rapidement",
            ),
            VisualItem(
                "handshake", "Relation",
                "Une proximité et une qualité d'accompagnement distinctives",
            ),
            VisualItem(
                "planning", "Méthode",
                "Une démarche structurée qui sécurise le résultat pour le client",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=10,
        variant="process_circles",
        title="La logique d'une architecture d'offre",
        subtitle="Quatre étages qui se répondent pour couvrir tous les besoins",
        items=(
            VisualItem("spark", "Appel", "Une offre d'entrée qui fait découvrir"),
            VisualItem("target", "Cœur", "L'offre principale, celle qui génère le CA"),
            VisualItem("shield", "Fidélité", "Des offres de suivi qui retiennent"),
            VisualItem("growth", "Premium", "Un haut de gamme qui tire la valeur perçue"),
        ),
    ),
    VisualBreak(
        after_chapter_number=13,
        variant="icon_cards_left",
        title="Les quatre leviers d'acquisition à combiner",
        subtitle="Ne jamais dépendre d'une seule source de clients",
        items=(
            VisualItem(
                "compass", "Réseau et prescription",
                "Recommandations, partenariats, présence dans les cercles pertinents",
            ),
            VisualItem(
                "network", "Contenu et référencement",
                "Présence organique construite dans le temps sur les bons sujets",
            ),
            VisualItem(
                "spark", "Communication payante",
                "Accélérateur ciblé sur des campagnes calibrées et suivies",
            ),
            VisualItem(
                "handshake", "Prospection directe",
                "Approche ciblée des comptes ou décideurs à fort potentiel",
            ),
        ),
    ),
    VisualBreak(
        after_chapter_number=16,
        variant="chronology",
        title="Trois horizons stratégiques",
        subtitle="Séquencer la feuille de route sans tout attaquer de front",
        items=(
            VisualItem(
                "shield", "Court terme",
                "Sécuriser la base : offres cœur, canaux prioritaires, marges",
            ),
            VisualItem(
                "growth", "Moyen terme",
                "Consolider et industrialiser ce qui fonctionne durablement",
            ),
            VisualItem(
                "target", "Long terme",
                "Ouvrir de nouveaux terrains sans fragiliser l'existant",
            ),
        ),
    ),
)


_BREAKS_BY_DELIVERABLE: dict[str, tuple[VisualBreak, ...]] = {
    DeliverableType.MARKET_STUDY: _MARKET_STUDY_BREAKS,
    DeliverableType.COMPETITOR_STUDY: _COMPETITOR_STUDY_BREAKS,
    DeliverableType.BUSINESS_PLAN: _BUSINESS_PLAN_BREAKS,
    DeliverableType.BUSINESS_STRATEGY: _BUSINESS_STRATEGY_BREAKS,
}


def visual_breaks_html_for(deliverable_type: str) -> dict[int, str]:
    """Retourne {chapter_number: html_block} : le visuel est insere APRES le chapitre."""
    breaks = _BREAKS_BY_DELIVERABLE.get(deliverable_type, ())
    return {vb.after_chapter_number: render_visual_break(vb) for vb in breaks}
