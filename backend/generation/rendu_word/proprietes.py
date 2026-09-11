"""Les propriétés du fichier Word livré : ce que l'aperçu en dit avant de l'ouvrir.

## Le défaut, mesuré sur un livrable réel

Stratégie du dossier `f7f2fad9`, livrée le 08/09/2026 : 112 pages en PDF,
210 000 signes. Ses propriétés déclaraient pourtant `Pages = 1`, `Words = 0`,
`Characters = 0`, une création le **23 décembre 2013**, et embarquaient une
miniature… de page blanche.

Ce sont les propriétés du gabarit Word d'origine, recopiées telles quelles dans
chaque livrable. Word les recalcule à l'ouverture, donc personne ne les voit
dans Word. Mais tout ce qui montre un fichier SANS l'ouvrir les lit : l'aperçu
du Finder, Coup d'œil, le volet de lecture de Mail ou d'Outlook, SharePoint. Le
client voyait une page blanche marquée « 1 page », et concluait que le document
était tronqué alors qu'il était complet. La cliente l'a signalé comme un bug —
c'en était un, et il se voyait avant même d'ouvrir le fichier.

## Ce que ce module corrige

- la **miniature** est retirée : une miniature fausse est pire que pas de
  miniature, puisque sans elle l'aperçu dessine la vraie première page ;
- les **statistiques** sont recalculées depuis le texte du document ;
- le **nombre de pages** vient du PDF produit à partir de ce même Word — la
  seule mesure réelle de la pagination. Tant qu'il n'est pas connu, la balise
  est RETIRÉE plutôt que laissée à 1 : une absence ne ment pas ;
- les **dates** sont celles de la génération.

## Ce qu'il ne touche JAMAIS

Le contenu. Seules les parties `docProps/` et la relation vers la miniature
sont réécrites ; toute autre partie du paquet est recopiée octet pour octet, et
`corriger` le VÉRIFIE avant de remplacer le fichier. C'est ce qui permet
d'appeler ce module après le contrôle du livrable sans rouvrir la règle 3 : ce
qui refait le document après le contrôle doit être contrôlé à son tour — ici,
la preuve que rien du document n'a bougé fait partie de l'opération.
"""
from __future__ import annotations

import re
import zipfile
from datetime import datetime
from html import unescape
from pathlib import Path

#: La partie qui porte la miniature, et le type de relation qui la désigne.
MINIATURE = "docProps/thumbnail.jpeg"
REL_MINIATURE = (
    "http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"
)

#: Les seules parties que ce module a le droit de réécrire.
PARTIES_REECRITES = frozenset({
    "docProps/app.xml",
    "docProps/core.xml",
    "_rels/.rels",
    "[Content_Types].xml",
})


class ProprietesIncorrigibles(RuntimeError):
    """La réécriture aurait touché autre chose que les propriétés.

    Levée plutôt qu'avalée : l'appelant garde alors le fichier d'origine, avec
    ses métadonnées fausses mais son contenu intact. Une métadonnée fausse est
    un défaut ; un contenu altéré après contrôle serait une faute.
    """


def _texte(document_xml: str) -> tuple[list[str], int]:
    """Le texte de chaque paragraphe non vide, et leur nombre."""
    paragraphes: list[str] = []
    for bloc in re.findall(r"<w:p[ >].*?</w:p>", document_xml, flags=re.S):
        morceaux = re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", bloc, flags=re.S)
        texte = unescape("".join(morceaux))
        if texte.strip():
            paragraphes.append(texte)
    return paragraphes, len(paragraphes)


def _statistiques(document_xml: str) -> dict[str, int]:
    """Mots, signes et paragraphes, comptés comme Word les compte à peu près.

    Word affine ces nombres à l'ouverture — ses règles sur la ponctuation et
    les traits d'union diffèrent de quelques pour cent. Ce qu'on corrige ici
    n'est pas cet écart, c'est le zéro : un aperçu qui annonce « 0 mot » pour
    trente-cinq mille mots ment sur l'essentiel.
    """
    paragraphes, nombre = _texte(document_xml)
    tout = "\n".join(paragraphes)
    return {
        "Words": len(tout.split()),
        "Characters": len(re.sub(r"\s", "", tout)),
        "CharactersWithSpaces": len(tout.replace("\n", " ")),
        "Paragraphs": nombre,
    }


