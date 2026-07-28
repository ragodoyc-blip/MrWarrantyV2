import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import requests
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError

from azure.storage.blob import (
    BlobServiceClient,
    BlobSasPermissions,
    generate_blob_sas,
)
from datetime import datetime, timedelta

from config import (
    AZURE_STORAGE_CONNECTION_STRING,
    AZURE_STORAGE_CONTAINER,
    POPPLER_PATH,
)
from logger import log
from Procesador_Mintral import Ejecutar_Mistral_diccionario
from API_SQIS import URL_Adjuntos


# ── Azure Blob Storage ──────────────────────────────────────
_blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
_container_client = _blob_service_client.get_container_client(AZURE_STORAGE_CONTAINER)


def generar_sas(blob_name: str) -> str:
    sas_token = generate_blob_sas(
        account_name=_blob_service_client.account_name,
        container_name=AZURE_STORAGE_CONTAINER,
        blob_name=blob_name,
        account_key=_blob_service_client.credential.account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(minutes=30),
    )
    blob_client = _container_client.get_blob_client(blob_name)
    return f"{blob_client.url}?{sas_token}"


def subir_imagenes_blob(document_folder: str, local_folder: str) -> list[str]:
    """Sube todas las imágenes al Blob y retorna URLs SAS válidas por 30 minutos."""
    urls = []
    for filename in sorted(os.listdir(local_folder)):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):
            local_path = os.path.join(local_folder, filename)
            blob_name = f"{document_folder}/{filename}"
            blob_client = _container_client.get_blob_client(blob_name)

            with open(local_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)

            sas_url = generar_sas(blob_name)
            urls.append(sas_url)
    return urls


def reconstruir_urls_existentes(download_path: str) -> dict[str, list[str]]:
    documentos_urls = {}
    id_claim = download_path.split("/")[-1]

    for carpeta in sorted(os.listdir(download_path)):
        carpeta_path = os.path.join(download_path, carpeta)
        if not os.path.isdir(carpeta_path):
            continue

        urls = []
        for filename in sorted(os.listdir(carpeta_path)):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                blob_name = f"{id_claim}/{carpeta}/{filename}"
                sas_url = generar_sas(blob_name)
                urls.append(sas_url)

        documentos_urls[carpeta] = urls
    return documentos_urls


def cerrar_edge() -> None:
    try:
        subprocess.run("taskkill /F /IM msedge.exe /T", shell=True)
        subprocess.run("taskkill /F /IM msedgedriver.exe /T", shell=True)
        time.sleep(2)
    except Exception as e:
        log.warning("No se pudieron cerrar procesos de Edge: %s", e)


def pdf_to_imagenes(pdf_file_path: str, output_folder: str) -> list[str]:
    if not os.path.exists(pdf_file_path):
        raise FileNotFoundError(f"El archivo PDF no existe: {pdf_file_path}")

    try:
        log.info("Procesando archivo PDF: %s", pdf_file_path)
        pages = convert_from_path(pdf_file_path, dpi=200, poppler_path=POPPLER_PATH)
        generated_files = []
        base_name = os.path.splitext(os.path.basename(pdf_file_path))[0]

        for idx, page in enumerate(pages, start=1):
            out_path = os.path.join(output_folder, f"{base_name}_page_{idx:02}.png")
            page.save(out_path, "PNG")
            generated_files.append(out_path)

        return generated_files

    except PDFPageCountError as e:
        log.error("Error al contar páginas del PDF %s: %s", pdf_file_path, e)
        raise ValueError(f"No se pudo procesar el archivo PDF: {pdf_file_path}. Error: {e}")
    except Exception as e:
        log.error("Error inesperado al procesar PDF %s: %s", pdf_file_path, e)
        raise ValueError(f"Error inesperado al procesar el archivo PDF: {pdf_file_path}. Error: {e}")


def AdjuntosSQIS(ID_CLAIM: str) -> dict[str, list[str]]:
    """Descarga los adjuntos asociados a un caso y retorna URLs SAS por documento."""
    download_path = str(Path("AdjuntosSQIS") / ID_CLAIM)

    if os.path.exists(download_path) and len(os.listdir(download_path)) > 0:
        log.info("Carpeta ya existe para %s, saltando descarga...", ID_CLAIM)
        return reconstruir_urls_existentes(download_path)

    os.makedirs(download_path, exist_ok=True)

    documentos_urls = URL_Adjuntos(ID_CLAIM)
    if documentos_urls is None:
        log.warning("No se encontraron adjuntos para %s", ID_CLAIM)
        return {}

    for item in documentos_urls:
        filename = item.get("filename")
        url = item.get("url")
        log.info("Descargando: %s", filename)

        doc_folder = os.path.splitext(filename)[0]
        local_doc_path = os.path.join(download_path, doc_folder)
        os.makedirs(local_doc_path, exist_ok=True)

        try:
            original_filename = os.path.basename(url.split("?")[0])
            _, file_extension = os.path.splitext(original_filename)
            base_name = original_filename[:20] if len(original_filename) > 20 else original_filename
            original_filename = f"{base_name}{file_extension}"

            local_file = os.path.join(local_doc_path, original_filename)

            r = requests.get(url)
            with open(local_file, "wb") as f:
                f.write(r.content)

            if original_filename.lower().endswith(".pdf"):
                try:
                    sanitized_file_path = sanitize_filename(local_file)
                    pdf_to_imagenes(os.path.normpath(sanitized_file_path), local_doc_path)
                    os.remove(local_file)
                except Exception as e:
                    log.error("Error al procesar PDF %s: %s", local_file, e)

        except Exception as e:
            log.error("Error al descargar %s: %s", url, e)

    urls_sas = {}
    for doc_folder in os.listdir(download_path):
        local_doc_path = os.path.join(download_path, doc_folder)
        if os.path.isdir(local_doc_path):
            urls_sas[doc_folder] = subir_imagenes_blob(f"{ID_CLAIM}/{doc_folder}", local_doc_path)

    return urls_sas


def sanitize_filename(file_path: str, max_length: int = 20) -> str:
    """Limpia el nombre del archivo de caracteres especiales y limita su longitud."""
    directory, filename = os.path.split(file_path)
    name, ext = os.path.splitext(filename)

    replacements = {"ñ": "n", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"}
    for char, replacement in replacements.items():
        name = name.replace(char, replacement)

    sanitized_name = re.sub(r"[^a-zA-Z0-9_\-]", "", name.replace(" ", "_"))

    if not sanitized_name:
        sanitized_name = "archivo"

    sanitized_name = sanitized_name[:max_length]
    sanitized_filename = f"{sanitized_name}{ext}"
    sanitized_path = os.path.join(directory, sanitized_filename)

    if file_path != sanitized_path:
        shutil.move(file_path, sanitized_path)

    return sanitized_path
