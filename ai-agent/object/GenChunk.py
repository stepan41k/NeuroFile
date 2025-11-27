import hashlib
from collections import defaultdict


# ============================================================
#           ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def add_source_and_id(chanks, source):
    for id in range(len(chanks)):
        chanks[id]["source"] = source
        chanks[id]["chunkID"] = id
    return chanks

def merge_chunks_by_source(chunks):
    grouped = defaultdict(lambda: {"chunkIDs": [], "texts": []})

    for ch in chunks:
        source = ch["source"]
        grouped[source]["chunkIDs"].extend(ch.get("chunkID", []))
        grouped[source]["texts"].extend(ch.get("text", []))

    # Превращаем в список и сортируем по source
    result = []
    for source, data in grouped.items():
        result.append({
            "source": source,
            "chunkIDs": data["chunkIDs"],
            "texts": data["texts"]
        })

    result.sort(key=lambda x: x["source"])
    return result

def tokenize_len(text: str) -> int:
    """Простейший токенайзер: считает слова."""
    return len(text.split())


def hash_text(text: str) -> str:
    """MD5-хэш текста — чтобы помечать таблицы."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def convert_table_to_text(table):
    """
    Преобразует таблицу (list[list[str]]) в текст формата:
    | A | B | C |
    """
    lines = []
    for row in table:
        line = "| " + " | ".join(str(c) for c in row) + " |"
        lines.append(line)
    return "\n".join(lines)


# ============================================================
#      МЯГКОЕ ДЕЛЕНИЕ СЛИШКОМ БОЛЬШОГО ЛОГИЧЕСКОГО БЛОКА
# ============================================================

def split_block_soft(block, min_size, max_size):
    """Режет слишком большой логический блок по словам."""
    words = block.split()
    parts = []
    cur = []
    cur_len = 0

    for w in words:
        wl = tokenize_len(w)
        if cur_len + wl > max_size:
            parts.append(" ".join(cur))
            cur = [w]
            cur_len = wl
        else:
            cur.append(w)
            cur_len += wl

    if cur:
        parts.append(" ".join(cur))

    return parts


# ============================================================
#             ЛОГИЧЕСКОЕ ДЕЛЕНИЕ ТАБЛИЦЫ
# ============================================================

def split_table_logically(table_text, min_size, max_size):
    """
    Делит таблицу логически корректно:
    - строки с пустой первой ячейкой считаются продолжением предыдущей
    - блоки не рвутся
    - слишком большие блоки мягко режутся
    """

    lines = table_text.split("\n")

    blocks = []
    current_block = []

    def flush_block():
        nonlocal current_block
        if current_block:
            blocks.append("\n".join(current_block))
            current_block = []

    for line in lines:
        parts = [p.strip() for p in line.split("|")]

        first_cell = parts[1] if len(parts) > 1 else ""

        if not current_block:
            current_block.append(line)
            continue

        if first_cell == "":
            current_block.append(line)
        else:
            flush_block()
            current_block.append(line)

    flush_block()

    # собираем чанки
    result = []
    cur = []
    cur_len = 0

    def flush_chunk():
        nonlocal cur, cur_len
        if cur:
            result.append("\n".join(cur))
            cur = []
            cur_len = 0

    for block in blocks:
        bsize = tokenize_len(block)

        # если блок огромный — мягко режем
        if bsize > max_size:
            for small in split_block_soft(block, min_size, max_size):
                ssize = tokenize_len(small)
                if cur_len + ssize > max_size:
                    flush_chunk()
                cur.append(small)
                cur_len += ssize
            continue

        # обычный случай
        if cur_len + bsize > max_size:
            flush_chunk()

        cur.append(block)
        cur_len += bsize

    flush_chunk()
    return result


# ============================================================
#         ДЕЛЕНИЕ ОГРОМНОГО ТЕКСТА НА ЧАНКИ
# ============================================================

def split_text_by_max_size(text, min_size, max_size, strict=True):
    """
    Делит текст по словам так, чтобы каждый чанк ≤ max_size.
    """
    words = text.split()
    chunks = []
    cur = []
    cur_len = 0

    for w in words:
        wl = 1
        if cur_len + wl > max_size:
            chunks.append(" ".join(cur))
            cur = [w]
            cur_len = wl
        else:
            cur.append(w)
            cur_len += wl

    if cur:
        chunks.append(" ".join(cur))

    return chunks


# ============================================================
#                ОСНОВНАЯ ФУНКЦИЯ CHUNKING
# ============================================================

def normalize_pre_chunks(pre_chunks, min_size=50, max_size=200, strict=True):
    """
    Объединяет текст, режет большие блоки,
    логически режет таблицы, формирует конечные чанки.
    """

    result_chunks = []
    current_text = []
    current_tables = []
    current_len = 0

    def flush_chunk():
        nonlocal current_text, current_len, current_tables
        if current_text:
            result_chunks.append({
                "text": "\n\n".join(current_text),
                "chunkSize": current_len,
                "tables": current_tables.copy()
            })
            current_text = []
            current_tables = []
            current_len = 0

    # ---------------------------
    # 1. основной цикл
    # ---------------------------
    for item in pre_chunks:

        # ======================================
        # TEXT
        # ======================================
        if item["type"] == "text":
            text = item["content"]
            t_size = tokenize_len(text)

            # если большой текст — режем
            if t_size > max_size:
                pieces = split_text_by_max_size(text, min_size, max_size, strict)

                for part in pieces:
                    psize = tokenize_len(part)
                    if current_len + psize > max_size:
                        flush_chunk()
                    current_text.append(part)
                    current_len += psize
                continue

            # обычный текст
            if current_len + t_size > max_size:
                flush_chunk()

            current_text.append(text)
            current_len += t_size
            continue

        # ======================================
        # TABLE
        # ======================================
        elif item["type"] == "table":
            table_text = convert_table_to_text(item["content"])
            table_parts = split_table_logically(table_text, min_size, max_size)

            for part in table_parts:
                part_size = tokenize_len(part)
                part_hash = hash_text(part)

                if current_len + part_size > max_size:
                    flush_chunk()

                current_text.append(part)
                current_tables.append(part_hash)
                current_len += part_size

            continue

    flush_chunk()

    # ======================================
    # Финальное объединение маленьких чанков
    # ======================================
    final = []
    buffer = None

    for ch in result_chunks:
        if ch["chunkSize"] < min_size:
            if buffer is None:
                buffer = ch
            else:
                merged = {
                    "text": buffer["text"] + "\n\n" + ch["text"],
                    "chunkSize": buffer["chunkSize"] + ch["chunkSize"],
                    "tables": buffer["tables"] + ch["tables"]
                }
                buffer = merged
        else:
            if buffer:
                if buffer["chunkSize"] + ch["chunkSize"] <= max_size:
                    merged = {
                        "text": buffer["text"] + "\n\n" + ch["text"],
                        "chunkSize": buffer["chunkSize"] + ch["chunkSize"],
                        "tables": buffer["tables"] + ch["tables"]
                    }
                    final.append(merged)
                else:
                    final.append(buffer)
                    final.append(ch)
                buffer = None
            else:
                final.append(ch)

    if buffer:
        final.append(buffer)

    return final
