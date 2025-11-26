import subprocess
import os
import tempfile
from docx import Document
from object.LoadDOCX import parse_docx

def parse_doc_or_rtf(file_path):
    """
    Конвертирует .doc или .rtf во временный .docx через LibreOffice,
    парсит через python-docx и возвращает структурированные блоки.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        tmp_docx = os.path.join(tmpdir, filename + ".docx")

        # Конвертация через LibreOffice
        if ext in [".doc", ".rtf"]:
            subprocess.run([
                "soffice", "--headless", "--convert-to", "docx", file_path, "--outdir", tmpdir
            ], check=True)
            # Путь к сконвертированному файлу
            tmp_docx = os.path.join(tmpdir, filename.replace(ext, ".docx"))

        # Парсинг docx
        blocks = parse_docx(tmp_docx)

        return blocks