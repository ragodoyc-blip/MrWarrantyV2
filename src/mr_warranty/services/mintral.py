import base64
import os
import time

import requests

from mr_warranty.config.config import AZURE_MISTRAL_API_KEY, AZURE_MISTRAL_ENDPOINT
from mr_warranty.core.logger import log


def encode_pdf_to_base64(pdf_path: str) -> str | None:
    """Read a PDF file and encode it to base64."""
    try:
        with open(pdf_path, "rb") as pdf_file:
            return base64.b64encode(pdf_file.read()).decode("utf-8")
    except FileNotFoundError:
        log.error("PDF no encontrado: %s", pdf_path)
        return None
    except Exception as e:
        log.error("Error leyendo PDF %s: %s", pdf_path, e)
        return None


def process_pdf_with_mistral(pdf_path: str) -> dict | None:
    """Process a local PDF file using Mistral Document AI."""
    api_key = AZURE_MISTRAL_API_KEY
    if not api_key:
        log.error("AZURE_MISTRAL_API_KEY no configurada en el entorno")
        return None

    base64_content = encode_pdf_to_base64(pdf_path)
    if not base64_content:
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": "mistral-document-ai-2505",
        "document": {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{base64_content}",
        },
        "include_image_base64": True,
    }

    try:
        time.sleep(1)
        start_time = time.time()
        response = requests.post(AZURE_MISTRAL_ENDPOINT, headers=headers, json=payload)
        end_time = time.time()

        response.raise_for_status()
        result = response.json()

        log.info("Mistral procesó %s en %.1fs", pdf_path, end_time - start_time)
        return result

    except requests.exceptions.RequestException as e:
        log.error("Error en request Mistral para %s: %s", pdf_path, e)
        if hasattr(e, "response") and e.response is not None:
            log.error("Response status: %s, content: %s", e.response.status_code, e.response.text[:200])
        return None


def Ejecutar_Mistral_diccionario(pdf_path: str) -> dict | None:
    if not os.path.exists(pdf_path):
        pdf_files = [f for f in os.listdir(".") if f.endswith(".pdf")]
        if pdf_files:
            log.info("Usando primer PDF encontrado: %s", pdf_files[0])
            pdf_path = pdf_files[0]
        else:
            log.warning("No se encontraron archivos PDF")
            return None

    result = process_pdf_with_mistral(pdf_path)
    if result and "pages" in result and len(result["pages"]) > 0:
        log.info("Mistral procesó exitosamente: %s", pdf_path)
        return result

    log.warning("Mistral no devolvió resultados para %s", pdf_path)
    return result
