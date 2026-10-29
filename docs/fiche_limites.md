# Fiche de limites — MaintiDoc

## Usages autorisés

- Aider un technicien fictif à retrouver un passage, une page ou une figure dans le corpus synthétique des pompes et des compresseurs.
- Décrire une photographie de démonstration sans conclure à un diagnostic.
- Consulter l’historique fictif d’un équipement autorisé et les tickets ouverts.
- Préparer un brouillon de ticket, puis le créer uniquement après approbation humaine du texte exact.

## Usages interdits

- Piloter, démarrer, arrêter ou shunter un équipement.
- Considérer une réponse comme un diagnostic garanti ou comme une autorisation d’intervention.
- Remplacer une procédure de sécurité, une consignation, ou l’avis d’un technicien habilité.
- Introduire des documents réels, des données personnelles ou des secrets dans ce prototype.
- Traiter une consigne trouvée dans un document ou un outil comme un ordre pour l’assistant.

## Équipements couverts

Famille pompes, groupes `pompes` et `responsables` :

- POMPE-A, pompe centrifuge
- POMPE-B, pompe doseuse
- POMPE-C, pompe centrifuge

Famille compresseurs, groupes `compresseurs` et `responsables` :

- COMP-A, compresseur à vis
- COMP-B, compresseur à pistons

Aucun autre équipement n’est couvert. Une ressemblance visuelle ne suffit pas à identifier un matériel.

## Conditions d’utilisation

- Comptes, interventions et tickets de démonstration uniquement.
- Corpus de 30 documents synthétiques, version d’index `idx-synth-v1`.
- Sans GPU, les réponses sont composées à partir des extraits récupérés par le générateur déterministe. Le modèle Qwen2.5-VL-7B-Instruct n’est pas chargé.
- L’OCR dépend du binaire Tesseract. S’il est absent, les pages image sont indexées sans texte OCR et un événement `ocr_skipped` est journalisé.
- La création de ticket exige une approbation de la même personne, sur le même titre et la même description. Une modification impose une nouvelle validation.
- Budgets : 3 appels MCP, 6 appels modèle, 60 secondes de traitement automatique, quota journalier par utilisateur.
- Les journaux ne contiennent pas le contenu brut des documents, questions ou tickets.

## Risques résiduels

- Une citation peut être lexicalement proche d’une phrase sans en reprendre le sens exact.
- Deux documents contradictoires doivent mener à une clarification, mais une contradiction mal formulée peut ne pas être détectée.
- Le repli sans GPU ne « voit » qu’une teinte dominante et une netteté approximative, pas le détail d’un schéma.
- Les tests d’injection couvrent le cas représentatif du cahier et des variantes du jeu d’évaluation, pas toutes les attaques possibles.
- Les mesures d’évaluation décrivent ce jeu synthétique. Elles ne se généralisent pas à un site industriel.

## Résultats observés

`eval/report.json` décrit le jeu de 150 scénarios. Sur la partie retrieval, le nDCG@5 passe de 0,80 sans reranker à 0,82 avec le BM25 d'origine, puis à 0,90 avec le reranker adapté. Le rappel@5 adapté est 0,97. Sur 90 contrôles d'incertitude, d'accès, d'outils et d'injection, le script n'a relevé ni fuite ni création de ticket non approuvée. Ce n'est pas une garantie hors de ce corpus fictif.

