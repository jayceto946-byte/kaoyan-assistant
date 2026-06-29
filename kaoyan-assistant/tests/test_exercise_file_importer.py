import io
import zipfile

import fitz
from fastapi.testclient import TestClient

from backend.main import app
from memory.exercise_file_importer import extract_exercise_text


def _make_docx(path, text: str):
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
  <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
</w:body></w:document>'''
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "")
        zf.writestr("word/document.xml", document.encode("utf-8"))


def test_extract_docx_text(tmp_path):
    path = tmp_path / "paper.docx"
    _make_docx(path, "1. 求函数 x^2 的导数。")
    extracted = extract_exercise_text(path)
    assert extracted.file_type == "docx"
    assert "导数" in extracted.text


def test_extract_pdf_text(tmp_path):
    path = tmp_path / "paper.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "1. Calculate linear programming optimum.")
    doc.save(path)
    doc.close()
    extracted = extract_exercise_text(path)
    assert extracted.file_type == "pdf"
    assert extracted.page_count == 1
    assert extracted.text_pages == 1
    assert "linear programming" in extracted.text


def test_upload_analyze_docx():
    buf = io.BytesIO()
    document = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
  <w:p><w:r><w:t>1. 求线性规划最优解。</w:t></w:r></w:p>
  <w:p><w:r><w:t>2. 判断：矩阵可逆当且仅当行列式不为 0。</w:t></w:r></w:p>
</w:body></w:document>'''
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "")
        zf.writestr("word/document.xml", document.encode("utf-8"))
    buf.seek(0)

    client = TestClient(app)
    res = client.post(
        "/api/exercises/upload-analyze?book_name=优化设计",
        data={"source": "docx测试", "subject": "优化设计"},
        files={"file": ("paper.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    ).json()
    assert res["success"] is True
    assert res["summary"]["total"] == 2
    assert res["extract"]["file_type"] == "docx"