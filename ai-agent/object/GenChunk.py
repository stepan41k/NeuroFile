import hashlib
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

def add_source_and_id(chanks, source):
    for id in range(len(chanks)):
        chanks[id]["source"] = source
        chanks[id]["chunkID"] = id
    return chanks

nltk.download("punkt", quiet=True)

def hash_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()

def tokenize_len(text: str) -> int:
    """Минимальная токенизация — по словам."""
    return len(word_tokenize(text))

def split_text_into_chunks(text, min_size, max_size):
    sentences = sent_tokenize(text)
    chunks = []
    current = []
    current_len = 0

    for sent in sentences:
        sent_len = tokenize_len(sent)
        if current_len + sent_len <= max_size:
            current.append(sent)
            current_len += sent_len
        else:
            if current_len >= min_size:
                chunks.append(" ".join(current))
                current = [sent]
                current_len = sent_len
            else:
                current.append(sent)
                current_len += sent_len

    if current:
        chunks.append(" ".join(current))
    return chunks

def convert_table_to_text(table):
    """Преобразуем таблицу в плоский текст (строки подряд)."""
    if isinstance(table, str):
        return table
    if isinstance(table, list):
        return "\n".join(["\t".join(map(str, row)) for row in table])
    return str(table)

def split_large_table(table_text, min_size, max_size):
    """
    Разделяем таблицу на несколько чанков по строкам.
    Возвращаем список текстовых чанков.
    """
    lines = table_text.split("\n")
    chunks = []
    current = []
    current_len = 0

    for line in lines:
        line_len = tokenize_len(line)
        if current_len + line_len > max_size:
            if current:
                chunks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunks.append("\n".join(current))
    return chunks


def normalize_pre_chunks(pre_chunks, min_size, max_size):
    """
    Нормализация pre_chunks в равномерные чанки.
    Возвращает массив словарей:
    {"chunkHash": str, "chunkSize": int, "text": str, "hashTable": [str]}
    """
    result = []
    current_text = []
    current_tables = []
    current_len = 0

    def flush_chunk():
        nonlocal current_text, current_tables, current_len
        if not current_text:
            return
        text = " ".join(current_text).strip()
        if not text:
            return
        result.append({
            "chunkHash": hash_text(text),
            "chunkSize": tokenize_len(text),
            "text": text,
            "hashTable": current_tables.copy()
        })
        current_text = []
        current_tables = []
        current_len = 0

    for item in pre_chunks:
        if item["type"] == "text":
            text_chunks = split_text_into_chunks(item["content"], min_size, max_size)
            for chunk in text_chunks:
                size = tokenize_len(chunk)
                if current_len + size > max_size:
                    if current_len >= min_size:
                        flush_chunk()
                    # если текущий маленький, добавляем в него
                current_text.append(chunk)
                current_len += size

        elif item["type"] == "table":
            table_text = convert_table_to_text(item["content"])
            table_size = tokenize_len(table_text)
            table_hash = hash_text(table_text)

            # если текущий чанк маленький — добавляем таблицу туда
            if 0 < current_len < min_size:
                current_text.append(table_text)
                current_len += table_size
                current_tables.append(table_hash)
                continue

            # если таблица или чанк+таблица превышает max_size — пробуем делить
            if table_size > max_size or current_len + table_size > max_size:
                split_res = try_split_table(table_text, min_size, max_size)
                if len(split_res) == 2:
                    flush_chunk()
                    for part in split_res:
                        part_hash = hash_text(part)
                        result.append({
                            "chunkHash": part_hash,
                            "chunkSize": tokenize_len(part),
                            "text": part,
                            "hashTable": [part_hash]
                        })
                    continue
                else:
                    flush_chunk()
                    result.append({
                        "chunkHash": table_hash,
                        "chunkSize": table_size,
                        "text": table_text,
                        "hashTable": [table_hash]
                    })
                    continue

            # иначе таблица умещается в текущий чанк
            current_text.append(table_text)
            current_len += table_size
            current_tables.append(table_hash)

    flush_chunk()
    return result