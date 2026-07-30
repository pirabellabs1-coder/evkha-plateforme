# Environnement de développement local

Procédure vérifiée le 29 juillet 2026 sur Windows 11, sans Docker.
Aucun appel externe : tous les adaptateurs sont en mode bouchon déterministe.

## Prérequis

| Outil | Version utilisée | Remarque |
|---|---|---|
| Python | 3.13.5 | 3.12 minimum. Éviter 3.14 : roues manquantes pour certaines dépendances. |
| Node.js | 24.18 | Pour le tableau de bord React. |
| Docker | absent | Non nécessaire : SQLite remplace PostgreSQL, Celery tourne en mode synchrone. |

## Installation

```bash
py -3.13 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[ai,search,pdf,dev]"
```

Copier `.env.example` vers `.env`, puis appliquer les réglages locaux :

- **ne pas définir `DATABASE_URL`** : `settings.py` retombe alors sur SQLite (`db.sqlite3` à la racine) ;
- `CELERY_TASK_ALWAYS_EAGER=true` : les tâches s'exécutent dans le processus, ni worker ni Redis ;
- tous les `EVKHA_USE_STUB_*` à `true` ;
- `EVKHA_DASHBOARD_AUTH_DISABLED=true`.

`.env` est couvert par `.gitignore` et ne doit jamais être committé.

## Initialisation

```bash
./.venv/Scripts/python.exe manage.py migrate
./.venv/Scripts/python.exe manage.py seed_offers
./.venv/Scripts/python.exe manage.py collectstatic --noinput
```

Compte d'administration local :

```bash
DJANGO_SUPERUSER_PASSWORD=evkha-local ./.venv/Scripts/python.exe manage.py createsuperuser --noinput --username admin --email admin@evkha.local
```

## Démarrage

Deux processus, dans deux terminaux :

```bash
./.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

```bash
cd frontend && npm install && npm run dev
```

| Service | URL |
|---|---|
| Tableau de bord | http://localhost:5173 |
| API du tableau de bord | http://localhost:8000/api/dashboard/ |
| Administration Django | http://localhost:8000/admin/ |
| Sonde de santé | http://localhost:8000/healthz/ |

Le tableau de bord demande un jeton au premier accès. L'authentification étant
désactivée en local, **n'importe quelle valeur non vide convient** : elle est
seulement stockée dans le `localStorage` du navigateur (`frontend/src/auth.ts`).

## Contrôles de référence

À rejouer avant et après toute modification :

```bash
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m mypy backend
./.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
```

### État mesuré au commit `dc8d64d`

| Contrôle | Résultat |
|---|---|
| `pytest` | **vert**, code de sortie 0 |
| `makemigrations --check` | **vert**, aucune migration manquante |
| `ruff check .` | **42 erreurs** |
| `mypy backend` | **102 erreurs sur 16 fichiers** |

`CLAUDE.md` exige que les quatre contrôles soient verts avant tout commit.
Deux ne le sont pas sur `main`. Ces erreurs **préexistent** à la mission : elles
constituent la ligne de référence et ne doivent pas être confondues avec des
régressions introduites par la refonte. Les corriger est une décision à part.

Concentration des erreurs `ruff` : `prompt_library.py` (9), `correction.py` (9),
`backend/scripts/` (6), le reste dispersé dans les tests.

## Limite connue : pas de PDF réel sous Windows

WeasyPrint s'installe mais ne s'importe pas :

```
cannot load library 'gobject-2.0-0'
```

Il lui faut les bibliothèques système GTK (Pango, Cairo), absentes de Windows.
Sans conséquence en développement : `EVKHA_USE_STUB_PDF=true` fait produire au
client bouchon des artefacts déterministes, sans écriture disque.

Trois options pour obtenir un vrai PDF en local :

1. installer le paquet d'exécution GTK pour Windows ;
2. travailler sous WSL, où `apt install libpango-1.0-0 libpangoft2-1.0-0` suffit ;
3. ne rien faire — le lot 3 remplace de toute façon cette chaîne par
   Word puis conversion, ce qui appellera une autre dépendance système
   (LibreOffice en mode sans interface).

## Génération de bout en bout sans coût

Le pipeline complet se rejoue hors ligne avec `StubClaudeClient`. Mesure du
29 juillet 2026 sur une étude de marché :

| Indicateur | Valeur |
|---|---|
| Chapitres générés | 22 sur 22 |
| Statut du job | `done` |
| Barrière de livraison | franchie, 0 échec |
| Document rendu | 22 sections |
| Artefacts | HTML + PDF bouchons |

Le contenu produit vient du bouchon : sa longueur n'a **aucune valeur
d'indication** sur celle d'un livrable réel. Ce test vérifie la mécanique du
pipeline, pas la qualité éditoriale.

Le test `backend/tests/test_smoke_em_pipeline_complet.py` couvre le même chemin
et s'exécute avec la suite.
