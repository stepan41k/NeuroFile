from docx import Document
import re

def clean_text_blocks_docs(blocks):
    cleaned = []
    for b in blocks:
        if b["type"] == "text":
            text = b["content"].strip()
            if text == "" or re.fullmatch(r'[-_]{3,}', text):
                continue  # удаляем пустые строки
            cleaned.append({
                "type": "text",
                "content": text
            })
        else:
            cleaned.append(b)  # таблицы оставляем как есть
    return cleaned

def can_merge(prev: str, next_: str) -> bool:
    prev = prev.strip()
    next_ = next_.strip()

    # Если что-то пустое — не объединяем
    if not prev or not next_:
        return False

    # --- 1) ТЕКСТ ВСЕ ЗАГЛАВНЫЙ (заголовок) ---
    # Если оба заглавные и не очень длинные → можно объединить (части заголовка)
    if prev.isupper() and next_.isupper():
        return True

    # --- 2) Конец предложения на ',' или ':'→ НЕ объединяем ---
    if prev.endswith((',', ':')):
        return True

    # --- 2) Обычный конец предложения → НЕ объединяем ---
    if prev.endswith(('.', '!', '?')):
        return False

    # --- 3) Если предыдущий блок длинный текст без точки → возможно перенос строки → объединяем ---
    if len(prev) > 40 and not prev.endswith('.'):
        return True

    # --- 4) Если предыдущий заканчивается словом (не знаками) и следующее начинается со строчной буквы → объединяем ---
    if prev[-1].isalnum() and next_[0].islower():
        return True

    return False


def merge_text_blocks(blocks):
    result = []

    for b in blocks:
        if b["type"] == "text":
            text = b["content"].strip()
            if not text:
                result.append(b)
                continue

            if (result and
                result[-1]["type"] == "text" and
                can_merge(result[-1]["content"], text)):

                result[-1]["content"] += " " + text
            else:
                result.append({"type": "text", "content": text})

        else:
            result.append(b)  # таблицы, изображения, всё оставляем
    return result

def parse_docx(file_path):
    doc = Document(file_path)
    blocks = []

    for element in doc.element.body:
        if element.tag.endswith('p'):
            # Абзац
            paragraph = element
            text = paragraph.text if paragraph.text else ""
            # text = fix_encoding(text)
            blocks.append({
                "type": "text",
                "content": text,
            })
        elif element.tag.endswith('tbl'):
            # Таблица
            table = element
            rows = []
            for row in table.findall(".//w:tr", table.nsmap):
                cells = []
                for cell in row.findall(".//w:tc", table.nsmap):
                    cell_text = ""
                    for p in cell.findall(".//w:p", table.nsmap):
                        # cell_text += fix_encoding(p.text or "")
                        cell_text += p.text or ""
                    cells.append(cell_text)
                rows.append(cells)

            blocks.append({
                "type": "table",
                "content": rows,   # list[list[str]]
            })

    # Убираем пустые сроки
    blocks = clean_text_blocks_docs(blocks)
    # Объединяем строки по структуре
    blocks = merge_text_blocks(blocks)
    return blocks
