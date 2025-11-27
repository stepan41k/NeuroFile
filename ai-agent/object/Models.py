from collections import defaultdict

from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModelForCausalLM
from sentence_transformers import CrossEncoder
from itertools import combinations
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
        # Берем все тексты из chunk['texts']
        pairs = [(query, ' '.join(r["texts"])) for r in chunks]

        # Получаем score
        scores = self.RerankerModel.predict(pairs)

        # Добавляем score в каждый результат
        chunks_with_scores = [
            {**r, "score": float(s)} for r, s in zip(chunks, scores)
        ]

        # Фильтруем по threshold
        chunks_filtered = [r for r in chunks_with_scores if r["score"] >= threshold]

        # Сортируем по убыванию score и берем топ-K
        reranked = sorted(chunks_filtered, key=lambda x: x["score"], reverse=True)[:top_k_rerank]

        return reranked


# ======================= LOGICAL RELATIONSHIP =======================
class LogicalRelationship:
    def __init__(self, model="./molder/lr", device="cpu"):
        self.tokenizer = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForSequenceClassification.from_pretrained(model)
        if torch.cuda.is_available():
            self.cuda()
        self.device = device

        # ======================= CHECK CONFLICT =======================

    def check_conflict(self, text1, text2):
        with torch.inference_mode():
            out = self.model(**self.tokenizer(text1, text2, return_tensors='pt').to(self.model.device))
            proba = torch.softmax(out.logits, -1).cpu().numpy()[0]
        data = ({v: proba[k] for k, v in self.model.config.id2label.items()})
        return data['contradiction']

        # =================== BUILD MATRIX CONFLICT ====================

    def build_conflict_matrix(self, chunks, threshold=0.5):
        """
        Возвращает:
        - conflict_matrix — матрица конфликтов между чанками
        - source_conflicts — список кортежей (sourceA, sourceB, score)
        """

        # 1. Собираем текст каждого чанка
        texts = [" ".join(c["texts"]) for c in chunks]
        sources = [c["source"] for c in chunks]
        n = len(chunks)

        # 2. Матрица конфликтов
        conflict_matrix = np.zeros((n, n), dtype=float)

        # 3. Временное хранилище конфликтов между источниками
        source_pairs = {}  # (A, B) -> [scores]

        for (i, j) in combinations(range(n), 2):
            score = self.check_conflict(texts[i], texts[j])
            conflict_matrix[i][j] = score
            conflict_matrix[j][i] = score

            if score >= threshold:
                s1, s2 = sources[i], sources[j]
                key = tuple(sorted([s1, s2]))
                source_pairs.setdefault(key, []).append(score)

        # 4. Финальные конфликты между документами
        #    теперь в виде списка кортежей:
        #    (sourceA, sourceB, avg_score)
        source_conflicts = [
            (a, b, float(np.mean(scores)))
            for (a, b), scores in source_pairs.items()
        ]

        return conflict_matrix, source_conflicts


    def build_document_conflict_matrix(self, chunks, threshold=0.5, agg='max'):
        # 1. Объединяем чанки по source
        docs = {}
        for ch in chunks:
            src = ch['source']
            if src not in docs:
                docs[src] = []
            # Объединяем текст чанка с контекстом
            combined_text = " ".join(ch["texts"])
            docs[src].append(combined_text)

        # 2. Матрица конфликтов
        sources = list(docs.keys())
        n = len(sources)
        conflict_matrix = [[0.0] * n for _ in range(n)]
        conflict_pairs = []

        for i, j in combinations(range(n), 2):
            src_i, src_j = sources[i], sources[j]
            scores = []

            # Сравниваем все чанк-пары между документами
            for text_i in docs[src_i]:
                for text_j in docs[src_j]:
                    score = self.check_conflict(text_i, text_j)
                    scores.append(score)

            # Агрегируем score
            if agg == 'max':
                agg_score = max(scores)
            elif agg == 'mean':
                agg_score = sum(scores) / len(scores)
            else:
                raise ValueError("agg должен быть 'max' или 'mean'")

            conflict_matrix[i][j] = conflict_matrix[j][i] = agg_score

            # Сохраняем только если выше threshold
            if agg_score >= threshold:
                conflict_pairs.append((src_i, src_j, agg_score))

        return conflict_matrix, conflict_pairs

    def build_non_conflicting_groups(self, conflicts, threshold=0.5):
        """
        conflicts: список кортежей (doc1, doc2, score)
        threshold: минимальный score, чтобы считать документы конфликтующими
        """
        # 1. Создаем словарь конфликтов
        conflict_map = defaultdict(set)
        docs = set()
        for d1, d2, score in conflicts:
            if score >= threshold:
                conflict_map[d1].add(d2)
                conflict_map[d2].add(d1)
            docs.add(d1)
            docs.add(d2)

        # 2. Формируем группы
        groups = []
        for doc in docs:
            placed = False
            for group in groups:
                if not any(conflict in group for conflict in conflict_map[doc]):
                    group.add(doc)
                    placed = True
                    break
            if not placed:
                groups.append({doc})

        # 3. Вернем как список списков
        return [list(g) for g in groups]

