"""Prédire le pas suivant d'une sinusoïde, sur CPU, sans poids préentraînés.

Le cours « Architecture Transformer » compare trois mémoires sur le même
découpage : dix valeurs de sin(x) pour prédire la suivante. Ce module
couvre le RNN, puis le LSTM. Aucun fichier de modèle n'est téléchargé.
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
