import hashlib
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize

nltk.download("punkt", quiet=True)

def add_source_and_id(chanks, source):
    for id in range(len(chanks)):
        chanks[id]["source"] = source
        chanks[id]["chunkID"] = id
    return chanks


def hash_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def tokenize_len(text: str) -> int:
    """Минимальная токенизация — по словам."""
    return len(word_tokenize(text))


def split_text_into_chunks(text, min_size, max_size):
    """
    Разделение обычного текста на чанки (только текст, не таблица).
    Чанки собираются последовательно из предложений.
    """
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
            # Чанк готов
            if current_len >= min_size:
                chunks.append(" ".join(current))
                current = [sent]
                current_len = sent_len
            else:
                # Чанк маленький — добавляем всё что есть + новое предложение
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


def try_split_table(table_text, min_size, max_size):
    """
    Попытка разделить таблицу *как обычный текст*.
    Разрешено делить таблицу только если получается 2 чанка,
    и оба удовлетворяют min_size ≤ size ≤ max_size.
    """
    parts = split_text_into_chunks(table_text, min_size, max_size)

    if len(parts) == 2:
        ok = True
        for p in parts:
            size = tokenize_len(p)
            if not (min_size <= size <= max_size):
                ok = False
                break
        if ok:
            return parts

    return [table_text]  # НЕ делим


def normalize_pre_chank(pre_chunks, min_size, max_size):
    """
    Главная функция нормализации всего набора pre_chunks.
    Реализует:
    - сбор текстов по min/max
    - обработку таблиц по особым правилам
    - формирование итоговых структур с hash, text, hashTable
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
            text = item["content"]
            sentences = split_text_into_chunks(text, min_size, max_size)

            for chunk in sentences:
                size = tokenize_len(chunk)

                # Если чанк укладывается — просто пушим
                if current_len + size <= max_size:
                    current_text.append(chunk)
                    current_len += size

                else:
                    # Закрываем текущий
                    if current_len >= min_size:
                        flush_chunk()
                        current_text.append(chunk)
                        current_len = size
                    else:
                        # Чанк маленький — просто добавляем
                        current_text.append(chunk)
                        current_len += size

        elif item["type"] == "table":
            table_text = convert_table_to_text(item["content"])
            table_size = tokenize_len(table_text)
            table_hash = hash_text(table_text)

            # 1) если предыдущий текстовый чанк < min_size — добавляем таблицу в него
            if 0 < current_len < min_size:
                current_text.append(table_text)
                current_len += table_size
                current_tables.append(table_hash)
                continue

            # 2) если (контекст+таблица) > max_size или таблица > max_size — пробуем делить
            if current_len + table_size > max_size or table_size > max_size:
                split_res = try_split_table(table_text, min_size, max_size)

                if len(split_res) == 2:  # Удалось разделить корректно
                    # Закрываем текущий чанк
                    flush_chunk()

                    # Создаём два отдельных чанка из таблицы
                    for part in split_res:
                        part_hash = hash_text(part)
                        result.append({
                            "chunkHash": part_hash,
                            "chunkSize": tokenize_len(part),
                            "text": part,
                            "hashTable": [part_hash],
                        })
                    continue

                else:
                    # НЕ делим, просто закрываем текущий и кладём большой чанк
                    flush_chunk()

                    result.append({
                        "chunkHash": table_hash,
                        "chunkSize": table_size,
                        "text": table_text,
                        "hashTable": [table_hash]
                    })
                    continue

            # Иначе таблица умещается
            current_text.append(table_text)
            current_len += table_size
            current_tables.append(table_hash)

    # Финальный сброс
    flush_chunk()

    return result
