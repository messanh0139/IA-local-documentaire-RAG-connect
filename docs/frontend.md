# Frontend DocMind

Le frontend est une application Next.js orientee console SaaS:

- etat systeme PostgreSQL, Qdrant, Redis;
- statistiques tenant;
- creation de connecteur local MVP;
- synchronisation foreground;
- liste des documents indexes;
- recherche conversationnelle RAG;
- panneau des citations.

## Variables

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_TENANT_ID=deep-bleue-ia
NEXT_PUBLIC_USER_ID=alice
NEXT_PUBLIC_USER_EMAIL=alice@deepbleue.ai
NEXT_PUBLIC_USER_GROUPS=everyone,finance,direction
```

Ces valeurs alimentent les en-tetes de developpement acceptes par le backend.
En production, elles devront etre remplacees par une vraie session OAuth.

## Commandes

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Le backend doit rester actif sur `127.0.0.1:8000`.
Le frontend tourne sur `localhost:3000`.
