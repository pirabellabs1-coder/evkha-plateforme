"""Strategy « Etude de marche » — le manuel EM.

Refonte apres retour Evangeline sur WAOME v1 (21/07/2026). Defauts nommes :

  - « TCAC mondial 20 % dans un chapitre, 31 % dans un autre »
  - « 40 Md$ 2024 -> 120 Md$ 2030 = 20 %, pas 31 % »
  - « marche francais 2,1 Md€ presente comme 16 % d'un marche europeen 3,6
    Md€ — le calcul donne 576 M€ »
  - « marche adressable 52-84 M€, 180-260 M€, 180-320 M€ selon chapitres »
  - « objectif 6-8 clients au total, mais graphique additionne a 12-16 »

Ce sont TOUS des defauts de coherence chiffree qu'un check textuel ne
peut pas voir. La solution structurelle : une BASE CHIFFREE CONSOLIDEE
produite apres les chapitres 1-2, re-injectee au contexte des chapitres
3+, et un check arithmetique qui verifie les relations declarees dans le
document (val_fin/val_deb pour un TCAC, X = pourcentage * Y, etc).

Sa methode manuelle (PDF « PROMPT FINAL VERSION 3 EM_EC ») explicite cette
etape : « Nous venons de terminer les chapitres 1 et 2 [...] peux-tu
consolider toutes les donnees clefs dans un tableau recapitulatif unique
[qui] servira de reference pour garantir la coherence de l'etude et
eviter toute contradiction dans les chapitres suivants ».

Cette strategy contient DEUX responsabilites :

1. `contexte_supplementaire()` : produire et injecter la base consolidee.
2. `problemes_de_coherence()` : verifier arithmetiquement le corpus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from catalog.models import DeliverableType
from generation.models import (
    ChapterGeneration,
    CoherenceFact,
    FactKind,
    GenerationJob,
)
from generation.strategies.base import (
    ContexteSupplementaire,
    ProblemeCoherence,
)

# ── Chapitres de reference et de destination ────────────────────────────────
# Apres les chapitres 1 et 2, on a en base tous les chiffres marche
# (taille_marche_mondial/continental/national, tcac_mondial/...). La base
# consolidee est injectee au contexte de tous les chapitres suivants.
_CHAPITRE_CONSOLIDATION = 2
# Chapitres 3 a 22 : les dix-neuf chapitres d'analyse, les sources (21) et
# l'annexe des reponses essentielles (22) — cf. blueprints.MARKET_STUDY_CHAPTERS.
#
# L'annexe en a besoin plus que tout autre : le manuel lui interdit d'introduire
# le moindre chiffre nouveau, et elle doit reprendre « exactement les memes
# chiffres, unites, dates et conclusions que dans les chapitres ». Sans la base
# consolidee, elle n'aurait rien contre quoi se verifier.
_CHAPITRES_CIBLES: tuple[int, ...] = tuple(range(3, 23))

# ── Tolerance arithmetique ──────────────────────────────────────────────────
# Une projection sur 6 ans a une marge acceptable liee aux arrondis
# successifs. On tolere 1 % d'ecart entre le TCAC declare et le TCAC
# recalcule a partir de (val_fin/val_deb)^(1/n) - 1. Au-dela, c'est un
# defaut de calcul, pas un arrondi.
_TOLERANCE_ARITHMETIQUE = 0.01


# ══════════════════════════════════════════════════════════════════════════
# 1. BASE CHIFFREE CONSOLIDEE
# ══════════════════════════════════════════════════════════════════════════


def _facts_par_cle(job: GenerationJob) -> dict[str, str]:
    """Extrait les faits verrouilles pertinents pour l'EM."""
    facts = CoherenceFact.objects.filter(
        job=job,
        is_locked=True,
        kind__in=(FactKind.MARKET_SIZE, FactKind.GROWTH_RATE),
    ).order_by("key")
    return {f.key: f.value for f in facts}


