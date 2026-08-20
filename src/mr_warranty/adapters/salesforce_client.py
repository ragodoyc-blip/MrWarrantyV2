import json
import os
import re
import tempfile

import pandas as pd
import requests
from simple_salesforce import Salesforce

from mr_warranty.config.config import (
    SF_AUTH_URL,
    SF_CONSUMER_KEY,
    SF_CONSUMER_SECRET,
    SF_CREATEDON_FILTER,
    SF_PASSWORD,
    SF_SECURITY_TOKEN,
    SF_USERNAME,
    ALLOWED_DISTRIBUTORS,
)
from mr_warranty.core.logger import log

# Cache de conexión Salesforce
_sf_client: Salesforce | None = None


def connect_salesforce() -> Salesforce:
    """Retorna una conexión Salesforce reutilizable (singleton)."""
    global _sf_client
    if _sf_client is not None:
        return _sf_client

    payload = {
        "grant_type": "password",
        "client_id": SF_CONSUMER_KEY,
        "client_secret": SF_CONSUMER_SECRET,
        "username": SF_USERNAME,
        "password": SF_PASSWORD + SF_SECURITY_TOKEN,
    }

    response = requests.post(SF_AUTH_URL, data=payload)
    if response.status_code != 200:
        raise ConnectionError(f"Error al autenticar con Salesforce: {response.json()}")

    auth = response.json()
    _sf_client = Salesforce(instance_url=auth["instance_url"], session_id=auth["access_token"])
    log.info("Conexión Salesforce establecida correctamente")
    return _sf_client


def reclamos_pendientes() -> pd.DataFrame:
    """Obtiene los reclamos pendientes desde Salesforce."""
    sf = connect_salesforce()
    try:
        campos_claim = [
            "Id", "Name", "Status",
            "Servicing_Distributor__c", "CreatedDate", "Claim_country__c",
            "SubmittedDate__c",
        ]

        query_claim = f"SELECT {', '.join(campos_claim)} FROM Claim"
        data = sf.query_all(query_claim)

        df = pd.DataFrame(data["records"]).drop(columns="attributes", errors="ignore")
        df = df[df["CreatedDate"] >= SF_CREATEDON_FILTER]
        df = df[df["Servicing_Distributor__c"].isin(ALLOWED_DISTRIBUTORS)]
        return df

    except Exception as e:
        log.error("Error al obtener reclamos pendientes: %s", e)
        return pd.DataFrame()


def process_salesforce_data(name: str) -> dict:
    """Procesa datos de un reclamo específico desde Salesforce."""
    sf = connect_salesforce()

    campos_claim = [
        "Id", "TSINumber__c", "Name", "Status", "CreatedDate",
        "ClaimType", "Summary", "Total_Adjudicated_Amount__c",
        "Account__c", "AdditionalComments__c", "Cause__c",
        "Complaint__c", "Correction__c", "LaborApprovedAmount__c",
        "PartsRequestedAmount__c", "Product_Code__c", "QualityCategory__c",
        "Servicing_Distributor__c", "Field_Campaign__c",
        "LaborRequestedQuantity__c", "PartsRequestedQuantity__c",
        "Mileage__c", "Travel_Time__c", "Parts_Required__c",
        "SubmittedDate__c",
    ]

    # Parametrizado para evitar SOQL injection
    query_claim = f"SELECT {', '.join(campos_claim)} FROM Claim WHERE Name = %s"
    data = sf.query_all(query_claim % (f"'{name}'"))
    df = pd.DataFrame(data["records"]).drop(columns="attributes", errors="ignore")

    tsi_list = df["TSINumber__c"].dropna().unique().tolist()
    field_list = df["Field_Campaign__c"].dropna().unique().tolist()

    campos_case = [
        "Id", "Subject", "Description", "Phenomenon__c",
        "FailureDate__c", "MachineRepairCompletionDate__c",
        "MachineCommissionedDate__c", "TrackingDepartment__c",
        "CauseOfFailure__c", "TSI_Title__c", "Closed_Reason__c",
        "Resolution_Details__c",
    ]

    ids_filter = "', '".join(tsi_list)
    query_case = f"SELECT {', '.join(campos_case)} FROM Case WHERE Id IN ('{ids_filter}') LIMIT 200"

    data_case = sf.query_all(query_case)
    df_case = pd.DataFrame(data_case["records"]).drop(columns="attributes", errors="ignore")

    if len(field_list) > 0:
        campos_field = [
            "Name", "EndDate__c", "Labor_Limit_hours__c",
            "Description__c", "Mileage__c", "Travel_Time__c",
            "Parts_Required__c",
        ]

        ids_field_filter = "', '".join(field_list)
        query_field = f"SELECT {', '.join(campos_field)} FROM Custom_Campaign__c WHERE Name IN ('{ids_field_filter}') LIMIT 200"
        data_field = sf.query_all(query_field)
        df_field = pd.DataFrame(data_field["records"]).drop(columns="attributes", errors="ignore")

        df_merged = df.merge(df_case, left_on="TSINumber__c", right_on="Id", suffixes=("_claim", "_case"))
        df_merged = df_merged.merge(df_field, left_on="Field_Campaign__c", right_on="Name", suffixes=("", "_field"))
    else:
        df_merged = df.merge(df_case, left_on="TSINumber__c", right_on="Id", suffixes=("_claim", "_case"))

    return df_merged.to_dict(orient="records")[0]