def _poser(xml: str, balise: str, valeur: str | None) -> str:
    """Remplace, ajoute ou retire `<balise>…</balise>` dans `<Properties>`."""
    motif = re.compile(rf"<{balise}>.*?</{balise}>|<{balise}\s*/>", flags=re.S)
    if valeur is None:
        return motif.sub("", xml)
    nouveau = f"<{balise}>{valeur}</{balise}>"
    if motif.search(xml):
        return motif.sub(nouveau, xml, count=1)
    return xml.replace("</Properties>", f"{nouveau}</Properties>", 1)


def _app(app_xml: str, document_xml: str, pages: int | None) -> str:
    for balise, valeur in _statistiques(document_xml).items():
        app_xml = _poser(app_xml, balise, str(valeur))
    # `Lines` dépend de la mise en page, que seul un moteur de rendu connaît.
    # On la retire au lieu de l'estimer : une absence ne ment pas.
    app_xml = _poser(app_xml, "Lines", None)
    return _poser(app_xml, "Pages", str(pages) if pages else None)


def _core(core_xml: str, maintenant: datetime) -> str:
    horodatage = maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")
    for balise in ("dcterms:created", "dcterms:modified"):
        core_xml = re.sub(
            rf"(<{balise}[^>]*>).*?(</{balise}>)",
            rf"\g<1>{horodatage}\g<2>",
            core_xml,
            flags=re.S,
        )
    return core_xml


def _rels(rels_xml: str) -> str:
    """La relation vers la miniature, retirée — pas la miniature seule.

    Retirer le fichier en laissant la relation produit un paquet qui désigne
    une partie absente : Word le déclare alors endommagé et propose de le
    « réparer ». On aurait remplacé un aperçu trompeur par un message
    d'erreur à l'ouverture.
    """
    # Guillemets simples OU doubles : un paquet écrit par un autre outil peut
    # employer les uns ou les autres, et une relation oubliée ici désignerait
    # une miniature retirée.
    return re.sub(
        r"<Relationship\b[^>]*Type=([\"'])" + re.escape(REL_MINIATURE) + r"\1[^>]*/>",
        "",
        rels_xml,
    )


def _types(types_xml: str) -> str:
    """La déclaration de type propre à la miniature, si elle est nommée."""
    return re.sub(
        r"<Override\b[^>]*PartName=([\"'])/docProps/thumbnail\.jpeg\1[^>]*/>",
        "",
        types_xml,
    )


def corriger(chemin: Path, *, pages: int | None, maintenant: datetime) -> None:
    """Réécrit les propriétés du `.docx`, EN PLACE, sans toucher au contenu.

    Écrit dans un fichier voisin puis le substitue : un échec en cours de
    route laisse l'original intact au lieu d'un paquet à moitié écrit.

    Lève `ProprietesIncorrigibles` si une partie autre que les propriétés
    différerait après réécriture.
    """
    provisoire = chemin.with_name(chemin.name + ".proprietes")
    # Tout échec, quel qu'il soit, retire la copie provisoire. Elle contient le
    # document du client en entier ; laissée sur le disque, elle échapperait à
    # la purge de rétention, qui ne connaît que les clés d'artefacts.
    try:
        _ecrire(chemin, provisoire, pages=pages, maintenant=maintenant)
        _prouver(chemin, provisoire)
    except BaseException:
        provisoire.unlink(missing_ok=True)
        raise
    provisoire.replace(chemin)


