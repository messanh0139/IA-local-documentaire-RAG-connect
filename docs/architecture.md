# Architecture RAG Deep Bleue IA

## 1. Vue d'ensemble

DocMind est organisé en quatre plans:

- Connecteurs: SharePoint, OneDrive, Google Drive, NAS ou stockage local.
- Indexation: extraction texte, chunking, embeddings, stockage chunks/metadonnees.
- Recherche securisee: retrieval vectoriel filtre par tenant et permissions.
- API SaaS: FastAPI, PostgreSQL, Qdrant, workers, frontend Next.js.

Les documents originaux ne sont jamais copies comme fichiers dans le RAG. Le systeme garde seulement:

- identifiants source,
- texte des chunks,
- embeddings,
- metadonnees de citation,
- ACL utilisateurs/groupes,
- etat de synchronisation.

## 2. Backend

```text
backend/
  app/
    api/v1/           Routes FastAPI
    core/             Configuration, securite, logging
    db/               Session SQLAlchemy et init DB
    models/           Tables PostgreSQL
    schemas/          DTO Pydantic
    services/         Logique metier RAG
    workers/          Taches RQ
```

## 3. Frontend cible

```text
frontend/
  app/
    login/
    search/
    admin/connectors/
    admin/audit/
  components/
    chat/
    citations/
    connector-status/
  lib/
    api-client.ts
    auth.ts
```

## 4. Modele PostgreSQL

Tables principales:

- tenants: isolation SaaS.
- users, groups, user_groups: identite et groupes synchronises depuis Entra ID ou Google.
- connectors: configuration non secrete des sources documentaires.
- documents: fichier source, checksum, version, chemin, url, statut.
- document_acls: permissions lecture par utilisateur ou groupe.
- chunks: mapping PostgreSQL vers points Qdrant.
- sync_runs: suivi des synchronisations.
- audit_logs: audit securite et recherche.

## 5. Collection Qdrant

Collection: `docmind_chunks`

Vecteur:

- taille: `EMBEDDING_DIMENSIONS`, 1536 par defaut avec `text-embedding-3-small`.
- distance: cosine.

Payload:

```json
{
  "tenant_id": "deep-bleue-ia",
  "document_id": "...",
  "chunk_id": "...",
  "connector_id": "...",
  "path": "/Finance/Budget.pdf",
  "source_url": "https://...",
  "page": 4,
  "title": "Budget.pdf",
  "chunk_text": "...",
  "allowed_user_ids": ["alice"],
  "allowed_group_ids": ["finance"],
  "is_public": false,
  "checksum": "sha256..."
}
```

## 6. Pipeline d'ingestion

1. Le connecteur liste les fichiers et retourne external_id, chemin, url, dates, checksum/version.
2. Le synchroniseur compare avec PostgreSQL.
3. Les fichiers ajoutes ou modifies sont telecharges en flux temporaire.
4. Le texte est extrait page par page quand possible.
5. Le texte est decoupe en chunks avec overlap.
6. Les embeddings sont calcules.
7. Les anciens points du document sont supprimes de Qdrant.
8. Les nouveaux chunks sont upsert dans Qdrant et references en PostgreSQL.
9. Les fichiers absents sont marques supprimes et retires de Qdrant.

## 7. Synchronisation

MVP:

- sync foreground via API.
- support RQ pour basculer vers worker.

SaaS:

- delta tokens Microsoft Graph et Google Drive Changes API.
- webhooks quand disponibles.
- fallback scan planifie.
- verrou par connecteur pour eviter les sync concurrentes.

## 8. Permissions

Regle stricte: un chunk n'est eligible que si l'utilisateur courant appartient au tenant et satisfait au moins une ACL:

- fichier public interne,
- utilisateur explicitement autorise,
- groupe autorise.

La verification se fait a deux endroits:

- filtre Qdrant sur tenant et ACL payload,
- garde applicative avant construction du contexte LLM.

## 9. Retrieval

1. Authentifier l'utilisateur.
2. Embedder la question.
3. Chercher top_k dans Qdrant avec filtre tenant + ACL.
4. Revalider les permissions cote API.
5. Construire un contexte cite `[S1]`, `[S2]`.
6. Appeler le LLM avec un prompt qui interdit les reponses sans source.
7. Retourner answer + citations structurees.

## 10. Prompt systeme RAG

Le prompt est dans `backend/app/services/rag/prompts.py`.
Il impose:

- repondre uniquement avec les sources fournies,
- refuser poliment si le contexte est insuffisant,
- citer chaque affirmation documentaire,
- ne jamais reveler de document hors contexte.

## 11. Endpoints MVP

- `GET /health`
- `GET /api/v1/auth/me`
- `POST /api/v1/connectors`
- `GET /api/v1/connectors`
- `POST /api/v1/connectors/{id}/sync`
- `GET /api/v1/documents`
- `POST /api/v1/search`
- `POST /api/v1/chat`

## 12. Plan MVP

1. Socle FastAPI, PostgreSQL, Qdrant, Redis.
2. Auth dev par headers, puis Entra ID.
3. Connecteur local pour valider ingestion/retrieval.
4. Connecteur SharePoint avec Microsoft Graph delta.
5. ACL documentaires synchronisees.
6. Interface Next.js recherche + citations.
7. Observabilite, audit, quotas.
8. Deploiement SaaS multi-tenant.

## 13. Securite

- Ne jamais envoyer au LLM des chunks non autorises.
- Ne pas stocker les secrets connecteurs en clair.
- Chiffrer les tokens OAuth.
- Journaliser les recherches et documents cites.
- Isoler chaque tenant dans PostgreSQL et Qdrant payload.
- Appliquer rate limits et quotas.
- Ajouter tests de non-regression sur les ACL.

## 14. Erreurs a eviter

- Se fier uniquement au frontend pour les permissions.
- Indexer des documents sans ACL.
- Stocker le fichier complet dans le RAG.
- Oublier la suppression des points Qdrant quand un fichier est supprime.
- Melanger les tenants dans une meme recherche.
- Afficher une reponse sans citation.
- Utiliser un prompt qui autorise le modele a inventer les sources.

## 15. Roadmap SaaS

- Multi-tenant complet avec plan, quotas et facturation.
- Connecteurs SharePoint, Google Drive, OneDrive, NAS.
- Admin UI connecteurs et audit.
- Encryption KMS pour secrets.
- Worker pool scalable.
- Evaluation automatique qualite RAG.
- RBAC admin.
- SSO Entra ID et Google Workspace.
- Export audit et conformite.