def ClaimDetails() -> pd.DataFrame:
    sf = connect_salesforce()

    campos_claim = [
        "Name", "ChargeType", "ReplacementPart__c",
        "Part_Description__c", "Quantity__c", "ClaimedAmount", "Total_Amount__c",
    ]

    query_claim = f"SELECT {', '.join(campos_claim)} FROM ClaimCoveragePaymentDetail WHERE Name LIKE '001257%'"
    data = sf.query_all(query_claim)
    return pd.DataFrame(data["records"]).drop(columns="attributes", errors="ignore")


def obtener_chatter_case_dict(case_id: str) -> dict:
    """Obtiene los posts de chatter asociados a un Case."""
    sf = connect_salesforce()
    response = sf.restful(f"chatter/feeds/record/{case_id}/feed-elements", method="GET")

    elementos = response.get("elements", [])
    resultado = {"CaseId": case_id, "CantidadPosts": len(elementos), "Posts": []}

    for idx, el in enumerate(elementos, start=1):
        texto = "".join(
            seg.get("text", "")
            for seg in el.get("body", {}).get("messageSegments", [])
            if seg.get("type") == "Text"
        )

        comentarios = []
        for c in el.get("capabilities", {}).get("comments", {}).get("items", []):
            c_texto = "".join(
                seg.get("text", "")
                for seg in c.get("body", {}).get("messageSegments", [])
                if seg.get("type") == "Text"
            )
            comentarios.append({
                "Autor": c.get("actor", {}).get("name"),
                "Fecha": c.get("createdDate"),
                "Texto": c_texto,
            })

        resultado["Posts"].append({
            "PostNumber": idx,
            "FeedElementId": el.get("id"),
            "Tipo": el.get("feedElementType"),
            "Autor": el.get("actor", {}).get("name"),
            "Fecha": el.get("createdDate"),
            "Texto": texto,
            "Comentarios": comentarios,
        })

    return resultado


def listar_tablas() -> list | None:
    """Lista todas las tablas (objetos) disponibles en Salesforce."""
    sf = connect_salesforce()
    try:
        metadata = sf.describe()
        tablas = [obj["name"] for obj in metadata["sobjects"]]

        with open("tablas_salesforce.json", "w", encoding="utf-8") as f:
            json.dump(tablas, f, ensure_ascii=False, indent=4)

        log.info("Tablas de Salesforce exportadas a tablas_salesforce.json")
        return tablas

    except Exception as e:
        log.error("Error al listar tablas: %s", e)
        return None