def _ecrire(
    chemin: Path, provisoire: Path, *, pages: int | None, maintenant: datetime
) -> None:
    with zipfile.ZipFile(chemin) as source:
        document_xml = source.read("word/document.xml").decode("utf-8")
        with zipfile.ZipFile(provisoire, "w", zipfile.ZIP_DEFLATED) as cible:
            for info in source.infolist():
                nom = info.filename
                if nom == MINIATURE:
                    continue
                donnees = source.read(nom)
                if nom == "docProps/app.xml":
                    donnees = _app(donnees.decode("utf-8"), document_xml, pages).encode()
                elif nom == "docProps/core.xml":
                    donnees = _core(donnees.decode("utf-8"), maintenant).encode()
                elif nom == "_rels/.rels":
                    donnees = _rels(donnees.decode("utf-8")).encode()
                elif nom == "[Content_Types].xml":
                    donnees = _types(donnees.decode("utf-8")).encode()
                cible.writestr(info, donnees)


def _prouver(avant_chemin: Path, apres_chemin: Path) -> None:
    """Trois preuves, avant de remplacer quoi que ce soit.

    1. Le contenu n'a pas bougé : toute partie non réécrite est identique.
    2. Les parties réécrites sont du XML bien formé.
    3. Chaque relation interne du paquet désigne une partie qui existe — une
       relation orpheline fait déclarer le fichier « endommagé » par Word.

    Les deux dernières manquaient : la première version ne comparait que ce
    qu'elle n'avait pas touché, donc elle ne pouvait pas voir sa propre casse.
    """
    from xml.dom import minidom  # noqa: PLC0415

    with zipfile.ZipFile(avant_chemin) as avant, zipfile.ZipFile(apres_chemin) as apres:
        noms_apres = set(apres.namelist())
        for nom in avant.namelist():
            if nom in PARTIES_REECRITES or nom == MINIATURE:
                continue
            if avant.read(nom) != apres.read(nom):
                raise ProprietesIncorrigibles(f"la partie {nom} aurait changé")
        for nom in PARTIES_REECRITES & noms_apres:
            try:
                minidom.parseString(apres.read(nom))
            except Exception as erreur:  # noqa: BLE001 — converti, jamais avalé
                raise ProprietesIncorrigibles(f"{nom} mal formé : {erreur}") from erreur
        for nom in (n for n in noms_apres if n.endswith(".rels")):
            dossier = nom.replace("_rels/", "").removesuffix(".rels")
            base = dossier.rsplit("/", 1)[0] + "/" if "/" in dossier else ""
            for cible, mode in re.findall(
                r"Target=[\"']([^\"']+)[\"'](?:\s+TargetMode=[\"']([^\"']+)[\"'])?",
                apres.read(nom).decode("utf-8"),
            ):
                if mode == "External" or "://" in cible:
                    continue
                chemin = cible.lstrip("/") if cible.startswith("/") else base + cible
                parties: list[str] = []
                for segment in chemin.split("/"):
                    if segment == "..":
                        if parties:
                            parties.pop()
                    elif segment and segment != ".":
                        parties.append(segment)
                if "/".join(parties) not in noms_apres:
                    raise ProprietesIncorrigibles(
                        f"{nom} désigne une partie absente : {cible}"
                    )


def lire(chemin: Path) -> dict[str, str]:
    """Les propriétés telles qu'un aperçu les lirait. Pour les tests et le suivi."""
    with zipfile.ZipFile(chemin) as paquet:
        app = paquet.read("docProps/app.xml").decode("utf-8")
        core = paquet.read("docProps/core.xml").decode("utf-8")
        noms = set(paquet.namelist())
    lu: dict[str, str] = {"miniature": "oui" if MINIATURE in noms else "non"}
    for balise in ("Pages", "Words", "Characters", "Paragraphs"):
        trouve = re.search(rf"<{balise}>(.*?)</{balise}>", app)
        lu[balise] = trouve.group(1) if trouve else ""
    cree = re.search(r"<dcterms:created[^>]*>(.*?)</dcterms:created>", core)
    lu["cree_le"] = cree.group(1) if cree else ""
    return lu
