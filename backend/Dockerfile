FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Dépendances système WeasyPrint (Phase 4b — D8 : PDF brandé) ──────────────
# WeasyPrint >= 60 utilise pydyf comme backend PDF : Pango/Cairo ne sont plus
# nécessaires. Il suffit d'avoir fontconfig + des polices système pour que
# les textes soient rendus correctement.
# fonts-liberation : Times, Arial, Courier (équivalents Liberations, suffisant pour le français)
# fonts-dejavu-core : fallback Unicode compact
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fontconfig \
        fonts-liberation \
        fonts-dejavu-core \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml manage.py /app/
COPY backend /app/backend

# [dev]  : outils de qualité (pytest, mypy, ruff)
# [pdf]  : WeasyPrint (génération PDF brandé)
# [ai]   : Anthropic SDK (génération texte Claude)
RUN pip install --no-cache-dir -e ".[dev,pdf,ai]"

EXPOSE 8000
