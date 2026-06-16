# DocMind - RAG documentaire sécurisé

DocMind est un starter backend pour construire le RAG documentaire de Deep Bleue IA.
Le principe central: les documents restent dans SharePoint, OneDrive, Google Drive, NAS ou disque local.
Le système indexe uniquement les chunks, embeddings et métadonnées de sécurité nécessaires à la recherche. Les fichiers complets restent dans leur source originale.

## Lancement le plus simple avec Docker

Oui: l'objectif est maintenant que Docker Compose lance toute la stack.

```powershell
docker compose up --build
```

Puis ouvre:

- Frontend: http://localhost:3000
- Backend API: http://127.0.0.1:8000/docs
- Qdrant: http://127.0.0.1:6333/dashboard

Garde le terminal Docker ouvert. Si tu l'arrêtes, le frontend et l'API ne répondent plus et le navigateur affiche `ERR_CONNECTION_REFUSED`.

Pour lancer en arrière-plan:

```powershell
docker compose up -d --build
```

Pour voir l'état:

```powershell
docker compose ps
```

Pour arrêter:

```powershell
docker compose down
```

Si Qdrant quitte avec une erreur de segment incompatible après un changement de version, supprime seulement l'index vectoriel et reconstruis-le par synchronisation:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\reset-qdrant.ps1
```

Cela ne supprime pas les documents sources. Cela supprime uniquement le volume Qdrant, donc les embeddings/chunks vectoriels seront recréés au prochain clic sur synchroniser.

## Démonstration rapide

Le compose monte automatiquement `sample_docs/` dans le conteneur backend sous:

```text
/data/local-docs
```

Dans l'interface, crée un connecteur local avec:

```text
Nom: Base documentaire locale
Racine locale: /data/local-docs
```

Puis clique sur synchroniser et pose une question.

Tu peux aussi lancer la démo automatiquement:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-local.ps1
```

Ce script crée un connecteur, synchronise les documents et pose une question RAG.

## Connecter un vrai dossier Windows

1. Copie le fichier d'exemple:

```powershell
Copy-Item docker-compose.local-folder.example.yml docker-compose.override.yml
```

2. Ouvre `docker-compose.override.yml` et remplace le chemin Windows:

```yaml
services:
  backend:
    volumes:
      - C:/Users/Admin/Documents/DeepBleueDemo:/data/local-docs:ro
```

3. Redémarre:

```powershell
docker compose up -d --build
```

4. Dans l'interface, utilise toujours:

```text
/data/local-docs
```

Le conteneur ne voit pas `C:\...` directement. Il voit le dossier monté sous `/data/local-docs`. Le montage est en lecture seule (`:ro`) pour éviter que DocMind modifie les documents sources.

## Démarrage local

```powershell
# L'environnement virtuel est déjà créé:
.\.venv\Scripts\activate

# Installer les dépendances
$env:UV_CACHE_DIR=".uv-cache"
uv pip install -e ".[dev]"

# Copier la configuration
Copy-Item .env.example .env

# Lancer PostgreSQL, Qdrant et Redis
docker compose up -d

# Initialiser les tables
$env:PYTHONPATH="backend"
python -m app.db.init_db

# Lancer l'API
uvicorn app.main:app --app-dir backend --reload
```

API locale: http://localhost:8000/docs

## Ce qui est inclus maintenant

- Backend FastAPI modulaire.
- PostgreSQL pour tenants, connecteurs, documents, ACL, chunks, synchronisations et audit.
- Qdrant pour la recherche vectorielle filtrée par tenant et permissions.
- Redis/RQ préparé pour les workers.
- Connecteur local fonctionnel pour valider tout le pipeline.
- Stubs SharePoint et Google Drive prêts à implémenter avec OAuth et delta sync.
- Healthchecks live/ready.
- Dashboard API.
- Frontend Next.js complet pour piloter le MVP.
- Prompt RAG strict avec citations obligatoires.
- Tests backend de base sur chunking, permissions et configuration de chemin Python.

Les versions Qdrant client et serveur doivent rester alignées. Le projet utilise `qdrant-client` installé côté Python et `qdrant/qdrant:v1.18.0` côté Docker.

## Démarrage recommandé

Le plus simple est d'utiliser le script de démarrage. Il vérifie Docker, lance PostgreSQL/Qdrant/Redis, attend PostgreSQL, initialise les tables, puis démarre FastAPI:

```powershell
.\.venv\Scripts\activate
.\scripts\start-dev.ps1
```

Si PowerShell bloque les scripts avec `l'exécution de scripts est désactivée sur ce système`, utilise cette commande:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

Garde ce terminal ouvert: FastAPI tourne dans ce processus. Si tu fermes le terminal ou interromps la commande avec `Ctrl+C`, le site `http://localhost:8000/docs` redevient inaccessible.

Si tu vois une erreur du type `failed to connect to the docker API at npipe...dockerDesktopLinuxEngine`, Docker Desktop n'est pas lancé. Ouvre Docker Desktop, attends que le moteur soit prêt, puis relance:

```powershell
.\scripts\start-dev.ps1
```

## Diagnostic rapide

Si le navigateur affiche `ERR_CONNECTION_REFUSED`, vérifie l'état local:

```powershell
.\scripts\check-dev.ps1
```

Ou, si PowerShell bloque les scripts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-dev.ps1
```

Si PostgreSQL, Qdrant et Redis sont `Up`, mais que le port `8000` est `KO`, cela veut dire que Docker fonctionne mais que FastAPI n'est pas lancé. Relance:

```powershell
.\scripts\start-dev.ps1
```

Puis ouvre: http://127.0.0.1:8000/docs

## Nettoyage du workspace

Pour retirer les caches Python, logs et artefacts locaux sans supprimer les dépendances frontend:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\clean.ps1
```

## Frontend Next.js

Ouvre un deuxième terminal à la racine du projet:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Frontend: http://localhost:3000

Le frontend appelle le backend via:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Tu peux modifier ces valeurs dans [frontend/.env.local.example](frontend/.env.local.example).

Si `npm` n'est pas reconnu, installe Node.js LTS, puis relance la commande.

## Flux de test complet

1. Place un fichier `.txt`, `.md`, `.pdf` ou `.docx` dans `sample_docs/`.
2. Lance Docker + FastAPI:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
```

3. Lance le frontend dans un deuxième terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

4. Va sur http://localhost:3000.
5. Crée ou sélectionne le connecteur local.
6. Clique sur synchroniser.
7. Pose une question dans la recherche RAG.

## Endpoints principaux

- `GET /health`
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `GET /api/v1/dashboard/stats`
- `GET /api/v1/auth/me`
- `POST /api/v1/connectors`
- `GET /api/v1/connectors`
- `GET /api/v1/connectors/{connector_id}`
- `GET /api/v1/connectors/{connector_id}/sync-runs`
- `POST /api/v1/connectors/{connector_id}/sync`
- `GET /api/v1/documents`
- `POST /api/v1/search`
- `POST /api/v1/chat`

## Authentification MVP

En développement, l'API accepte des en-têtes de test:

```text
X-Tenant-Id: deep-bleue-ia
X-User-Id: alice
X-User-Email: alice@deepbleue.ai
X-User-Groups: direction,finance
```

Ce mode doit rester désactivé en production.

## Premier test d'ingestion

1. Ajouter des fichiers `.txt`, `.md`, `.pdf` ou `.docx` dans `sample_docs/`.
2. Créer un connecteur local:

```http
POST /api/v1/connectors
{
  "name": "Dossier local MVP",
  "type": "local",
  "config": { "root_path": "./sample_docs" }
}
```

3. Lancer une synchronisation:

```http
POST /api/v1/connectors/{connector_id}/sync
{ "mode": "foreground" }
```

4. Poser une question:

```http
POST /api/v1/chat
{ "question": "Quels documents parlent de sécurité ?", "top_k": 5 }
```


## Corrections robustesse ajoutées

- Le projet n'inclut plus les caches, logs, environnement virtuel ni fichiers `.env` dans l'archive propre.
- Les tests fonctionnent directement avec `python -m pytest` grâce à `tests/conftest.py`.
- Le connecteur local limite l'accès au dossier autorisé `LOCAL_CONNECTOR_ROOT` pour éviter les chemins arbitraires.
- L'extraction documentaire est plus robuste: TXT, MD, CSV, PDF et DOCX, y compris les tableaux DOCX.
- La synchronisation continue si un fichier individuel est corrompu ou inexploitable; l'erreur est stockée dans `sync_runs.stats.file_errors`.
- Les changements de permissions déclenchent maintenant une réindexation via `acl_hash`.
- Les appels OpenAI ont des retries et respectent `EMBEDDING_DIMENSIONS` pour les modèles `text-embedding-3`.
