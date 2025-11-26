import os
import torch
import shutil
import time
# FastAPI
from typing import Literal, List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
# Парсинг документов
from object.LoadDOCX import parse_docx
from object.LoadPDF import parse_pdf
from object.LoadDOC_RTF import parse_doc_or_rtf
# Генерация чанков полсе парсинга
from object.GenChunk_old import normalize_pre_chank, add_source_and_id
# Модели
from object.SystemSearch import SearchSystem
from object.Models import Reranker, LLM


app = FastAPI()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

DB_SEARCH = SearchSystem(device=DEVICE)
DB_SEARCH.load("./SearchStartData/pre-best-V4") # Для локальных тестов

RERANKER = Reranker(device=DEVICE)
LLM = LLM(device=DEVICE)


tmp_folder = Path("inputTMP")
tmp_folder.mkdir(exist_ok=True)


def save_temp_file(upload: UploadFile) -> Path:
    # Создаём папку, если её нет
    tmp_folder.mkdir(parents=True, exist_ok=True)

    tmp_path = tmp_folder / upload.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    return tmp_path

def get_parser_for_file(path: Path):
    ext = path.suffix.lower()

    mapping = {
        ".docx": parse_docx,
        ".doc": parse_doc_or_rtf,
        ".pdf": parse_pdf,
        ".rtf": parse_doc_or_rtf,
    }

    parser = mapping.get(ext)
    if not parser:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    return parser