def obtener_todos_los_campos(objeto: str) -> str | None:
    """Obtiene todos los campos de un objeto y construye una consulta SOQL."""
    sf = connect_salesforce()
    try:
        metadata = sf.__getattr__(objeto).describe()
        campos = [field["name"] for field in metadata["fields"]]
        return f"SELECT {', '.join(campos)} FROM {objeto}"
    except Exception as e:
        log.error("Error al obtener campos del objeto %s: %s", objeto, e)
        return None


def buscar_adjuntos_sf(entity_id: str) -> list[dict]:
    """Obtiene los archivos adjuntos (ContentDocument) de un registro (Claim o Case)."""
    sf = connect_salesforce()
    query = f"""
        SELECT ContentDocumentId
        FROM ContentDocumentLink 
        WHERE LinkedEntityId = '{entity_id}'
    """
    try:
        data = sf.query(query)
        adjuntos = []
        for record in data.get("records", []):
            doc_id = record.get("ContentDocumentId")
            # Obtener detalles del documento
            query_doc = f"""
                SELECT Title, FileType, ContentSize
                FROM ContentDocument 
                WHERE Id = '{doc_id}'
            """
            data_doc = sf.query(query_doc)
            docs = data_doc.get("records", [])
            if docs:
                doc = docs[0]
                adjuntos.append({
                    "id": doc_id,
                    "title": doc.get("Title", ""),
                    "file_type": doc.get("FileType", ""),
                    "size": doc.get("ContentSize", 0),
                })
        return adjuntos
    except Exception as e:
        log.error("Error al buscar adjuntos para %s: %s", entity_id, e)
        return []


def clasificar_adjuntos(adjuntos: list[dict]) -> dict:
    """
    Clasifica adjuntos por tipo basándose en el nombre del archivo.
    Retorna dict con listas de documentos encontrados por categoría.
    Los Technical Reports y las fotografías se mantienen como categorías separadas.
    """
    classifications = {
        "plm": [],
        "analisis_aceite": [],
        "datapacks": [],
        "reporte_tecnico": [],
        "fotografias": [],
        "work_order": [],
        "purchase_invoice": [],
    }

    keywords = {
        "plm": [
            "plm", "payload meter", "payload", "tonnage",
            "load", "weight", "cycle", "haul", "ton",
            "truck payload", "machine payload", "carga",
            "product lifecycle", "part number", "pn ",
        ],
        "analisis_aceite": ["oil analysis", "analisis de aceite", "oil leakage", "oil sample", "oil test"],
        "datapacks": [
            "dsc_", "datapack", "dsc", "haulcycle", "alarmfile", "im2", "komtrax",
            "data ", "data_", "vhms", "vims", "vids", "ge_", "plm_ht", "komtrax",
        ],
        "reporte_tecnico": [
            "technical report", "reporte tecnico", "failure analysis",
            "analisis de falla", "repair", "reparacion", "flash report",
            "tr-", "tr_", "tr ", "tsi", "claim report", "service letter",
            "service news", "informe", "falla", "leak", "needle", "sensor",
            "assembly", "replacement", "trouble", "diagnostico",
        ],
        "fotografias": [
            "foto", "photo", "imagen", "image", "picture", "evidencia",
            "img_", "screenshot", "captura", "video", "avi", "mp4",
            "ht", "before", "after", "installation", "evidencia", "pic",
        ],
        "work_order": [
            "work order", "workorder", "service order", "orden de trabajo",
            "repair order", "ro_", "ro-", "job card",
        ],
        "purchase_invoice": [
            "purchase invoice", "invoice", "factura", "purchase", "bill",
        ],
    }

    for adj in adjuntos:
        title_lower = adj["title"].lower()
        file_type = (adj.get("file_type") or "").lower()
        es_reporte_tecnico = False
        es_video_o_imagen = file_type in ("mp4", "mov", "avi", "jpg", "jpeg", "png", "heic", "bmp", "tiff")

        # Primero verificar si es reporte técnico
        # Solo PDFs o docs sin extension clara pueden ser technical reports
        # Videos e imagenes sueltas NO son technical reports
        if not es_video_o_imagen:
            if any(kw in title_lower for kw in keywords["reporte_tecnico"]):
                classifications["reporte_tecnico"].append(adj["title"])
                es_reporte_tecnico = True

        # Verificar otras categorías
        for tipo, kw_list in keywords.items():
            if tipo == "reporte_tecnico":
                continue  # Ya se verificó arriba
            if any(kw in title_lower for kw in kw_list):
                classifications[tipo].append(adj["title"])

        # Detectar fotografías por extension si no se clasifico antes
        if not any(adj["title"] in classifications[t] for t in classifications):
            if es_video_o_imagen:
                classifications["fotografias"].append(adj["title"])

    return classifications


