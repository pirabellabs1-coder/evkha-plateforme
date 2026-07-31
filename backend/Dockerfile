FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Dépendances système WeasyPrint (Phase 4b — D8 : PDF brandé) ──────────────
# WeasyPrint 62 utilise pydyf comme backend PDF mais conserve Pango pour le
# rendu de texte. libglib2.0-0 fournit libgobject-2.0-0 requis par GObject
# introspection. libpangocairo-1.0-0 est nécessaire pour les fontes FreeType.
# fonts-liberation : Times, Arial, Courier (équivalents Linux)
# fonts-dejavu-core : fallback Unicode compact
# fonts-crosextra-carlito : clone libre métriquement compatible de Calibri —
# la police EXIGÉE par le Bloc 6 des Consignes EVKHA. Sans lui, WeasyPrint
# retombait sur Liberation Sans et la charte typographique n'était pas tenue.
# ── LibreOffice : conversion Word vers PDF (lot 3) ───────────────────────────
# `libreoffice-writer` et NON `libreoffice` : le paquet complet embarque le
# tableur, la présentation et la base, soit environ un gigaoctet pour une
# fonction qu'on n'utilise pas. Writer seul suffit à `--convert-to pdf`.
#
# Pas de `default-jre` non plus : Java n'est requis que pour Base et les
# macros. La conversion d'un `.docx` en PDF s'en passe, et l'ajouter coûterait
# 150 Mo de plus.
#
# ATTENTION AUX POLICES. Le livrable emploie Aptos et Georgia, deux polices
# Microsoft absentes de Debian et non redistribuables. LibreOffice leur
# substituera automatiquement autre chose, et le PDF différera visiblement du
# Word — interlignes, chasses, coupures de ligne. Trois issues, à trancher :
#   1. déposer les fichiers de police dans l'image (licence à vérifier) ;
#   2. installer `ttf-mscorefonts-installer` pour Georgia (accepte la licence
#      Microsoft de manière non interactive, mais l'ajoute au conteneur) ;
#   3. changer les polices du gabarit pour des polices libres, ce qui garantit
#      un rendu identique partout — au prix d'un écart avec le modèle de
#      référence de la cliente.
# Tant que rien n'est fait, le PDF est fidèle au contenu mais pas à la
# typographie. Ne pas le dire reviendrait à livrer un écart invisible.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fontconfig \
        fonts-liberation \
        fonts-dejavu-core \
        fonts-crosextra-carlito \
        libglib2.0-0 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libpangocairo-1.0-0 \
        libharfbuzz0b \
        libcairo2 \
        libreoffice-writer \
        libreoffice-core \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

# LibreOffice écrit un profil utilisateur au premier lancement. Sans `HOME`
# accessible en écriture, la conversion échoue avec un message qui ne dit pas
# pourquoi — le conteneur tourne souvent sans répertoire personnel.
ENV HOME=/tmp

COPY pyproject.toml manage.py /app/
COPY backend /app/backend

# Ressources situées à la RACINE du dépôt et résolues à l'exécution par des
# chemins `parents[3]`. Elles ne sont pas du code, mais sans elles le moteur
# s'arrête net :
#
#   prompts/  — les consignes de rédaction, une par chapitre et par livrable
#               (`chapitres/configuration.py` : RACINE_PROMPTS) ;
#   gabarits/ — le modèle Word dont le rendu hérite styles, palette et marges
#               (`rendu_word/gabarit.py` : CHEMIN_GABARITS).
#
# Elles manquaient. La première génération par le nouveau moteur a échoué sur
# « Prompt introuvable : /app/prompts/etude_marche/chapitre_00.md », et le
# rendu Word aurait buté ensuite sur le gabarit absent. Aucun test ne pouvait
# le voir : en local, les fichiers sont là.
#
# `test_image_dependances.py` vérifie désormais que ces répertoires sont copiés.
COPY prompts /app/prompts
COPY gabarits /app/gabarits
# `references/` porte le MODÈLE de l'étude de marché, lu à l'exécution par
# `generation/modele/chargement.py`. Sans lui, aucun chapitre ne peut être
# comparé — et un contrôle qui n'a rien à comparer est un échec, pas un succès.
COPY references /app/references

# [dev]    : outils de qualité (pytest, mypy, ruff)
# [pdf]    : WeasyPrint (génération PDF brandé)
# [ai]     : Anthropic SDK (génération texte Claude)
# [word]   : python-docx et matplotlib — le livrable Word et ses graphiques
# [search] : ancrage web anti-hallucination (§6)
#
# `word` MANQUAIT. La chaîne de rendu Word du lot 3 était donc installée sans
# python-docx ni matplotlib : le premier document produit sur le serveur a
# échoué sur « No module named 'matplotlib' », et l'incident était le seul
# endroit où ça se voyait.
#
# Toute liste d'extras déclarée dans `pyproject.toml`, hors `dev`, doit figurer
# ici — c'est ce que vérifie `backend/tests/test_image_dependances.py`, pour que
# le prochain extra ajouté ne soit pas oublié à son tour.
RUN pip install --no-cache-dir -e ".[dev,pdf,ai,word,search]"

EXPOSE 8000
