# Securite documentaire Deep Bleue IA

Le systeme RAG DocMind doit respecter les permissions utilisateurs et groupes.
Une reponse ne doit jamais etre construite avec un document inaccessible a l'utilisateur courant.

Chaque reponse doit citer ses sources avec le nom du fichier, le chemin, la page quand elle existe et le lien source.
Les documents originaux restent dans leur emplacement d'origine. DocMind indexe uniquement les chunks, les embeddings et les metadonnees necessaires a la recherche.

Pour le MVP local, les fichiers places dans `sample_docs` sont visibles par le groupe `everyone`.