def validar_adjuntos_requeridos(
    claim_id: str,
    tsi_id: str | None,
    claim_data: dict | None = None,
    es_pc: bool = False,
) -> dict:
    """
    Valida la presencia de documentos requeridos en un claim de Salesforce.
    Busca adjuntos tanto en el Claim como en el Case (TSI).
    Usa clasificacion hibrida: keywords primero, IA para casos sin match.
    """
    # Buscar adjuntos en Claim
    adjuntos_claim = buscar_adjuntos_sf(claim_id)

    # Buscar adjuntos en Case (TSI) si existe
    adjuntos_case = buscar_adjuntos_sf(tsi_id) if tsi_id else []

    # Combinar adjuntos (evitar duplicados por ID)
    ids_vistos = set()
    adjuntos_combinados = []
    for adj in adjuntos_claim + adjuntos_case:
        if adj["id"] not in ids_vistos:
            adjuntos_combinados.append(adj)
            ids_vistos.add(adj["id"])

    # Clasificar con keywords primero
    classifications = clasificar_adjuntos(adjuntos_combinados)
    classification_details = {}
    for adj in adjuntos_combinados:
        categories = [
            category
            for category, titles in classifications.items()
            if adj["title"] in titles
        ]
        classification_details[adj["id"]] = {"categories": categories}

    # Detectar adjuntos no clasificados (excluyendo datapacks que ya estan OK)
    titles_clasificados = set()
    for docs in classifications.values():
        titles_clasificados.update(docs)

    no_clasificados = [
        adj for adj in adjuntos_combinados
        if adj["title"] not in titles_clasificados
    ]

    # Enviar a IA los no clasificados (que sean PDFs, no videos)
    keywords_dp = ["dsc_", "datapack", "dsc", "haulcycle", "alarmfile", "im2", "komtrax"]
    for adj in no_clasificados:
        title_lower = adj["title"].lower()
        file_type = (adj.get("file_type") or "").lower()

        # Saltar datapacks (ya estan bien clasificados por keyword)
        if any(kw in title_lower for kw in keywords_dp):
            if adj["title"] not in classifications["datapacks"]:
                classifications["datapacks"].append(adj["title"])
            continue

        # Saltar videos (se clasifican por extension)
        if file_type in ("mp4", "mov", "avi"):
            if adj["title"] not in classifications["fotografias"]:
                classifications["fotografias"].append(adj["title"])
            continue

        # Enviar a IA
        log.info(f"Sin match por keywords, enviando a IA: {adj['title']}")
        try:
            resultado_ia = clasificar_adjunto_con_ia(adj, claim_data)
            cat = resultado_ia.get("categoria", "otro")
            if cat in classifications and cat != "otro":
                if adj["title"] not in classifications[cat]:
                    classifications[cat].append(adj["title"])
                classification_details[adj["id"]] = {
                    "categories": [cat],
                    "blob_folder": resultado_ia.get("blob_folder"),
                }
        except Exception as e:
            log.error(f"Error clasificando con IA: {e}")

    # Todos los Factory Warranty requieren estas categorías para su evaluación.
    required_categories = [
        "plm",
        "analisis_aceite",
        "datapacks",
        "reporte_tecnico",
    ]
    required_categories.extend(["work_order", "purchase_invoice"])
    total_required = len(required_categories)
    found = sum(1 for category in required_categories if classifications.get(category))

    return {
        "total_adjuntos": len(adjuntos_combinados),
        "adjuntos_en_claim": len(adjuntos_claim),
        "adjuntos_en_case": len(adjuntos_case),
        "clasificacion": classifications,
        "classification_details": classification_details,
        "documentos_encontrados": found,
        "documentos_requeridos": total_required,
        "faltantes": [tipo for tipo in required_categories if not classifications.get(tipo)],
    }


