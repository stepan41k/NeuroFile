import os
import torch
import shutil
import time
from typing import Literal, List
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from object.LoadDOCX import parse_docx
from object.LoadPDF import parse_pdf
from object.LoadDOC_RTF import parse_doc_or_rtf
from object.GenChunk_old import normalize_pre_chank, add_source_and_id
from object.GenChunk import merge_chunks_by_source
from object.SystemSearch import SearchSystem
from object.Models import Reranker, LogicalRelationship, LLM


app = FastAPI()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

DB_SEARCH = SearchSystem(device=DEVICE)
DB_SEARCH.load("./SearchStartData/pre-best-V4.pkl")

RERANKER = Reranker(model='./model/reranker', device=DEVICE)
LLM = LLM(model='./model/qwen3-0.6b',device=DEVICE)

LR = LogicalRelationship(model="./model/lr", device=DEVICE)


tmp_folder = Path("inputTMP")
tmp_folder.mkdir(exist_ok=True)


def save_temp_file(upload: UploadFile) -> Path:
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
    temp_path = save_temp_file(file)

    if DB_SEARCH.file_exists(temp_path.stem):
        raise HTTPException(status_code=400, detail=f"File {temp_path.name} already exists")

    parser = get_parser_for_file(temp_path)

    try:
        pre_chunks = parser(temp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {e}")

    chunks = normalize_pre_chank(pre_chunks, 50, 120)
    chunks = add_source_and_id(chunks, temp_path.stem)

    DB_SEARCH.add_chunks(chunks)
    DB_SEARCH.build_index()

    temp_path.unlink(missing_ok=True)

    return {"status": "created", "filename": temp_path.stem}


@app.post("/update_file")
def update_file(file: UploadFile = File(...)):
    temp_path = save_temp_file(file)

    if not DB_SEARCH.file_exists(temp_path.stem):
        raise HTTPException(status_code=400, detail=f"File {temp_path.name} not exists")

    DB_SEARCH.remove_by_source(temp_path.stem)

    parser = get_parser_for_file(temp_path)

    try:
        pre_chunks = parser(temp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {e}")

    chunks = normalize_pre_chank(pre_chunks, 50, 120)
    chunks = add_source_and_id(chunks, temp_path.stem)

    DB_SEARCH.add_chunks(chunks)
    DB_SEARCH.build_index()

    temp_path.unlink(missing_ok=True)

    return {"status": "created", "filename": temp_path.stem}


@app.delete("/delete_file/{filename}")
def delete_file(filename: str):
    name_without_ext = os.path.splitext(filename)[0]
    if not DB_SEARCH.file_exists(name_without_ext):
        raise HTTPException(status_code=400, detail=f"File {filename} not exists")

    DB_SEARCH.remove_by_source(name_without_ext)
    DB_SEARCH.build_index()
    return {"status": "deleted", "filename": filename}


def smart_search_chunk(searchSystem: SearchSystem, reranker: Reranker, question: str):
    chunks = searchSystem.search_hybrid(question, top_k=15, alpha=0.8)

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

    reranker_output = reranker.rerank_results(question, filter_result, 4, 0.35)

    return reranker_output

class ChatAnswer(BaseModel):
    role: Literal["assistant"]
    message: str
    files_used: List[str]
    attention: List[List[str]]

class ChatAnswerResponse(BaseModel):
    chat: List[ChatAnswer]

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    message: str

class ChatRequest(BaseModel):
    separate_conflicts: bool
    chat: List[ChatMessage]

@app.post("/chat/answer")
def chat_answer(req: ChatRequest):

    start_total = time.time()

    question = req.chat[-1].message

    search_chunk_with_context = time.time()
    top_k_chunks = smart_search_chunk(DB_SEARCH, RERANKER, question)
    search_chunk_with_context = time.time() - search_chunk_with_context

    merge_by_source = merge_chunks_by_source(top_k_chunks)
    matrix, conflicts = LR.build_document_conflict_matrix(top_k_chunks)

    llm_time = time.time()
    answers = []

    def build_context(chunks_group):
        context = ""
        source_chunks = set()
        for chunk_source in chunks_group:
            source_chunks.add(chunk_source["source"])
            context += f"Файл: {chunk_source['source']}\n"
            context += "\n\n".join(chunk_source["texts"]) + "\n\n"
        return context, source_chunks

    if conflicts and req.separate_conflicts:
        non_conflicting_groups = LR.build_non_conflicting_groups(conflicts)
        for group_sources in non_conflicting_groups:
            group_chunks = [c for c in merge_by_source if c["source"] in group_sources]
            context, source_chunks = build_context(group_chunks)

            attention_pairs = [[c[0], c[1]] for c in conflicts if c[0] in source_chunks or c[1] in source_chunks]

            answer = LLM.generate_answer([msg.dict() for msg in req.chat], question, context, attention="")
            answers.append(ChatAnswer(
                role="assistant",
                message=answer,
                files_used=list(source_chunks),
                attention=attention_pairs
            ))
    else:
        attention_pairs = [[c[0], c[1]] for c in conflicts] if conflicts else []

        context, source_chunks = build_context(merge_by_source)
        answer = LLM.generate_answer([msg.dict() for msg in req.chat], question, context, attention="")
        answers.append(ChatAnswer(
            role="assistant",
            message=answer,
            files_used=list(source_chunks),
            attention=attention_pairs
        ))

    llm_time = time.time() - llm_time

    total_time = time.time() - start_total
    print(f"Поиска чанков и контекста(RAG + BM25) время:         {search_chunk_with_context:.1f} сек")
    print(f"{len(answers)} LLM генераций по времи:                {llm_time:.1f} сек")
    print(f"Общее время:                                         {total_time:.1f} сек")

    response_data = ChatAnswerResponse(chat=answers)
    return response_data