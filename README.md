# MaintiDoc

Assistant documentaire multimodal pour des techniciens de maintenance fictifs. Il répond en français à partir d’un corpus synthétique (pompes et compresseurs), de photographies de démonstration et, si besoin, d’un service de maintenance exposé en MCP. La création d’un ticket n’a lieu qu’après une approbation humaine du texte exact.

MaintiDoc ne pilote aucun équipement, ne garantit pas un diagnostic et ne remplace ni une procédure de sécurité ni un technicien habilité.

## Périmètre

| Élément | Choix |
| --- | --- |
| Utilisateurs | Comptes fictifs (techniciens et responsables). |
| Corpus | Documents synthétiques, deux familles : pompes et compresseurs. |
| Entrées | Question en français, photographie, identifiant d’équipement optionnel. |
| Sorties | Réponse sourcée, clarification, ou brouillon de ticket. |
| Action sensible | Création d’un ticket après approbation explicite. |
| Hors périmètre | Pilotage de machines, diagnostic garanti, intervention autonome. |

Les objectifs chiffrés du cahier (citations, latence) sont des cibles, pas des résultats acquis. Le détail d’architecture, des flux et des risques est dans `docs/architecture.md` et `docs/risques.md`. Les usages autorisés sont dans `docs/fiche_limites.md`.

## Secrets

Copier `.env.example` vers `.env`. Ne jamais versionner `.env`. Aucun secret de production n’est codé en dur : le secret d’application est lu à l’exécution.

## Mode local

Sans GPU, le prototype répond à partir des extraits récupérés (générateur déterministe). Les poids Qwen2.5-VL et BGE-M3 ne sont pas téléchargés par défaut (`USE_VLM=0`, `USE_HEAVY_MODELS=0`).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
python scripts/ingest.py
python -m pytest
python scripts/api_server.py
```

Dans un second terminal :

```powershell
python scripts/ui.py
```

L'interface est sur http://localhost:8501 et l'API sur http://localhost:8000. Comptes fictifs : `alice` / `alice-demo` (pompes), `bob` / `bob-demo` (accès refusé), `carol` / `carol-demo` (compresseurs), `diana` / `diana-demo` (les deux familles).

Le serveur d'outils seul : `python scripts/mcp_server.py` (port 8001). La comparaison des rerankers : `python scripts/evaluate.py`. Le rapport synthétique est `eval/report.json`.

## Docker Compose

`docker compose up --build` démarre l'API, l'interface, Qdrant, PostgreSQL, MinIO, le serveur MCP et MLflow. Les mots de passe de ce fichier sont des secrets de démonstration. L'interface reste sur le port 8501. En local, sans ces services, `STORAGE_BACKEND=local` suffit.

