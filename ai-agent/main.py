import os
import shutil
import tempfile
import time
from typing import Literal, List

import torch
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from HelpObject import Reranker
from SystemSearch import SearchSystem
from LoadDOCX import parse_docx
from LoadPDF import parse_pdf
from LoadDOC_RTF import parse_doc_or_rtf
from GenChunk import normalize_pre_chank, add_source_and_id
from LLM import LLM

app = FastAPI()  # <- обязательно до декораторов

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

DB_SEARCH = SearchSystem(device=DEVICE)
DB_SEARCH.load("./SearchStartData/pre-best-V4") # Для локальных тестов

RERANKER = Reranker(device=DEVICE)
LLM = LLM(device=DEVICE)


folder = Path("dataset")
folderTMP = Path("inputTMP")
folder.mkdir(exist_ok=True)


def save_temp_file(upload: UploadFile) -> Path:
    # Создаём папку, если её нет
    folderTMP.mkdir(parents=True, exist_ok=True)

    tmp_path = folderTMP / upload.filename
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

@app.post("/create_file/{filename}")
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


@app.put("/update_file/{filename}")
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

# Объекты
# Создаём Pydantic модель для ответа
class ChatAnswerResponse(BaseModel):
    answer: str
    files_used: List[str]


class ChatMessage(BaseModel):
    user: Literal["system", "user"]
    content: str
    files: List[str] = []

class ChatRequest(BaseModel):
    chat: List[ChatMessage]

@app.post("/chat/answer")
def chat_answer(req: ChatRequest):

    # собрать контекст
    system_messages = []
    user_messages = []
    file_contents = {}
    start_total = time.time()

    # Получаем последний вопрос пользователя
    question = req.chat[-1].content

    # Поиск по базе зананий RAG + BM25
    results = DB_SEARCH.search_hybrid(question, top_k=20, alpha=0.8)

    # Получаем контекст для каждого чанка и приводим к стуктуре
    filter_result = []

    for item in results:
        context_chunks = DB_SEARCH.get_context_chunks(
            item["payload"]["chunkID"],
            item["payload"]["source"]
        )

        chunk_ids = [ch["chunkID"] for ch in context_chunks]
        texts = [ch["text"] for ch in context_chunks]

        filter_result.append({
            "source": item["payload"]["source"],
            "chunkIDs": chunk_ids,
            "texts": texts
        })

    # Получение лучших чанков
    reranker_output = RERANKER.rerank_results(
        "Что должно быть обязательно отражено в протоколе (акте, заключении) по результатам визуального и измерительного контроля?",
        filter_result, 5)

    # Объеденяем чанки по source
    merged_source = {}
    for context_reranker_chunk in reranker_output:
        key = context_reranker_chunk["source"]

        if key in merged_source:
            merged_source[key]["chunkIDs"].extend(context_reranker_chunk["chunkIDs"])
            merged_source[key]["texts"].extend(context_reranker_chunk["texts"])
        else:
            merged_source[key] = {
                "chunkIDs": list(context_reranker_chunk["chunkIDs"]),
                "texts": list(context_reranker_chunk["texts"])
            }

    source_chunks = []
    source_doc = []
    for src, chunks in merged_source.items():
        source_doc.append(src)
        # удаляем дубли по chunkID, сохраняя порядок
        seen_ids = set()
        unique_chunkIDs = []
        unique_texts = []

        for cid, text in zip(chunks["chunkIDs"], chunks["texts"]):
            if cid not in seen_ids:
                seen_ids.add(cid)
                unique_chunkIDs.append(cid)
                unique_texts.append(text)

        # создаём список кортежей и сортируем по chunkID
        paired_sorted = sorted(zip(unique_chunkIDs, unique_texts), key=lambda x: x[0])

        if paired_sorted:
            chunkIDs_sorted, texts_sorted = zip(*paired_sorted)
        else:
            chunkIDs_sorted, texts_sorted = [], []

        source_chunks.append({
            "source": src,
            "chunkIDs": list(chunkIDs_sorted),
            "texts": list(texts_sorted)
        })

    # Генерация отвера по чанкам
    context = ""
    for source_chunk in source_chunks:
        for chunk in source_chunk["texts"]:
            context = context + chunk + '\n'
        context = context + "\n---\n"

    answer = LLM.generate_answer(question, context)

    total_time = time.time() - start_total
    print(f"Общее время:         {total_time:.1f} сек")
    # Возврат через BaseModel + JSONResponse
    response_data = ChatAnswerResponse(
        answer=answer,
        files_used=source_doc,
    )
    return response_data