from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModelForCausalLM
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

SYSTEM_PROMPT = (
    "Используя только предоставленный контекст из документов, дай краткий и точный ответ на вопрос пользователя."
    "Если контекст не содержит ответа — сообщи об этом."
)

class LLM:
    def __init__(self, model="./model/decoder-encoder", device="cpu"):
        self.tokenizer = AutoTokenizer.from_pretrained(model)
        self.model = AutoModelForCausalLM.from_pretrained(model).to(device)
        self.device = device

    def generate_answer(self, chat_history, question, context_text):
        # Преобразуем ключи, если нужно
        for msg in chat_history:
            if "message" in msg:
                msg["content"] = msg.pop("message")

        # Добавляем вопрос пользователя в историю
        chat_history.append({"role": "user", "content": question})

        # Формируем временные сообщения для модели
        messages_for_model = [{"role": "system", "content": "Используя только предоставленный контекст из документов, "
                                                            "дай краткий и точный ответ на вопрос пользователя. "
                                                            "Если контекст не содержит ответа — сообщи об этом."},
                              {"role": "system", "content": f"Контекст документов:\n{context_text}"}]

        # Добавляем историю чата (вопросы и ответы) + текущий вопрос
        messages_for_model.extend(chat_history)

        # Применяем шаблон
        text = self.tokenizer.apply_chat_template(
            messages_for_model,
            tokenize=False,
            add_generation_prompt=True
        )

        # Токенизация
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.device)

        # Генерация
        generated_ids = self.model.generate(
            **model_inputs,
            max_new_tokens=512,
            do_sample=False,
            temperature=1.0,
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