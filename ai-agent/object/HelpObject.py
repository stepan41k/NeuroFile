from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sentence_transformers import CrossEncoder
import torch
import numpy as np

# ======================= RERANK OBJECT =======================
class Reranker:
    def __init__(self, model="./model/reranker", device="cpu"):
        # Cross-encoder reranker
        self.RerankerModel = CrossEncoder(model, device=device) if model else None

    # ======================= RERANK =======================
    def rerank_results(self, query, chunks, top_k_rerank=3, threshold=0.0):
        if not self.RerankerModel or not chunks:
            return chunks[:top_k_rerank]

        # Составляем пары для Reranker
        pairs = [(query, ''.join(r["texts"])) for r in chunks]
        scores = self.RerankerModel.predict(pairs)

        # Добавляем score к каждому результату
        chunks_with_scores = [
            {**r, "score": float(s)} for r, s in zip(chunks, scores)
        ]

        # Фильтруем по threshold
        chunks_filtered = [r for r in chunks_with_scores if r["score"] >= threshold]

        # Сортировка по убыванию score и топ-K
        reranked = sorted(chunks_filtered, key=lambda x: x["score"], reverse=True)[:top_k_rerank]

        return reranked


# ======================= LOGICAL RELATIONSHIP =======================
class LogicalRelationship:
    def __init__(self, model="...", device="cpu"):
        self.tokenizer = AutoTokenizer.from_pretrained("cointegrated/rubert-base-cased-nli-threeway")
        self.model = AutoModelForSequenceClassification.from_pretrained("cointegrated/rubert-base-cased-nli-threeway")
        self.model.eval()
        self.model.to(device)
        self.device = device

    # ======================= CHECK CONFLICT =======================
    def check_conflict(self, text1, text2, threshold=0.5):
        inputs = self.tokenizer(text1, text2, return_tensors="pt", truncation=True, max_length=512).to(self.device)
        with torch.no_grad():
            logits = self.model(**inputs).logits
            probs = torch.softmax(logits, dim=1)[0]
        contradiction_prob = probs[0].item()
        return contradiction_prob >= threshold

    # =================== BUILD MATRIX CONFLICT ====================
    def build_conflict_matrix(self, chunks: list):
        n = len(chunks)
        matrix = np.zeros((n, n), dtype=bool)

        for i in range(n):
            for j in range(i + 1, n):
                conflict = self.check_conflict(chunks[i]["text"], chunks[j]["text"])
                matrix[i, j] = conflict
                matrix[j, i] = conflict  # симметрично

        return matrix