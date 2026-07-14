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
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml manage.py /app/
COPY backend /app/backend

# [dev]  : outils de qualité (pytest, mypy, ruff)
# [pdf]  : WeasyPrint (génération PDF brandé)
# [ai]   : Anthropic SDK (génération texte Claude)
RUN pip install --no-cache-dir -e ".[dev,pdf,ai]"

EXPOSE 8000
