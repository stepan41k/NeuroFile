import csv
import time
from pathlib import Path
import torch
from object.SystemSearch import SearchSystem
from object.Models import Reranker, LLM

# =========================== НАСТРОЙКИ ===========================
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

ENCODER_MODEL = "./model/encoder"
LLM_MODEL = "./model/decoder-encoder"
RERANKER_MODEL = "./model/reranker"
DB_DATA = "./SearchStartData/pre-best-V4.pkl"

SYSTEM_PROMPT = (
    "Используя только предоставленный контекст из документов, дай краткий и точный ответ на вопрос пользователя."
    "Если контекст не содержит ответа — сообщи об этом."
)


def smart_search_chunk(searchSystem: SearchSystem, reranker: Reranker, question: str):
    # На основе вопроса получаем ближайшие чанки (RAG + BM25)
    chunks = searchSystem.search_hybrid(question, top_k=20, alpha=0.8)

    # Расширяем контекс для каждого чанка(+-1, сохраняя score и chunkID): {"source": str, "chunkIDs": array, "texts": array}
    filter_result = []

    for chunk in chunks:
        context_chunks = searchSystem.get_context_chunks(
            chunk["payload"]["chunkID"],
            chunk["payload"]["source"],
            0
        )

        chunk_ids = [ch["chunkID"] for ch in context_chunks]
        texts = [ch["text"] for ch in context_chunks]

        filter_result.append({
            "source": chunk["payload"]["source"],
            "chunkIDs": chunk_ids,
            "texts": texts
        })
    # Получение лучших чанков(с контекстом)
    reranker_output = reranker.rerank_results(question, filter_result, 5, 0.0)

    return reranker_output

# ==============================
#           MAIN
# ==============================
def main():
    start_total = time.time()
    # ====================== ЗАГРУЗКА МОДЕЛЕЙ ========================
    print("1/4 Загрузка SearchSystem (RAG + BM25)")
    searchSystem = SearchSystem(model=ENCODER_MODEL, device=DEVICE)
    searchSystem.load(DB_DATA)

    print("2/4 Загрузка Reranker")
    reranker = Reranker(model=RERANKER_MODEL, device=DEVICE)

    print("3/4 Загрузка LLM")
    llm = LLM(model=LLM_MODEL, device=DEVICE)

    # =========================== ЧТЕНИЕ ВОПРОСОВ ===========================
    print("4/4 Чтение input.csv...")
    input_path = Path("test_file/input.csv")
    if not input_path.exists():
        return

    # ============================== ОБРАБОТКА ===============================
    start_processing = time.time()
    total_questions = 0
    with open("test_file/input.csv", newline="", encoding="utf-8") as f_in, \
         open("output.csv", "w", newline="", encoding="utf-8") as f_out:

        reader = csv.DictReader(f_in)
        writer = csv.writer(f_out)
        writer.writerow(["id", "answer", "documents"])

        for row in reader:
            total_questions += 1
            q_id = row["id"]
            question = row["question"]

            # Нахождение нужных чанков
            top_k_chunks = smart_search_chunk(searchSystem, reranker, question)

            # Генерация отвера по чанкам
            context = ""
            source_chunks = set()
            for chunk_with_context in top_k_chunks:
                source_chunks.add(chunk_with_context["source"])
                for chunk in chunk_with_context["texts"]:
                    context = context + chunk + '\n'
                context = context + "\n---\n"

            # ====== Генерация ответа ======
            # answer = llm.generate_answer_old(question, context)
            answer = llm.generate_answer([], question, context)

            used_docs = {c for c in source_chunks}
            writer.writerow([q_id, answer, "; ".join(used_docs)])

    total_processing_time = time.time() - start_processing
    total_time = time.time() - start_total
    avg_speed = total_processing_time / total_questions
    print(f"Всего вопросов:      {total_questions}")
    print(f"Время обработки:     {total_processing_time:.1f} сек")
    print(f"Средняя скорость:    {avg_speed:.2f} вопросов в секунду")
    print(f"Общее время:         {total_time:.1f} сек")
    print("ГОТОВО! output.csv сохранён.")

if __name__ == "__main__":
    main()