@app.post("/create_file")
def create_file(file: UploadFile = File(...)):
    # Сохраняем временно файл
    temp_path = save_temp_file(file)

    # Проверка что в бд нет файла
    if DB_SEARCH.file_exists(temp_path.stem):
        raise HTTPException(status_code=400, detail=f"File {filename} already exists")

    # Определяем нужный парсер
    parser = get_parser_for_file(temp_path)

    # Парсим и получаем пре чанки
    try:
        pre_chunks = parser(temp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {e}")

    # Создаем чанки
    chunks = normalize_pre_chank(pre_chunks, 50, 120)
    chunks = add_source_and_id(chunks, temp_path.stem)

    # Добавляем чанки
    DB_SEARCH.add_chunks(chunks)
    DB_SEARCH.build_index()

    # удаляем временный файл
    temp_path.unlink(missing_ok=True)

    return {"status": "created", "filename": temp_path.stem}


@app.put("/update_file")
def update_file(file: UploadFile = File(...)):
    # Сохраняем временно файл
    temp_path = save_temp_file(file)

    # Проверка что в бд нет файла
    if not DB_SEARCH.file_exists(temp_path.stem):
        raise HTTPException(status_code=400, detail=f"File {temp_path.stem} not exists")

    # Удаляем старые чанки
    DB_SEARCH.remove_by_source(temp_path.stem)

    # Определяем нужный парсер
    parser = get_parser_for_file(temp_path)

    # Парсим и получаем пре чанки
    try:
        pre_chunks = parser(temp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {e}")

    # Создаем чанки
    chunks = normalize_pre_chank(pre_chunks, 50, 120)
    chunks = add_source_and_id(chunks, temp_path.stem)

    # Добавляем чанки
    DB_SEARCH.add_chunks(chunks)
    DB_SEARCH.build_index()

    # удаляем временный файл
    temp_path.unlink(missing_ok=True)

    return {"status": "created", "filename": temp_path.stem}


@app.delete("/delete_file/{filename}")
def delete_file(filename: str):
    name_without_ext = os.path.splitext(filename)[0]
    # Проверка что в бд нет файла
    if not DB_SEARCH.file_exists(name_without_ext):
        raise HTTPException(status_code=400, detail=f"File {filename} not exists")

    # Удаляем старые чанки
    DB_SEARCH.remove_by_source(name_without_ext)
    return {"status": "deleted", "filename": filename}


def smart_search_chunk(searchSystem: SearchSystem, reranker: Reranker, question: str):
    # На основе вопроса получаем ближайшие чанки (RAG + BM25)
    chunks = searchSystem.search_hybrid(question, top_k=20, alpha=0.8)

    # Расширяем контекс для каждого чанка(+-1, сохраняя score и chunkID): {"source": str, "chunkIDs": array, "texts": array}
    filter_result = []

    for chunk in chunks:
        context_chunks = searchSystem.get_context_chunks(
            chunk["payload"]["chunkID"],
            chunk["payload"]["source"],
        )

        chunk_ids = [ch["chunkID"] for ch in context_chunks]
        texts = [ch["text"] for ch in context_chunks]

        filter_result.append({
            "source": chunk["payload"]["source"],
            "chunkIDs": chunk_ids,
            "texts": texts
        })

    # Получение лучших чанков(с контекстом)
    reranker_output = reranker.rerank_results(question, filter_result, 5, 0.35)

    return reranker_output

# Объекты
# Создаём Pydantic модель для ответа
class ChatAnswerResponse(BaseModel):
    answer: str
    files_used: List[str]


class ChatMessage(BaseModel):
    user: Literal["system", "user"]
    content: str

class ChatRequest(BaseModel):
    chat: List[ChatMessage]

@app.post("/chat/answer")
def chat_answer(req: ChatRequest):

    start_total = time.time()

    # Получаем последний вопрос пользователя
    question = req.chat[-1].content

    # Нахождение нужных чанков
    top_k_chunks = smart_search_chunk(DB_SEARCH, RERANKER, question)

    # -------------------------------------------------------------------- Объеденяем чанки по source
    # merged_source = {}
    # for context_reranker_chunk in reranker_output:
    #     key = context_reranker_chunk["source"]
    #
    #     if key in merged_source:
    #         merged_source[key]["chunkIDs"].extend(context_reranker_chunk["chunkIDs"])
    #         merged_source[key]["texts"].extend(context_reranker_chunk["texts"])
    #     else:
    #         merged_source[key] = {
    #             "chunkIDs": list(context_reranker_chunk["chunkIDs"]),
    #             "texts": list(context_reranker_chunk["texts"])
    #         }
    #
    # source_chunks = []
    # source_doc = []
    # for src, chunks in merged_source.items():
    #     source_doc.append(src)
    #     # удаляем дубли по chunkID, сохраняя порядок
    #     seen_ids = set()
    #     unique_chunkIDs = []
    #     unique_texts = []
    #
    #     for cid, text in zip(chunks["chunkIDs"], chunks["texts"]):
    #         if cid not in seen_ids:
    #             seen_ids.add(cid)
    #             unique_chunkIDs.append(cid)
    #             unique_texts.append(text)
    #
    #     # создаём список кортежей и сортируем по chunkID
    #     paired_sorted = sorted(zip(unique_chunkIDs, unique_texts), key=lambda x: x[0])
    #
    #     if paired_sorted:
    #         chunkIDs_sorted, texts_sorted = zip(*paired_sorted)
    #     else:
    #         chunkIDs_sorted, texts_sorted = [], []
    #
    #     source_chunks.append({
    #         "source": src,
    #         "chunkIDs": list(chunkIDs_sorted),
    #         "texts": list(texts_sorted)
    #     })
    # -------------------------------------------------------------------- Объеденяем чанки по source

    # Генерация отвера по чанкам
    context = ""
    source_chunks = set()
    for chunk_with_context in top_k_chunks:
        source_chunks.add(chunk_with_context["source"])
        for chunk in chunk_with_context["texts"]:
            context = context + chunk + '\n'
        context = context + "\n---\n"

    # ====== Генерация ответа ======
    answer = LLM.generate_answer(question, context)

    total_time = time.time() - start_total
    print(f"Общее время:         {total_time:.1f} сек")
    # Возврат через BaseModel + JSONResponse
    response_data = ChatAnswerResponse(
        answer=answer,
        files_used=list(source_chunks),
    )
    return response_data