def base_consolidee_markdown(job: GenerationJob) -> str:
    """Genere le tableau de reference EM inspire de la methode manuelle."""
    facts = _facts_par_cle(job)
    if not facts:
        return ""

    def _get(cle: str) -> str:
        return facts.get(cle, "—")

    lignes = [
        "## BASE CHIFFREE CONSOLIDEE — reference pour tous les chapitres suivants",
        "",
        "Ce tableau consolide les chiffres cles produits aux chapitres 1 et 2. "
        "Chaque valeur ci-dessous est INTANGIBLE pour la suite du document. "
        "Toute mention d'un chiffre dans les chapitres 3 et au-dela DOIT :",
        "- soit reprendre EXACTEMENT une valeur de ce tableau,",
        "- soit etre derivee arithmetiquement de ces valeurs (dans ce cas, "
        "montrer le calcul),",
        "- soit citer une source publique differente avec URL.",
        "",
        "| Perimetre | Zone | Taille de marche | TCAC observe |",
        "|---|---|---|---|",
        f"| Mondial | Monde | {_get('taille_marche_mondial')} "
        f"| {_get('tcac_mondial')} |",
        f"| Continental | Zone macro | {_get('taille_marche_continental')} "
        f"| {_get('tcac_continental')} |",
        f"| National | Pays cible | {_get('taille_marche_national')} "
        f"| {_get('tcac_national')} |",
        "",
        "Si un chiffre est manquant (« — »), c'est qu'il n'a pas ete verrouille "
        "au chapitre 1 ou 2. Ne PAS l'inventer dans les chapitres suivants : "
        "signaler l'absence et poursuivre l'analyse sur les niveaux disponibles.",
    ]
    return "\n".join(lignes)


# ══════════════════════════════════════════════════════════════════════════
# 2. CHECKS ARITHMETIQUES
# ══════════════════════════════════════════════════════════════════════════

# Motif TCAC : « TCAC de X % » ou « croissance annuelle de X % ». On capture
# le pourcentage annonce ET le contexte pour retrouver la fenetre (val_deb,
# val_fin) dans la phrase englobante.
_TCAC_ANNONCE_RE = re.compile(
    r"(?:TCAC|taux\s+de\s+croissance(?:\s+annuel\s+moyen)?|"
    r"croissance\s+annuelle(?:\s+moyenne)?)"
    r"[^.\n]{0,60}?"
    r"(?:de|:|est\s+de|atteint|s['’]\s*[eé]l[eè]ve\s+[àa])\s*"
    r"(\d+(?:[.,]\d+)?)\s*%",
    re.IGNORECASE,
)

# Motif TCAC + NIVEAU : capture aussi le qualificatif geographique du meme
# TCAC pour permettre le regroupement inter-chapitres. WAOME a montre le
# defaut : « TCAC 20 % » chapitre 1 vs « TCAC 31 % » chapitre 8 pour le
# meme perimetre mondial. La cohérence intra-phrase n'attrape pas ca.
_TCAC_AVEC_NIVEAU_RE = re.compile(
    r"TCAC\b[^.\n]{0,40}?"
    r"(mondial|europ[ée]en|africain|asiatique|am[ée]ricain|"
    r"maghr[ée]bin|caribe[ée]n|national|hexagonal|francais)"
    r"[^.\n]{0,60}?"
    r"(?:de|:|est\s+de|retenu\s+(?:de|a)|retenu\s*:|atteint|"
    r"s['’]\s*[eé]l[eè]ve\s+[àa])\s*"
    r"(\d+(?:[.,]\d+)?)\s*%",
    re.IGNORECASE,
)

# Mapping qualificatif -> niveau canonique (partage avec `coherence.py`
# pour rester coherent : regle 5, une seule source).
_QUALIFIANT_VERS_NIVEAU: dict[str, str] = {
    "mondial":     "mondial",
    "européen":    "continental",
    "europeen":    "continental",
    "africain":    "continental",
    "asiatique":   "continental",
    "américain":   "continental",
    "americain":   "continental",
    "maghrébin":   "continental",
    "maghrebin":   "continental",
    "caribeen":    "continental",
    "caribéen":    "continental",
    "national":    "national",
    "hexagonal":   "national",
    "francais":    "national",
}

# Tolerance : deux TCAC differant de moins d'1 point sont consideres comme
# identiques (arrondis d'un chapitre a l'autre). Au-dela, c'est un choix
# editorial different — le lecteur ne saurait plus lequel retenir.
_ECART_TCAC_TOLERE = 1.0

# Motif projection : « de X en 2024 a Y en 2030 » — permet de verifier que
# le TCAC annonce est coherent avec l'evolution declaree.
_PROJECTION_RE = re.compile(
    r"(?:de|passer\s+de)\s+"
    r"(\d+(?:[.,]\d+)?)\s*(Md\$?|Md€|milliards?|M\$?|M€|millions?)"
    r"[^.\n]{0,40}?"
    r"(20\d{2})[^.\n]{0,80}?"
    r"[àa]\s+"
    r"(\d+(?:[.,]\d+)?)\s*(Md\$?|Md€|milliards?|M\$?|M€|millions?)"
    r"[^.\n]{0,40}?"
    r"(20\d{2})",
    re.IGNORECASE,
)