SYSTEM_PROMPT = (
    "Используя только предоставленный контекст из документов, дай краткий и точный ответ на вопрос пользователя."
    "Если контекст не содержит ответа — сообщи об этом."
)

class LLM:
    def __init__(self, model="./model/decoder-encoder", device="cpu"):
        self.tokenizer = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForCausalLM.from_pretrained(model).to(device)
        self.device = device

    def generate_answer_old(self, question, context):
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Контекст:\n{context}\n\n"
            f"Вопрос: {question}\nОтвет:"
        )

        inputs = self.tokenizer(prompt, return_tensors="pt", padding=True, truncation=True).to(self.device)

        output = self.model.generate(
            **inputs,
            max_new_tokens=200,
            do_sample=False,
            temperature=1.0,
            eos_token_id=self.tokenizer.eos_token_id,
            pad_token_id=self.tokenizer.eos_token_id
        )

        decoded = self.tokenizer.decode(output[0], skip_special_tokens=True)
        return decoded.split("Ответ:", 1)[-1].strip()

    def generate_answer(self, chat_history, question, context_text, attention=""):
        # Преобразуем ключи, если нужно
        for msg in chat_history:
            if "message" in msg:
                msg["content"] = msg.pop("message")

        # Добавляем вопрос пользователя в историю
        chat_history.append({"role": "user", "content": question})

        # Формируем временные сообщения для модели
        messages_for_model = [{"role": "system", "content": "Используя только предоставленный контекст из документов, "
                                                            "дай краткий и точный ответ на вопрос пользователя. "
                                                            "Если контекст не содержит ответа — сообщи об этом."}]
        if attention != "":
            messages_for_model.append({"role": "system", "content": attention})
        messages_for_model.append({"role": "system", "content": f"Контекст документов:\n{context_text}"})

        # Добавляем историю чата (вопросы и ответы) + текущий вопрос
        messages_for_model.extend(chat_history)

        # Применяем шаблон
        text = self.tokenizer.apply_chat_template(
            messages_for_model,
            tokenize=False,
            add_generation_prompt=True
        )

        # Токенизация
        model_inputs = self.tokenizer([text], return_tensors="pt", padding=True, truncation=True).to(self.device)

        # Генерация
        generated_ids = self.model.generate(
            **model_inputs,
            max_new_tokens=256,
            do_sample=False,
            temperature=0.3,
            eos_token_id=self.tokenizer.eos_token_id,
            pad_token_id=self.tokenizer.eos_token_id
        )

        # Обрезаем токены, которые были в prompt, оставляем только новые
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]

        # Декодируем
        response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()

        # Сохраняем ответ модели в историю
        chat_history.append({"role": "assistant", "content": response})

        return response