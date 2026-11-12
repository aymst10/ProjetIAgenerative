"""Prédire le pas suivant d'une sinusoïde, sur CPU, sans poids préentraînés.

Le cours « Architecture Transformer » compare trois mémoires sur le même
découpage : dix valeurs de sin(x) pour prédire la suivante. Ce module
couvre le RNN, le LSTM, un petit encodeur, puis deux modèles de texte
minuscules (décodeur causal et masque bidirectionnel). GPT-2 et BERT
ne sont pas téléchargés.
"""

from __future__ import annotations

import torch
import torch.nn as nn


def make_windows() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """190 fenêtres chronologiques, 150 pour apprendre et 40 pour tester."""
    periode = torch.linspace(0, 20, 200)
    serie = torch.sin(periode)
    longueur_sequence = 10
    entrees = torch.stack(
        [serie[i : i + longueur_sequence] for i in range(len(serie) - longueur_sequence)]
    )
    cibles = torch.stack(
        [serie[i + longueur_sequence] for i in range(len(serie) - longueur_sequence)]
    )
    entrees = entrees.unsqueeze(-1)
    cibles = cibles.unsqueeze(-1)
    return periode, serie, entrees[:150], cibles[:150], entrees[150:], cibles[150:]


class SimpleRNN(nn.Module):
    """Une couche RNN réutilisée dans le temps, puis une lecture du dernier état."""

    def __init__(self) -> None:
        super().__init__()
        self.rnn = nn.RNN(input_size=1, hidden_size=16, batch_first=True)
        self.sortie = nn.Linear(16, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        etats, _ = self.rnn(x)
        return self.sortie(etats[:, -1, :])


class SimpleLSTM(nn.Module):
    """Mémoire à portes : état caché et état de cellule, lus au dernier pas."""

    def __init__(self) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size=1, hidden_size=16, num_layers=1, batch_first=True)
        self.sortie = nn.Linear(16, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        etats, _etats_finaux = self.lstm(x)
        return self.sortie(etats[:, -1, :])


class MiniTransformer(nn.Module):
    """Encodeur à une couche : projection, positions apprises, attention, dernière position."""

    def __init__(self, longueur_max: int = 10) -> None:
        super().__init__()
        dimension = 16
        self.projection = nn.Linear(1, dimension)
        self.positions = nn.Embedding(longueur_max, dimension)
        couche = nn.TransformerEncoderLayer(
            d_model=dimension,
            nhead=2,
            dim_feedforward=32,
            dropout=0.0,
            batch_first=True,
        )
        self.encodeur = nn.TransformerEncoder(couche, num_layers=1)
        self.sortie = nn.Linear(dimension, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        longueur = x.size(1)
        projete = self.projection(x)
        indices = torch.arange(longueur, device=projete.device)
        projete = projete + self.positions(indices).unsqueeze(0)
        representations = self.encodeur(projete)
        return self.sortie(representations[:, -1, :])


def train_and_eval(
    modele: nn.Module,
    x_train: torch.Tensor,
    y_train: torch.Tensor,
    x_test: torch.Tensor,
    y_test: torch.Tensor,
    epochs: int = 300,
    lr: float = 0.01,
    log: bool = True,
) -> dict:
    """Boucle du cours : MSE, Adam, puis erreur sur la fin de la série."""
    critere = nn.MSELoss()
    optimiseur = torch.optim.Adam(modele.parameters(), lr=lr)
    modele.train()
    history: list[float] = []
    for epoch in range(epochs):
        predictions = modele(x_train)
        perte = critere(predictions, y_train)
        optimiseur.zero_grad()
        perte.backward()
        optimiseur.step()
        history.append(float(perte.item()))
        if log and (epoch + 1) % 50 == 0:
            print(f"Epoch {epoch + 1:3d} | Erreur : {perte.item():.6f}")
    modele.eval()
    with torch.no_grad():
        predictions = modele(x_test)
        erreur_test = critere(predictions, y_test)
    if log:
        print(f"\nErreur de test : {erreur_test.item():.6f}")
        print(f"Valeur réelle  : {y_test[0].item():.4f}")
        print(f"Valeur prédite : {predictions[0].item():.4f}")
    return {
        "history": history,
        "test_loss": float(erreur_test.item()),
        "predictions": predictions,
        "y_test": y_test,
    }


class _MiniCausal(nn.Module):
    """Une couche d'attention causale : une position ne voit pas les caractères futurs."""

    def __init__(self, vocabulaire: int, longueur: int) -> None:
        super().__init__()
        self.emb = nn.Embedding(vocabulaire, 32)
        self.pos = nn.Embedding(longueur, 32)
        couche = nn.TransformerEncoderLayer(
            d_model=32,
            nhead=4,
            dim_feedforward=64,
            dropout=0.0,
            batch_first=True,
        )
        self.encodeur = nn.TransformerEncoder(couche, num_layers=1, enable_nested_tensor=False)
        self.tete = nn.Linear(32, vocabulaire)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        longueur = x.size(1)
        positions = torch.arange(longueur, device=x.device)
        cache = self.emb(x) + self.pos(positions)
        masque = torch.triu(torch.ones(longueur, longueur, dtype=torch.bool, device=x.device), diagonal=1)
        return self.tete(self.encodeur(cache, mask=masque))


def prolonger_phrase(epochs: int = 300, seed: int = 42) -> str:
    """Apprend une seule phrase anglaise et en prolonge l'amorce. Ce n'est pas GPT-2."""
    torch.manual_seed(seed)
    texte = "Artificial intelligence can help people"
    amorce = "Artificial intelligence can help"
    caracteres = sorted(set(texte))
    indice_de = {caractere: indice for indice, caractere in enumerate(caracteres)}
    caractere_de = {indice: caractere for caractere, indice in indice_de.items()}
    donnees = torch.tensor([indice_de[caractere] for caractere in texte], dtype=torch.long)
    modele = _MiniCausal(len(caracteres), len(donnees))
    optimiseur = torch.optim.Adam(modele.parameters(), lr=0.05)
    critere = nn.CrossEntropyLoss()
    entrees = donnees[:-1].unsqueeze(0)
    cibles = donnees[1:].unsqueeze(0)
    modele.train()
    for _ in range(epochs):
        optimiseur.zero_grad()
        logits = modele(entrees)
        perte = critere(logits.reshape(-1, logits.size(-1)), cibles.reshape(-1))
        perte.backward()
        optimiseur.step()
    contexte = [indice_de[caractere] for caractere in amorce]
    modele.eval()
    with torch.no_grad():
        for _ in range(len(texte) - len(amorce)):
            fenetre = contexte[-(len(donnees) - 1) :]
            entree = torch.tensor(fenetre, dtype=torch.long).unsqueeze(0)
            logits = modele(entree)
            contexte.append(int(logits[0, -1].argmax()))
    return "".join(caractere_de[indice] for indice in contexte)


class _MiniMasque(nn.Module):
    """Encodeur sans masque causal : le trou voit le contexte des deux côtés."""

    def __init__(self, taille_vocabulaire: int, longueur: int) -> None:
        super().__init__()
        self.identifiant_masque = taille_vocabulaire
        self.emb = nn.Embedding(taille_vocabulaire + 1, 32)
        self.pos = nn.Embedding(longueur, 32)
        couche = nn.TransformerEncoderLayer(
            d_model=32,
            nhead=4,
            dim_feedforward=64,
            dropout=0.0,
            batch_first=True,
        )
        self.encodeur = nn.TransformerEncoder(couche, num_layers=1, enable_nested_tensor=False)
        self.tete = nn.Linear(32, taille_vocabulaire)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        longueur = x.size(1)
        positions = torch.arange(longueur, device=x.device)
        return self.tete(self.encodeur(self.emb(x) + self.pos(positions)))


def proposer_masque(epochs: int = 400, seed: int = 42) -> list[tuple[str, float]]:
    """Retrouve un mot masqué sur trois phrases. Ce n'est pas BERT multilingue."""
    torch.manual_seed(seed)
    phrases = [
        "Paris est la capitale de la France".split(),
        "Rome est la capitale de l Italie".split(),
        "Madrid est la capitale de l Espagne".split(),
    ]
    vocabulaire = sorted({mot for phrase in phrases for mot in phrase})
    indice_de = {mot: indice for indice, mot in enumerate(vocabulaire)}
    mot_de = {indice: mot for mot, indice in indice_de.items()}
    identifiant_cible = indice_de["capitale"]
    longueur_max = max(len(phrase) for phrase in phrases)
    modele = _MiniMasque(len(vocabulaire), longueur_max)
    optimiseur = torch.optim.Adam(modele.parameters(), lr=0.05)
    critere = nn.CrossEntropyLoss()
    modele.train()
    for _ in range(epochs):
        optimiseur.zero_grad()
        pertes = []
        for phrase in phrases:
            identifiants = [indice_de[mot] for mot in phrase]
            position = phrase.index("capitale")
            identifiants[position] = modele.identifiant_masque
            entree = torch.tensor(identifiants, dtype=torch.long).unsqueeze(0)
            logits = modele(entree)
            cible = torch.tensor([identifiant_cible])
            pertes.append(critere(logits[0, position].unsqueeze(0), cible))
        torch.stack(pertes).mean().backward()
        optimiseur.step()
    phrase = phrases[0]
    position_masque = phrase.index("capitale")
    identifiants = [indice_de[mot] for mot in phrase]
    identifiants[position_masque] = modele.identifiant_masque
    entree = torch.tensor(identifiants, dtype=torch.long).unsqueeze(0)
    modele.eval()
    with torch.no_grad():
        probabilites = torch.softmax(modele(entree)[0, position_masque], dim=-1)
        top_probabilites, top_indices = torch.topk(probabilites, k=5)
    return [(mot_de[int(indice)], float(proba)) for proba, indice in zip(top_probabilites, top_indices)]