def obtener_content_version_id(content_document_id: str) -> str | None:
    """Obtiene el ContentVersionId (versión más reciente) desde ContentDocumentId."""
    sf = connect_salesforce()
    query = f"""
        SELECT Id
        FROM ContentVersion
        WHERE ContentDocumentId = '{content_document_id}'
        AND IsLatest = true
        LIMIT 1
    """
    try:
        data = sf.query(query)
        records = data.get("records", [])
        if records:
            return records[0].get("Id")
    except Exception as e:
        log.error("Error al obtener ContentVersion: %s", e)
    return None


def descargar_archivo_salesforce(content_version_id: str, local_path: str) -> bool:
    """
    Descarga el archivo binario desde Salesforce usando ContentVersion.
    Retorna True si la descarga fue exitosa.
    """
    sf = connect_salesforce()
    try:
        url = f"{sf.base_url}sobjects/ContentVersion/{content_version_id}/VersionData"
        response = sf._call_salesforce('GET', url)

        with open(local_path, 'wb') as f:
            f.write(response.content)

        log.info("Archivo descargado: %s", local_path)
        return True
    except Exception as e:
        log.error("Error al descargar archivo %s: %s", content_version_id, e)
        return False


def obtener_modelo_serial_tsi(tsi_id: str) -> dict:
    """
    Obtiene el modelo (Product__c) y número de serie (Machine_Serial__c)
    desde el objeto Case (que actua como TSI).
    """
    sf = connect_salesforce()
    query = f"""
        SELECT Product__c, Machine_Serial__c
        FROM Case
        WHERE Id = '{tsi_id}'
        LIMIT 1
    """
    try:
        data = sf.query(query)
        records = data.get("records", [])
        if records:
            return {
                "modelo": records[0].get("Product__c", ""),
                "serial": records[0].get("Machine_Serial__c", ""),
            }
    except Exception as e:
        log.error("Error al obtener modelo/serial del TSI %s: %s", tsi_id, e)

    return {"modelo": "", "serial": ""}


