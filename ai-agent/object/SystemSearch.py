from typing import List, Dict
import numpy as np
import pickle
import re
import string

from nltk.stem import SnowballStemmer
from rank_bm25 import BM25L
from sentence_transformers import SentenceTransformer


# ======================= НОРМАЛИЗАЦИЯ =======================
def normalize_basic(text: str) -> str:
    text = text.replace("\t", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# --- Улучшенная токенизация для BM25 ---
stemmer = SnowballStemmer("russian")

def bm25_tokenize(text: str) -> list:
    text = normalize_basic(text)
    text = text.lower()

    # сохраняем дефисы (важно для терминов)
    text = text.replace(".", " ")

    # разрешаем буквы / цифры / дефис
    text = re.sub(r"[^a-zа-яё0-9\-]+", " ", text)

    tokens = text.split()

    # стемминг
    tokens = [stemmer.stem(t) for t in tokens]

    return tokens


# ======================= Search System =======================
class SearchSystem:
    def __init__(self, model="./model/encoder", device="cpu"):
        self.encoder = SentenceTransformer(model)

        # Embeddings index
        self.matrix = None
        self.norm_matrix = None

        # BM25
        self.bm25 = None
        self.bm25_corpus = None

        # Payloads
        self.payloads = []
        self.ids = []

    # ======================= ADD CHUNKS =======================
    def add_chunks(self, chunks):
        raw_texts = [normalize_basic(c["text"]) for c in chunks]
        bm25_tokens = [bm25_tokenize(c["text"]) for c in chunks]

        # Embeddings
        vectors = (
            self.encoder.encode(
                raw_texts, convert_to_numpy=True, normalize_embeddings=False
            ).astype(np.float32)
        )

        self._add_internal(
            ids=[c["chunkHash"] for c in chunks],
            vectors=vectors,
            payloads=[
                {
                    **c,
                    "text_raw": raw_texts[i],
                    "tokens": bm25_tokens[i],
                }
                for i, c in enumerate(chunks)
            ]
        )

    def _add_internal(self, ids, vectors, payloads):
        if self.matrix is None:
            self.matrix = vectors
        else:
            self.matrix = np.vstack([self.matrix, vectors])

        self.ids.extend(ids)
        self.payloads.extend(payloads)

    # ======================= BUILD INDEX =======================
    def build_index(self, bm25_k1=1.5, bm25_b=0.1):
        # Embeddings
        norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
        self.norm_matrix = self.matrix / norms

        # BM25
        self.bm25_corpus = [p["tokens"] for p in self.payloads]
        self.bm25 = BM25L(
            self.bm25_corpus,
            k1=bm25_k1,     # степень влияния частоты слова (TF)
            b=bm25_b       # влияние длины документа
        )

    # ======================= REMOVE CHUNKS BY SOURCE =======================
    def remove_by_source(self, source_name: str):
        keep_indices = [i for i, p in enumerate(self.payloads) if p.get("source") != source_name]

        if not keep_indices:
            self.matrix = None
            self.norm_matrix = None
            self.payloads = []
            self.ids = []
            self.bm25_corpus = []
            self.bm25 = None
            return

        # фильтруем embeddings, payloads и ids
        self.matrix = self.matrix[keep_indices]
        self.payloads = [self.payloads[i] for i in keep_indices]
        self.ids = [self.ids[i] for i in keep_indices]

        # ! ПОСЛЕ нужно сделать build_index()
        self.norm_matrix = None
        self.bm25_corpus = []
        self.bm25 = None

    # ======================= GET CONTEXT CHUNKS =======================
    def get_context_chunks(self, chunk_id: str, source: str, n: int = 1, include_self: bool = True) -> List[Dict]:
        # Находим все индексы чанков с заданным source
        source_indices = [i for i, p in enumerate(self.payloads) if p.get("source") == source]

        # Находим индекс целевого чанка в пределах этого source
        try:
            idx_in_source = next(i for i in source_indices if self.payloads[i]["chunkID"] == chunk_id)
        except StopIteration:
            return []

        start = max(0, idx_in_source - n)
        end = min(len(self.payloads), idx_in_source + n + 1)

        context = []
        for i in range(start, end):
            if not include_self and i == idx_in_source:
                continue
            # Берем только чанки того же source
            if self.payloads[i]["source"] == source:
                context.append(self.payloads[i])

        return context

    # ======================= CHECK IF FILE EXISTS =======================
    def file_exists(self, source_name: str) -> bool:
        return any(p.get("source") == source_name for p in self.payloads)

    # ======================= SEARCH: EMBEDDINGS =======================
    def search_embeddings(self, query, top_k=5):
        q = self.encoder.encode(
            [normalize_basic(query)],
            convert_to_numpy=True,
            normalize_embeddings=True
        )[0]

        scores = self.norm_matrix @ q
        idx = np.argsort(-scores)[:top_k]

        return [
            {"chunkHash": self.ids[i], "score": float(scores[i]), "payload": self.payloads[i]}
            for i in idx
        ]

    # ======================= SEARCH: BM25 =======================
    def search_bm25(self, query, top_k=5):
        tokens = bm25_tokenize(query)
        scores = self.bm25.get_scores(tokens)

        # --- нормализация критически важна ---
        scores = (scores - scores.min()) / (scores.max() - scores.min() + 1e-6)

        idx = np.argsort(-scores)[:top_k]
        return [
            {"chunkHash": self.ids[i], "score": float(scores[i]), "payload": self.payloads[i]}
            for i in idx
        ]

    # ======================= HYBRID =======================
    def search_hybrid(self, query, top_k=5, alpha=0.5):
        """
        alpha = 0.5 → 50% embedding + 50% BM25 (нормализованный)
        """

        # EMBEDDINGS
        q_emb = self.encoder.encode(
            [normalize_basic(query)],
            convert_to_numpy=True,
            normalize_embeddings=True
        )[0]
        sim_emb = self.norm_matrix @ q_emb

        # BM25
        tokens = bm25_tokenize(query)
        sim_bm25 = self.bm25.get_scores(tokens)
        sim_bm25 = (sim_bm25 - sim_bm25.min()) / (sim_bm25.max() - sim_bm25.min() + 1e-6)

        # Гибрид
        score = alpha * sim_emb + (1 - alpha) * sim_bm25

        idx = np.argpartition(-score, top_k)[:top_k]
        idx = idx[np.argsort(-score[idx])]

        return [
            {
                "chunkHash": self.ids[i],
                "score": float(score[i]),
                "payload": self.payloads[i]
            }
            for i in idx
        ]

    # ======================= SAVE / LOAD =======================
    def save(self, path):
        data = {
            "matrix": self.matrix,
            "norm_matrix": self.norm_matrix,
            "payloads": self.payloads,
            "ids": self.ids,
            "bm25_corpus": self.bm25_corpus,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

    def load(self, path):
        with open(path, "rb") as f:
            data = pickle.load(f)

        self.matrix = data["matrix"]
        self.norm_matrix = data["norm_matrix"]
        self.payloads = data["payloads"]
        self.ids = data["ids"]

        self.bm25_corpus = data["bm25_corpus"]
        self.bm25 = BM25L(self.bm25_corpus)
