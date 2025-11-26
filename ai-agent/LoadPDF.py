import fitz
import re
import io
from PIL import Image
import pytesseract


def clean_text(text: str):
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def ocr_image(pix, table_mode=False):
    """OCR изображения.
    table_mode=True → лучше для таблиц.
    """
    img_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_bytes))

    config = "--psm 6" if table_mode else "--psm 3"
    text = pytesseract.image_to_string(img, lang="rus+eng", config=config)

    return clean_text(text)


def detect_table_candidates(page, min_width=80, min_height=40):
    """Выделяем блоки-кандидаты под таблицы в обычном PDF (не сканах).
    Используем layout-блоки PDF.
    """
    tables = []
    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no)
    for b in blocks:
        x0, y0, x1, y1, txt, _ = b
        w, h = x1 - x0, y1 - y0
        txt_clean = clean_text(txt)

        if w > min_width and h > min_height:
            # Эвристика: много символов-разделителей → таблица
            if re.search(r"[|·─—\-]{2,}", txt) or re.search(r"\b\d+[,.;]\d+\b", txt):
                tables.append({
                    "bbox": (x0, y0, x1, y1),
                    "content": txt_clean
                })

    return tables


def extract_table_ocr(page):
    """OCR таблиц со страницы (сканированный PDF).
    Выделяем 2-4 крупных блока, делаем OCR в табличном режиме.
    """
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_bytes))

    width, height = img.size
    table_candidates = []

    # Простая сегментация: делим страницу на 4 зоны и ищем в них таблицы
    regions = [
        (0, 0, width, height//2),
        (0, height//2, width, height)
    ]

    for (x0, y0, x1, y1) in regions:
        crop = img.crop((x0, y0, x1, y1))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        crop_pix = fitz.Pixmap(fitz.csRGB, fitz.open("png", buf.getvalue()))
        text = ocr_image(crop_pix, table_mode=True)

        # Эвристика: если похоже на таблицу
        if re.search(r"[|·─—\-]{2,}", text) or len(text.split()) > 20:
            table_candidates.append({
                "bbox": (x0, y0, x1, y1),
                "content": text
            })

    return table_candidates


def parse_pdf(path):
    doc = fitz.open(path)
    result = []

    for page in doc:
        text_regular = clean_text(page.get_text("text"))

        # ===== 1. Страница с обычным текстом =====
        if len(text_regular.replace(" ", "")) > 10:

            # — таблицы из обычного PDF (если есть)
            table_blocks = detect_table_candidates(page)

            blocks = []
            # Обычный текст — общий блок
            if text_regular:
                blocks.append({
                    "type": "text",
                    "bbox": (0, 0, page.rect.width, page.rect.height),
                    "content": text_regular,
                    "source": "pdf_text"
                })

            # Таблицы добавляем отдельно
            for t in table_blocks:
                blocks.append({
                    "type": "table",
                    "bbox": t["bbox"],
                    "content": t["content"],
                    "source": "pdf_table"
                })

            # сортировка по Y-координате (по порядку появления)
            blocks.sort(key=lambda b: b["bbox"][1])
            result.extend(blocks)

        else:
            # ===== 2. Скан → OCR текста =====
            pix = page.get_pixmap(dpi=300)
            ocr_txt = ocr_image(pix)

            # OCR текста
            if ocr_txt:
                result.append({
                    "type": "text",
                    "bbox": (0, 0, page.rect.width, page.rect.height),
                    "content": ocr_txt,
                    "source": "pdf_ocr"
                })

            # OCR таблиц
            tables_ocr = extract_table_ocr(page)
            for t in tables_ocr:
                result.append({
                    "type": "table",
                    "bbox": t["bbox"],
                    "content": t["content"],
                    "source": "ocr_table"
                })

    doc.close()

    # финальная очистка
    final = []
    for b in result:
        c = clean_text(b["content"])
        if c:
            b["content"] = c
            final.append(b)

    return final