def descargar_y_subir_adjuntos_ia(
    claim_id: str,
    tsi_id: str | None,
    categorias: list[str],
    classifications: dict | None = None,
    attachment_details: dict | None = None,
) -> dict:
    """
    Descarga adjuntos de las categorías especificadas, convierte PDFs a PNG,
    sube a Azure Blob y retorna URLs SAS para enviar a Azure OpenAI.
    """
    from mr_warranty.infrastructure.blob import (
        obtener_urls_blob_existentes,
        pdf_to_imagenes,
        subir_imagenes_blob,
    )

    adjuntos_claim = buscar_adjuntos_sf(claim_id)
    adjuntos_case = buscar_adjuntos_sf(tsi_id) if tsi_id else []

    ids_vistos = set()
    adjuntos_combinados = []
    for adj in adjuntos_claim + adjuntos_case:
        if adj["id"] not in ids_vistos:
            adjuntos_combinados.append(adj)
            ids_vistos.add(adj["id"])

    classifications = classifications or clasificar_adjuntos(adjuntos_combinados)

    resultado = {}
    attachment_details = attachment_details or {}
    blob_urls_cache = {}

    def urls_cached(folder: str, filename_prefix: str | None = None) -> list[str]:
        cache_key = (folder, filename_prefix)
        if cache_key not in blob_urls_cache:
            blob_urls_cache[cache_key] = obtener_urls_blob_existentes(folder, filename_prefix)
        return blob_urls_cache[cache_key]

    for categoria in categorias:
        docs_titulos = classifications.get(categoria, [])
        urls_sas_categoria = []
        titulos_categoria = []

        for adj in adjuntos_combinados:
            if adj["title"] not in docs_titulos:
                continue

            doc_id = adj["id"]
            titulo = adj["title"]
            file_type = adj["file_type"]

            detail = attachment_details.get(doc_id, {})
            classification_folder = detail.get("blob_folder")
            if classification_folder:
                classification_urls = urls_cached(classification_folder)
                if classification_urls:
                    urls_sas_categoria.extend(classification_urls)
                    titulos_categoria.append(titulo)
                    continue

            blob_folder = f"AdjuntosSF/{claim_id}/{categoria}/{doc_id}"
            urls = urls_cached(blob_folder)
            if not urls:
                legacy_folder = f"AdjuntosSF/{claim_id}/{categoria}"
                legacy_prefix = re.sub(r"[^a-zA-Z0-9_\-]", "_", titulo)[:20]
                urls = urls_cached(legacy_folder, legacy_prefix)
            if urls:
                urls_sas_categoria.extend(urls)
                titulos_categoria.append(titulo)
                log.info("[BLOB CACHE] Reutilizando %s (%s)", titulo, categoria)
                continue

            cv_id = obtener_content_version_id(doc_id)
            if not cv_id:
                continue

            with tempfile.TemporaryDirectory() as tmp_dir:
                nombre_seguro = re.sub(r'[^a-zA-Z0-9_\-]', '_', titulo)[:30]
                extension = ".pdf" if file_type == "PDF" else f".{file_type.lower()}"
                local_file = os.path.join(tmp_dir, f"{nombre_seguro}{extension}")

                if not descargar_archivo_salesforce(cv_id, local_file):
                    continue

                if file_type == "PDF":
                    try:
                        png_files = pdf_to_imagenes(local_file, tmp_dir)
                    except Exception as e:
                        log.error("Error convirtiendo PDF a PNG: %s", e)
                        continue
                else:
                    png_files = [local_file]

                urls = subir_imagenes_blob(blob_folder, tmp_dir)
                urls_sas_categoria.extend(urls)
                titulos_categoria.append(titulo)

        resultado[categoria] = {
            "urls_sas": urls_sas_categoria,
            "titulos": titulos_categoria,
        }

    return resultado


def obtener_repair_date(claim_id: str) -> str | None:
    """Obtiene el Repair Date (MachineRepairCompletionDate__c) del TSI asociado al Claim."""
    sf = connect_salesforce()
    try:
        query_claim = f"SELECT TSINumber__c FROM Claim WHERE Id = '{claim_id}'"
        data = sf.query(query_claim)
        records = data.get("records", [])
        if not records or not records[0].get("TSINumber__c"):
            return None

        tsi_id = records[0]["TSINumber__c"]
        query_case = f"SELECT MachineRepairCompletionDate__c FROM Case WHERE Id = '{tsi_id}' LIMIT 1"
        data_case = sf.query(query_case)
        case_records = data_case.get("records", [])
        if case_records:
            return case_records[0].get("MachineRepairCompletionDate__c")
    except Exception as e:
        log.error("Error obteniendo repair_date para %s: %s", claim_id, e)
    return None


def obtener_coverage_type(claim_id: str) -> dict:
    """Obtiene CoverageType del ClaimCoverage asociado al Claim."""
    sf = connect_salesforce()
    try:
        query = f"SELECT CoverageType, Claim_Type__c, CausalPart__c, Parts_Requested_Amount__c, Parts_Requested_Quantity__c FROM ClaimCoverage WHERE ClaimId = '{claim_id}' LIMIT 1"
        data = sf.query(query)
        records = data.get("records", [])
        if records:
            return {
                "coverage_type": records[0].get("CoverageType", ""),
                "claim_group": records[0].get("Claim_Type__c", ""),
                "causal_part": records[0].get("CausalPart__c", ""),
                "parts_amount": records[0].get("Parts_Requested_Amount__c", 0),
                "parts_quantity": records[0].get("Parts_Requested_Quantity__c", 0),
            }
    except Exception as e:
        log.error("Error obteniendo coverage_type para %s: %s", claim_id, e)
    return {"coverage_type": "", "claim_group": "", "causal_part": "", "parts_amount": 0, "parts_quantity": 0}