# Motif ratio : « X represente/correspond a/est 16 % du/d'un marche de Y »
_RATIO_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(Md\$?|Md€|milliards?|M\$?|M€|millions?)"
    r"[^.\n]{0,60}?"
    r"(?:represente|correspond\s+[àa]|est|constitue|equivaut\s+[àa])"
    r"[^.\n]{0,20}?"
    r"(\d+(?:[.,]\d+)?)\s*%"
    r"[^.\n]{0,60}?"
    r"(?:du|d['’]un|de\s+ce)[^.\n]{0,30}?"
    r"(\d+(?:[.,]\d+)?)\s*(Md\$?|Md€|milliards?|M\$?|M€|millions?)",
    re.IGNORECASE,
)


def _en_millions(valeur: float, unite: str) -> float:
    """Normalise en millions (l'unite de comparaison la plus lisible)."""
    u = unite.lower().rstrip("$").rstrip("€").rstrip(".")
    if u in ("md", "mds", "milliard", "milliards"):
        return valeur * 1000.0
    return valeur  # deja en millions


def verifier_tcac_projection(texte: str) -> list[str]:
    """Compare le TCAC annonce a celui recalcule depuis la projection."""
    problemes: list[str] = []
    for m in _PROJECTION_RE.finditer(texte):
        val_deb = _lire_nombre(m.group(1))
        val_fin = _lire_nombre(m.group(4))
        an_deb = int(m.group(3))
        an_fin = int(m.group(6))
        if val_deb <= 0 or an_fin <= an_deb:
            continue
        n_annees = an_fin - an_deb
        tcac_reel = (val_fin / val_deb) ** (1.0 / n_annees) - 1.0
        tcac_pc = tcac_reel * 100

        # Chercher un TCAC annonce dans la meme phrase que la projection.
        # On borne au point qui suit le match projection, ou +300 chars.
        fin_phrase_re = re.search(r"[.!?](?:\s|$)", texte[m.end():])
        fin_phrase = m.end() + (fin_phrase_re.end() if fin_phrase_re else 300)
        contexte = texte[m.start(): fin_phrase]
        for m_tcac in _TCAC_ANNONCE_RE.finditer(contexte):
            tcac_annonce = _lire_nombre(m_tcac.group(1))
            ecart = abs(tcac_annonce - tcac_pc)
            # On tolere 1 point de pourcentage absolu (arrondi/formulation).
            if ecart > 1.0:
                problemes.append(
                    f"TCAC annonce {tcac_annonce:.1f} % incoherent avec "
                    f"projection {val_deb:.1f} en {an_deb} vers {val_fin:.1f} "
                    f"en {an_fin} (recalcule : {tcac_pc:.1f} %)."
                )
    return problemes


def verifier_ratio(texte: str) -> list[str]:
    """Verifie X = pourcentage * Y quand la phrase l'affirme."""
    problemes: list[str] = []
    for m in _RATIO_RE.finditer(texte):
        val_partie = _en_millions(_lire_nombre(m.group(1)), m.group(2))
        pourcentage = _lire_nombre(m.group(3)) / 100.0
        val_total = _en_millions(_lire_nombre(m.group(4)), m.group(5))
        attendu = val_total * pourcentage
        if attendu <= 0:
            continue
        ecart_relatif = abs(val_partie - attendu) / attendu
        # Tolerance 5 % : l'analyste peut mentionner « environ », mais un
        # ecart d'un facteur 3-4 (cas 2,1 Md€ vs 576 M€ attendu) doit lever.
        if ecart_relatif > 0.05:
            unite = m.group(2)
            problemes.append(
                f"Ratio annonce incoherent : {m.group(1)} {unite} presente comme "
                f"{m.group(3)} % de {m.group(4)} {m.group(5)}, mais le calcul "
                f"donne {attendu:.0f} millions (ecart {ecart_relatif * 100:.0f} %)."
            )
    return problemes


