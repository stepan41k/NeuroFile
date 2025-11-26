import fitz
import re
from PIL import Image
import pytesseract
import io

def clean_text_blocks_pdf(blocks):
    cleaned = []
    for b in blocks:
        text = b["content"].strip()
        if text:
            b["content"] = text
            cleaned.append(b)
    return cleaned

def ocr_image(pix):
    """OCR с изображения страницы PDF."""
    img_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_bytes))
    text = pytesseract.image_to_string(img, lang="rus+eng")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def parse_pdf(file_path):
    doc = fitz.open(file_path)
    blocks = []

    for page in doc:
        # 1) Пробуем извлечь текст обычным способом
        page_text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        text_clean = re.sub(r"\s+", " ", page_text.replace("\n", " ").replace("\t", " ")).strip()

        if text_clean and len(text_clean.replace(" ", "")) > 5:
            # Страница содержит реальный текст
            blocks.append({
                "type": "text",
                "content": text_clean,
                "source": "pdf_text"
            })
        else:
            # 2) Если текста нет → это скан → OCR
            pix = page.get_pixmap(dpi=300)
            ocr_text = ocr_image(pix)

            if ocr_text:
                blocks.append({
                    "type": "text",
                    "content": ocr_text,
                    "source": "pdf_ocr"
                })

    doc.close()
    return clean_text_blocks_pdf(blocks)