def seleccionar_imagenes_para_ia(urls_sas: list[str], max_images: int = 10) -> list[str]:
    """Wrapper compatibilidad - delega a utils.seleccionar_imagenes_para_ia."""
    from mr_warranty.core.utils import seleccionar_imagenes_para_ia as _core_sel
    return _core_sel(urls_sas, max_images=max_images)


def clasificar_adjunto_con_ia(adjunto: dict, claim_data: dict | None = None) -> dict:
    """
    Descarga un adjunto, lo convierte a imagen si es PDF, lo sube a Blob
    y pregunta a Azure OpenAI que tipo de documento es.

    Retorna: {
        "categoria": "reporte_tecnico|plm|fotografias|analisis_aceite|otro",
        "confianza": 0.0-1.0,
        "razon": "..."
    }
    """
    from mr_warranty.infrastructure.blob import pdf_to_imagenes, subir_imagenes_blob
    from mr_warranty.services.prompts import clasificar_documento_adjunto
    from mr_warranty.infrastructure.cache import get_clasificacion_cache, save_clasificacion_cache

    # La taxonomía incluye Work Order e Invoice; no reutilizar clasificaciones antiguas.
    cache_key = f"v2:{adjunto['id']}"
    cached = get_clasificacion_cache(cache_key)
    if cached:
        log.info(f"[CACHE] {adjunto['title']}: {cached.get('categoria')} (confianza={cached.get('confianza', 0):.2f})")
        return cached

    cv_id = obtener_content_version_id(adjunto["id"])
    if not cv_id:
        return {"categoria": "otro", "confianza": 0.0, "razon": "No se pudo obtener ContentVersionId"}

    file_type = (adjunto.get("file_type") or "").lower()

    if file_type in ("mp4", "mov", "avi"):
        return {"categoria": "fotografias", "confianza": 0.85, "razon": "Video detectado por extension"}

    with tempfile.TemporaryDirectory() as tmp_dir:
        nombre_seguro = re.sub(r'[^a-zA-Z0-9_\-]', '_', adjunto["title"])[:30]
        extension = f".{file_type}" if file_type else ".bin"
        local_file = os.path.join(tmp_dir, f"{nombre_seguro}{extension}")

        if not descargar_archivo_salesforce(cv_id, local_file):
            return {"categoria": "otro", "confianza": 0.0, "razon": "Error al descargar"}

        if file_type == "pdf":
            try:
                png_files = pdf_to_imagenes(local_file, tmp_dir)
            except Exception as e:
                log.error(f"Error convirtiendo PDF a PNG: {e}")
                return {"categoria": "otro", "confianza": 0.0, "razon": f"Error PDF: {e}"}
        else:
            png_files = [local_file]

        blob_folder = f"Clasificacion/{adjunto['id']}"
        urls = subir_imagenes_blob(blob_folder, tmp_dir)

        if not urls:
            return {"categoria": "otro", "confianza": 0.0, "razon": "Error al subir a Blob"}

    try:
        modelo = (claim_data or {}).get("modelo", "")
        serial = (claim_data or {}).get("serial", "")
        resultado = clasificar_documento_adjunto(urls, modelo, serial)
    except Exception as e:
        log.error(f"Error en clasificacion IA: {e}")
        return {"categoria": "otro", "confianza": 0.0, "razon": f"Error IA: {e}"}

    resultado["blob_folder"] = blob_folder
    save_clasificacion_cache(cache_key, resultado)

    confianza = resultado.get("confianza", 0)
    if confianza >= 0.7:
        log.info(f"[IA OK] {adjunto['title']}: {resultado.get('categoria')} (confianza={confianza:.2f})")
    else:
        log.warning(f"[IA BAJA] {adjunto['title']}: {resultado.get('categoria')} (confianza={confianza:.2f}) - {resultado.get('razon', '')}")

    return resultado
