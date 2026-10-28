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
