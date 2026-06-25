import fitz
from PIL import Image, ImageOps
import numpy as np
import logging
import io
from typing import Union
import pytesseract
import streamlit as st

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

TESSERACT_CONFIG = r'--oem 3 --psm 6 -l fra+eng'
TESSERACT_MIN_CHARS = 50

# Seuil : si une page contient plus de N caractères en texte natif,
# on n'utilise pas l'OCR pour cette page
NATIVE_TEXT_MIN_CHARS = 100


@st.cache_resource
def get_reader():
    import easyocr
    import torch
    gpu_available = torch.cuda.is_available()
    if not gpu_available:
        logging.warning("GPU non disponible — EasyOCR fonctionnera en CPU (fallback uniquement)")
    logging.info("Initialisation EasyOCR...")
    return easyocr.Reader(['en', 'fr'], gpu=gpu_available)


def _preprocess_image(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    img = ImageOps.autocontrast(img)
    return img


def _easyocr_extract(img: Image.Image) -> str:
    reader = get_reader()
    img_preprocessed = _preprocess_image(img)
    img_array = np.array(img_preprocessed)
    result = reader.readtext(img_array, detail=1)
    return "\n".join(item[1] for item in result)


def extract_text_from_image(image_path: Union[str, Image.Image]) -> str:
    """Extrait le texte d'une image via Tesseract (+ fallback EasyOCR)."""
    try:
        if isinstance(image_path, Image.Image):
            img = image_path
        else:
            img = Image.open(image_path)

        img_preprocessed = _preprocess_image(img)

        try:
            text = pytesseract.image_to_string(img_preprocessed, config=TESSERACT_CONFIG)
            if len(text.strip()) >= TESSERACT_MIN_CHARS:
                logging.info(f"Tesseract OK — {len(text.strip())} caractères extraits")
                return text
            logging.info(f"Tesseract insuffisant ({len(text.strip())} chars) — fallback EasyOCR")
        except Exception as e:
            logging.warning(f"Tesseract échoué ({e}) — fallback EasyOCR")

        text = _easyocr_extract(img)
        logging.info(f"EasyOCR — {len(text.strip())} caractères extraits")
        return text

    except Exception as e:
        logging.exception("Erreur OCR image")
        raise


def _extract_native_text_from_page(page) -> str:
    """
    Extrait le texte natif d'une page PDF via PyMuPDF.
    Retourne une chaîne vide si la page ne contient pas de texte natif.
    """
    # "dict" layout préserve mieux l'ordre de lecture tabulaire
    blocks = page.get_text("blocks", sort=True)
    lines = []
    for block in blocks:
        # block = (x0, y0, x1, y1, text, block_no, block_type)
        # block_type 0 = texte, 1 = image
        if block[6] == 0:
            text = block[4].strip()
            if text:
                lines.append(text)
    return "\n".join(lines)


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extrait le texte d'un PDF.

    Stratégie par page :
      1. Texte natif PyMuPDF (rapide, précis pour PDFs non scannés)
         → utilisé si >= NATIVE_TEXT_MIN_CHARS caractères trouvés
      2. OCR Tesseract sur l'image de la page (PDFs scannés)
         → utilisé si Tesseract donne >= TESSERACT_MIN_CHARS
      3. Fallback EasyOCR si Tesseract insuffisant
    """
    try:
        doc = fitz.open(pdf_path)
        logging.info(f"PDF : {pdf_path} ({len(doc)} pages)")
        full_text = []

        for page_num in range(len(doc)):
            logging.info(f"Traitement page {page_num + 1}/{len(doc)}")
            page = doc.load_page(page_num)

            # ── Étape 1 : texte natif ───────────────────────────────────────
            native_text = _extract_native_text_from_page(page)
            if len(native_text.strip()) >= NATIVE_TEXT_MIN_CHARS:
                logging.info(
                    f"Page {page_num + 1} — texte natif extrait "
                    f"({len(native_text)} chars) — OCR ignoré"
                )
                full_text.append(native_text)
                continue

            # ── Étape 2 : OCR si texte natif insuffisant ────────────────────
            logging.info(
                f"Page {page_num + 1} — texte natif insuffisant "
                f"({len(native_text.strip())} chars) — passage en OCR"
            )
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            page_text = extract_text_from_image(img)
            logging.info(f"Page {page_num + 1} — OCR : {len(page_text)} caractères")
            full_text.append(page_text)

        doc.close()
        final_text = "\n".join(full_text)
        logging.info(f"Extraction terminée — {len(final_text)} caractères au total")
        return final_text

    except Exception as e:
        logging.exception("Erreur extraction PDF")
        raise