def verifier_tcac_coherent_par_niveau(
    corpus_par_chapitre: dict[int, str]
) -> list[str]:
    """Un meme niveau geographique doit garder le meme TCAC dans TOUT le doc.

    Defaut mesure sur WAOME v1 : « TCAC 20 % » chapitre 1 puis « TCAC 31 % »
    chapitre 8 pour le meme perimetre mondial. Aucun check textuel intra-
    phrase ne pouvait le voir. Ici on regroupe par (niveau, valeur) sur
    l'ensemble du corpus et on signale toute divergence > 1 point.

    Une fois la base consolidee injectee (voir `contexte_supplementaire`),
    ce defaut devrait disparaitre par construction — mais le check reste
    utile en filet de securite pour les cas ou la base est vide (chapitres
    1-2 n'ont pas verrouille).
    """
    from collections import defaultdict
    tcac_par_niveau: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for chapitre, texte in corpus_par_chapitre.items():
        for m in _TCAC_AVEC_NIVEAU_RE.finditer(texte):
            niveau = _QUALIFIANT_VERS_NIVEAU.get(
                m.group(1).lower(), None
            )
            if niveau is None:
                continue
            valeur = _lire_nombre(m.group(2))
            if valeur <= 0:
                continue
            tcac_par_niveau[niveau].append((chapitre, valeur))

    problemes: list[str] = []
    for niveau, mentions in tcac_par_niveau.items():
        valeurs = sorted({round(v, 1) for _, v in mentions})
        if len(valeurs) < 2:
            continue
        # Une divergence significative si l'ecart max depasse la tolerance.
        if max(valeurs) - min(valeurs) > _ECART_TCAC_TOLERE:
            lieux = ", ".join(
                f"{v:.1f} % au ch. {ch}"
                for ch, v in sorted(mentions, key=lambda x: x[0])
            )
            problemes.append(
                f"TCAC {niveau} incoherent d'un chapitre a l'autre : {lieux}. "
                f"Un seul TCAC par niveau geographique dans tout le document."
            )
    return problemes


def _lire_nombre(raw: str) -> float:
    """« 1 250,50 » -> 1250.5. Espaces horizontaux, virgule decimale."""
    nettoye = re.sub(r"[\s\xa0]+", "", raw).replace(",", ".")
    try:
        return float(nettoye)
    except ValueError:
        return 0.0


# ══════════════════════════════════════════════════════════════════════════
# 3. STRATEGY
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EMStrategy:
    """Strategy pour l'etude de marche."""

    deliverable_type: ClassVar[str] = DeliverableType.MARKET_STUDY

    def contexte_supplementaire(
        self, job: GenerationJob, chapter: ChapterGeneration
    ) -> ContexteSupplementaire | None:
        """Injecte la base chiffree consolidee dans les chapitres 3+."""
        if chapter.chapter_number not in _CHAPITRES_CIBLES:
            return None
        corps = base_consolidee_markdown(job)
        if not corps:
            return None
        return ContexteSupplementaire(
            intitule="Base chiffree consolidee",
            corps=corps,
            chapitres_cibles=_CHAPITRES_CIBLES,
        )

    def problemes_de_coherence(
        self, job: GenerationJob, corpus_par_chapitre: dict[int, str]
    ) -> list[ProblemeCoherence]:
        """Checks specifiques EM :
        - arithmetiques intra-phrase (TCAC recalcule, ratio X = P % de Y),
        - coherence inter-chapitres (TCAC identique par niveau).
        """
        problemes: list[ProblemeCoherence] = []
        for numero, corps in corpus_par_chapitre.items():
            for detail in verifier_tcac_projection(corps):
                problemes.append(ProblemeCoherence(
                    categorie="arithmetique",
                    chapitre=numero,
                    detail=detail,
                ))
            for detail in verifier_ratio(corps):
                problemes.append(ProblemeCoherence(
                    categorie="arithmetique",
                    chapitre=numero,
                    detail=detail,
                ))
        # Check inter-chapitres : un seul TCAC par niveau geographique.
        for detail in verifier_tcac_coherent_par_niveau(corpus_par_chapitre):
            m = re.search(r"ch\.\s*(\d+)", detail)
            chapitre_ref = int(m.group(1)) if m else 0
            problemes.append(ProblemeCoherence(
                categorie="tcac_inter_chapitres",
                chapitre=chapitre_ref,
                detail=detail,
            ))
        # NB : pas de plafond sur le NOMBRE de TCAC distincts. Le manuel EM
        # (juillet 2026) n'impose aucun cardinal — une etude cite legitimement
        # plusieurs taux (mondial, national, par segment au ch. 3, parmi les
        # 12 chiffres cles du ch. 9...). Seule la COHERENCE d'un meme niveau
        # geographique est controlee (verifier_tcac_coherent_par_niveau), ce
        # qui correspond a la regle de cohorence p.4 (« un chiffre valide ne
        # change pas de valeur »). Un ancien check « max 3 TCAC » a ete retire :
        # il bloquait des etudes conformes au manuel.
        return problemes


def get_strategy() -> EMStrategy:
    """Point d'entree utilise par `strategies.base.get_strategy`."""
    return EMStrategy()
