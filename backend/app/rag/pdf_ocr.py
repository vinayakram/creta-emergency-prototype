from pdf2image import convert_from_path
import pytesseract


def extract_pages_ocr(
    pdf_path: str,
    start_page: int,
    end_page: int,
) -> str:
    """
    OCR extract text from PDF pages (1-based, inclusive).
    """
    images = convert_from_path(
        pdf_path,
        first_page=start_page,
        last_page=end_page,
        dpi=300,
    )

    text = ""
    for img in images:
        page_text = pytesseract.image_to_string(img, lang="eng")
        text += page_text + "\n"

    return text
