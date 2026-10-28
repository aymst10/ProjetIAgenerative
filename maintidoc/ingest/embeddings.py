"""Embeddings de repli : hachage multilingue et histogramme couleur.

Les poids BGE-M3 ou CLIP ne sont chargés que si USE_HEAVY_MODELS=1 et si
les paquets sont déjà installés. Aucun téléchargement n'est tenté sinon.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
from PIL import Image

from maintidoc.config import Settings
from maintidoc.logging_utils import log_event


DIM = 384
HIST_BINS = 8
HIST_DIM = HIST_BINS * 3
TOKEN = re.compile(r"[a-z0-9àâäéèêëïîôùûüç]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    words = [match.group(0).lower() for match in TOKEN.finditer(text)]
    bigrams = [f"{left}_{right}" for left, right in zip(words, words[1:])]
    return words + bigrams


def hashing_embed(text: str, dim: int = DIM) -> np.ndarray:
    vector = np.zeros(dim, dtype=np.float32)
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "little") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector /= norm
    return vector


def embed_texts(texts: list[str], settings: Settings) -> np.ndarray:
    if settings.use_heavy_models:
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("BAAI/bge-m3")
            matrix = np.asarray(model.encode(texts, normalize_embeddings=True), dtype=np.float32)
            return matrix
        except Exception:
            log_event("embedding_fallback", backend="hashing-multilingual-v1", reason="heavy_unavailable")
    if not texts:
        return np.zeros((0, DIM), dtype=np.float32)
    return np.stack([hashing_embed(text) for text in texts])


def color_histogram(path: str) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    array = np.asarray(image)
    parts: list[np.ndarray] = []
    for channel in range(3):
        counts, _ = np.histogram(array[:, :, channel], bins=HIST_BINS, range=(0, 256))
        parts.append(counts.astype(np.float32))
    vector = np.concatenate(parts)
    total = float(vector.sum())
    if total > 0:
        vector /= total
    return vector


def image_signals(path: str) -> dict[str, float | bool]:
    image = Image.open(path).convert("RGB")
    array = np.asarray(image, dtype=np.float32)
    mean = float(array.mean())
    std = float(array.std())
    readable = mean > 25 and std > 8
    channel_means = array.reshape(-1, 3).mean(axis=0)
    names = ("rouge", "vert", "bleu")
    dominant = names[int(np.argmax(channel_means))]
    if channel_means[0] > channel_means[1] + 20 and channel_means[0] > channel_means[2] + 20:
        if channel_means[1] > 80:
            dominant = "orange"
        else:
            dominant = "rouge"
    return {"readable": readable, "mean": mean, "std": std, "dominant_color": dominant}


def embed_image(path: str, settings: Settings) -> np.ndarray:
    if settings.use_heavy_models:
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("sentence-transformers/clip-ViT-B-32-multilingual-v1")
            vector = model.encode(Image.open(path), normalize_embeddings=True)
            return np.asarray(vector, dtype=np.float32)
        except Exception:
            log_event("vision_fallback", backend="colorhist-v1", reason="heavy_unavailable")
    return color_histogram(path)
