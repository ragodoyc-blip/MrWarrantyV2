import ast
import time

from openai import OpenAI

from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY
from logger import log
from Ponderaciones import PONDERACIONES_STD, PONDERACIONES_FC, Ajuste_Parts, PONDERACIONES_STD_SF

# -------------------------------------------------------------
# Utilidad universal: parsea string → dict de forma segura
# -------------------------------------------------------------
def safe_parse_dict(texto, max_ponderacion):
    """
    Recibe algo como:
    "{'score': 0.04, 'reason': 'texto'}"
    y retorna un dict validado.
    """

    if not isinstance(texto, str):
        raise ValueError("La respuesta del modelo no es un string.")

    # Sanitizar: eliminar saltos y espacios extremos
    limpio = texto.strip()

    try:
        parsed = ast.literal_eval(limpio)
    except Exception as e:
        raise ValueError(f"El modelo devolvió un diccionario inválido: {texto}") from e

    # Validar estructura obligatoria
    if not isinstance(parsed, dict):
        raise ValueError(f"El modelo no devolvió un diccionario válido: {parsed}")

    if "score" not in parsed or "reason" not in parsed:
        raise ValueError(f"Diccionario no contiene claves esperadas ('score', 'reason'): {parsed}")

    # Validar que el score no exceda la ponderación máxima
    if parsed["score"] > max_ponderacion:
        raise ValueError(f"El score ({parsed['score']}) excede la ponderación máxima permitida ({max_ponderacion}).")

    return parsed


# -------------------------------------------------------------
# Utilidad para parsear respuesta de clasificacion: {categoria, confianza, razon}
# -------------------------------------------------------------
def safe_parse_clasificacion(texto):
    """
    Recibe algo como:
    "{'categoria': 'reporte_tecnico', 'confianza': 0.95, 'razon': 'texto'}"
    y retorna un dict validado.
    """
    if not isinstance(texto, str):
        raise ValueError("La respuesta del modelo no es un string.")

    limpio = texto.strip()

    try:
        parsed = ast.literal_eval(limpio)
    except Exception as e:
        raise ValueError(f"El modelo devolvió un diccionario inválido: {texto}") from e

    if not isinstance(parsed, dict):
        raise ValueError(f"El modelo no devolvió un diccionario válido: {parsed}")

    if "categoria" not in parsed or "confianza" not in parsed or "razon" not in parsed:
        raise ValueError(
            f"Diccionario no contiene claves esperadas ('categoria', 'confianza', 'razon'): {parsed}"
        )

    return parsed


# -------------------------------------------------------------
# Funcion generica que ejecuta el modelo con reintentos seguros
# -------------------------------------------------------------
def call_azure_gpt(messages, deployment, max_ponderacion, max_retries=3, parse_mode="score"):
    """
    parse_mode: "score" para validacion con score/reason
                 "clasificacion" para respuesta con categoria/confianza/razon
    """
    client = OpenAI(
        base_url=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
    )

    retry = 0
    backoff = 0.5

    while retry < max_retries:
        try:
            response = client.chat.completions.create(
                messages=messages,
                max_tokens=800,
                temperature=0.0,
                top_p=1.0,
                model=deployment,
            )
            texto = response.choices[0].message.content
            if parse_mode == "clasificacion":
                return safe_parse_clasificacion(texto)
            return safe_parse_dict(texto, max_ponderacion)

        except Exception as e:
            log.warning("Intento %d/%d falló: %s", retry + 1, max_retries, e)
            retry += 1
            if retry < max_retries:
                time.sleep(backoff)
                backoff *= 2

    log.error("IA falló definitivamente tras %d intentos. Continuando con siguiente registro...", max_retries)
    return {
        "score": 0.0,
        "reason": "Error: No se pudo procesar este caso con IA después de varios intentos.",
    }


# -------------------------------------------------------------
# Definición común de system prompt
# -------------------------------------------------------------
SYSTEM_TEMPLATE = (
    "Eres un analista técnico. "
    "Debes responder SIEMPRE en formato diccionario Python. "
    "Formato obligatorio de respuesta: {'score': <float>, 'reason': '<texto>'}. "
    "No incluyas texto fuera del diccionario."
)


# =============================================================
# 1) Informe Técnico
# =============================================================
def InformeTecnico(dict_caso, extendermensaje, tipoWC):
    if tipoWC == "STD":
        ponderacion = PONDERACIONES_STD.get("technical_report")
    elif tipoWC == "FC":
        ponderacion = PONDERACIONES_FC.get("technical_report")

    messages = [
        {"role": "system", "content": SYSTEM_TEMPLATE},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""
    Recibiras información del caso subido en plataforma en el diccionario {dict_caso} que contiene:
    - kom_customerassetmodelcal (Modelo)
    - kom_user (Distribuidor)
    - kom_failuresmrd (SMR)
    - kom_failuredate (Fecha falla)
    - kom_workordernumber (Work Order)

    Deberas analizar el documento que se llame o haga referencia al informe tecnico. Normalmente contiene imagenes del
    procedimiento y tablas con datos.

    Si todo coincide: score = {ponderacion}, reason = 'OK'.
    Si algo no coincide: score < {ponderacion} y reason explicando claramente.

    Responde SOLO con un diccionario Python válido.
    """
                },
                *extendermensaje
            ]
        }
    ]

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=ponderacion)


# =============================================================
# 2) Orden de Trabajo
# =============================================================
def OrdenTrabajo(dict_caso, extendermensaje, tipoWC):
    if tipoWC == "STD":
        ponderacion = PONDERACIONES_STD.get("work_order")
    elif tipoWC == "FC":
        ponderacion = PONDERACIONES_FC.get("work_order")

    messages = [
        {"role": "system", "content": SYSTEM_TEMPLATE},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""
    Recibiras el diccionario {dict_caso} con:
    - kom_workordernumber

    Debes verificar en los documentos si existe una orden de trabajo coincidente (NO factura, No informe tecnico) con
    el numero de orden de trabajo del diccionario.
    Ademas es requisito que la descripción del trabajo dentro del documento debe estar en ingles, si no es ese el idioma debes mencionarlo y
    penalizarlo en el score con un poco menos de puntaje.

    Si todo coincide: score = {ponderacion}, reason = 'OK'.
    Si algo no coincide: score < {ponderacion}, reason explicando claramente.
    Responde SOLO un diccionario Python válido.
    """
                },
                *extendermensaje
            ]
        }
    ]

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=ponderacion)


# =============================================================
# 3) Facturas
# =============================================================
def facturas_promp(extendermensaje, dict_caso_partes, tipoWC):
    if tipoWC == "STD":
        ponderacion = PONDERACIONES_STD.get("invoices")
    elif tipoWC == "FC":
        ponderacion = PONDERACIONES_FC.get("invoices")
    
    ajuste = dict_caso_partes.get('kom_distributorcode', {}).get(0)
    ajuste = Ajuste_Parts.get(ajuste)

    messages = [
        {"role": "system", "content": SYSTEM_TEMPLATE},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""
    Se analizarán piezas del reclamo usando {dict_caso_partes} con:
    - kom_productserialnumber
    - kom_offerquantity
    - kom_offercost

    Comparar exactamente con la factura adjunta. 
    Por lo tanto debes saber la cantidad de piezas contenidas en el reclamo y buscar el unit price
    en la factura de la pieza. Con el número de piezas en el reclamo y el unit price en la factura, multiplica ambos
    valores y luego ajusta el valor resultante multiplicandolo por {ajuste}.
    Ese valor debes compararlo con el reclamo, y si la diferencia es mayor a 10 usd, 
    el score debe ser 0, si la diferencia es menor o igual a 10 usd para cada pieza, el score debe ser {ponderacion}.

    Ademas no castigues el score si las piezas en la factura no son las mismas que las del reclamo, dado que el distribuidor puede dejar piezas 
    extras en la factura.
    Si todo coincide según lo mencionado: score = {ponderacion}, reason = 'OK'.
    Si algo no coincide: score < {ponderacion}, reason explicando claramente.

    Responde SOLO un diccionario Python válido.
    """
                },
                *extendermensaje
            ]
        }
    ]

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=ponderacion)


# =============================================================
# 4) Fotografías
# =============================================================
def fotografias(dict_caso, extendermensaje, tipoWC):
    if tipoWC == "STD":
        ponderacion = PONDERACIONES_STD.get("photographs")
        
        messages = [
            {"role": "system", "content": SYSTEM_TEMPLATE},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
        Recibiras el diccionario {dict_caso} con:
        - kom_failuredetailenglish
        - kom_offerdetailenglish
        - kom_otherenglish
        - kom_claimcommentenglish

        Estas columnas ocupas como referencias y deben tener la misma relación con lo que aparece en las imagenes.
        Las imagenes deben contener y aparecer evidenciando la falla, proceso de reparación y finalmente la maquina funcionando.
        Es requisito principal que aparezca esto proceso como evidencia del reclamo de garantía.


        Si todo coincide: score = {ponderacion}, reason = 'OK'.
        Si algo no coincide: score < {ponderacion}, reason explicando claramente.
        Responde SOLO un diccionario Python válido.
        """
                    },
                    *extendermensaje
                ]
            }
        ]

    elif tipoWC == "FC":
        ponderacion = PONDERACIONES_FC.get("photographs")
        messages = [
            {"role": "system", "content": SYSTEM_TEMPLATE},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
        Recibiras el diccionario {dict_caso} con:
        - kom_failuredetailenglish
        - kom_offerdetailenglish
        - kom_otherenglish
        - kom_claimcommentenglish

        Estas columnas ocupas como referencias y deben tener la misma relación con lo que aparece en las imagenes.
        Las imagenes deben evidenciar la ejecución de la campaña, bajo el concepto que se mencionan en el diccionario.
        Si no tiene relación debes mencionarlo.


        Si todo coincide: score = {ponderacion}, reason = 'OK'.
        Si algo no coincide: score < {ponderacion}, reason explicando claramente.
        Responde SOLO un diccionario Python válido.
        """
                    },
                    *extendermensaje
                ]
            }
        ]
    

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=ponderacion)

# =============================================================
# 5) Análisis de Causa Raíz
# =============================================================
def root_cause_analysis(dict_caso, dict_chatter):
    ponderacion_root_cause = PONDERACIONES_STD_SF.get("RootCause_analysis")
    messages = [
        {"role": "system", "content": SYSTEM_TEMPLATE},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""
        Recibiras el diccionario {dict_caso} con un reclamo de garantía.
        Debes analizar toda la información del caso y los posts de chatter asociados en {dict_chatter}.
        Debes determinar si la causa raíz del problema está claramente identificada y respaldada por la evidencia proporcionada.


        Si esta presente la causa raiz: score = {ponderacion_root_cause}, reason = 'OK'.
        Si algo no coincide: score < {ponderacion_root_cause}, reason explicando claramente.
        Responde SOLO un diccionario Python válido.
        """
                }
            ]
        }
    ]

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion = ponderacion_root_cause)


# =============================================================
# 6) Validar adjunto con IA (technical_report, plm)
# =============================================================
def validar_adjunto_con_ia(
    urls_sas: list[str],
    modelo: str,
    serial: str,
    tipo_adjunto: str,
    ponderacion: float,
) -> dict:
    """
    Envía imágenes del adjunto a Azure OpenAI para validar modelo y serial.
    Primera imagen = portada, luego hasta 9 adicionales.
    """
    from API_Salesforce import seleccionar_imagenes_para_ia

    if not urls_sas:
        return {"score": 0, "reason": f"No se encontró {tipo_adjunto}"}

    system = (
        "Eres un analista técnico. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'score': <float>, 'reason': '<texto>'}"
    )

    user_text = f"""
    Analiza las imágenes del {tipo_adjunto} adjunto.

    Datos esperados del Claim:
    - Modelo: {modelo}
    - Número de serie: {serial}

    Verifica que el documento contenga ambos datos.

    Si ambos coinciden: score = {ponderacion}, reason = 'OK'
    Si falta uno o ninguno: score < {ponderacion}, reason explicando
    Responde SOLO un diccionario Python válido.
    """

    urls_limitadas = seleccionar_imagenes_para_ia(urls_sas, max_images=10)

    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                *[{"type": "image_url", "image_url": {"url": url}} for url in urls_limitadas],
            ],
        },
    ]

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=ponderacion)


# =============================================================
# 9) Extraer fecha de instalacion de parte (para PC)
# =============================================================
def extraer_fecha_instalacion_parte(dict_claim: dict, dict_tsi: dict) -> dict:
    """
    Extrae la fecha de instalacion/reemplazo de la parte desde el texto del Claim y TSI.
    Retorna: {'fecha': 'YYYY-MM-DD', 'confianza': <0-1>, 'razon': '...'}
    """
    system = (
        "Eres un analista tecnico de Komatsu. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'fecha': 'YYYY-MM-DD' o None, 'confianza': <0.0-1.0>, 'razon': '<texto>'}"
    )

    claim_summary = dict_claim.get("Summary", "") or ""
    claim_description = dict_claim.get("Description", "") or ""
    claim_cause = dict_claim.get("Cause__c", "") or ""
    claim_correction = dict_claim.get("Correction__c", "") or ""
    claim_additional = dict_claim.get("AdditionalComments__c", "") or ""
    claim_complaint = dict_claim.get("Complaint__c", "") or ""

    tsi_subject = dict_tsi.get("Subject", "") or ""
    tsi_description = dict_tsi.get("Description", "") or ""
    tsi_resolution = dict_tsi.get("Resolution_Details__c", "") or ""

    user_text = f"""
    Analiza la siguiente informacion del Claim y TSI (Technical Service Information).
    Identifica la FECHA en que se INSTALO o REEMPLAZO la parte/componente que esta siendo reclamada.

    Busca frases como:
    - "replaced on <fecha>"
    - "installed on <fecha>"
    - "instalado el <fecha>"
    - "reemplazado el <fecha>"
    - "service life ended"
    - "component reached end of service life"
    - fechas en formato MM/DD/YYYY, YYYY-MM-DD, DD/MM/YYYY, Month DD YYYY, etc.

    Claim:
    - Summary: {claim_summary}
    - Description: {claim_description}
    - Cause: {claim_cause}
    - Correction: {claim_correction}
    - AdditionalComments: {claim_additional}
    - Complaint: {claim_complaint}

    TSI:
    - Subject: {tsi_subject}
    - Description: {tsi_description}
    - Resolution: {tsi_resolution}

    Si encuentras la fecha, respondela en formato YYYY-MM-DD.
    Si no encuentras fecha explícita, responde fecha=null.
    Responde SOLO un diccionario Python válido.
    """

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": [{"type": "text", "text": user_text}]},
    ]

    try:
        client = OpenAI(base_url=AZURE_OPENAI_ENDPOINT, api_key=AZURE_OPENAI_KEY)
        response = client.chat.completions.create(
            messages=messages, max_tokens=500, temperature=0.0, top_p=1.0, model="gpt-4.1",
        )
        texto = response.choices[0].message.content.strip()
        import ast
        parsed = ast.literal_eval(texto)
        if isinstance(parsed, dict) and "fecha" in parsed:
            return parsed
        return {"fecha": None, "confianza": 0.0, "razon": "Formato inesperado de la IA"}
    except Exception as e:
        return {"fecha": None, "confianza": 0.0, "razon": f"Error IA: {e}"}


# =============================================================
# 10) Validar Work Order con IA (para PC)
# =============================================================
def validar_work_order_con_ia(urls_sas: list[str], claim_data: dict) -> dict:
    """
    Valida que exista un documento tipo Work Order y que tenga sentido con el reclamo.
    Retorna: {'score': <float>, 'reason': '<texto>'}
    """
    if not urls_sas:
        return {"score": 0, "reason": "No hay documentos adjuntos para validar Work Order"}

    from API_Salesforce import seleccionar_imagenes_para_ia

    system = (
        "Eres un analista tecnico de Komatsu. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'score': <float>, 'reason': '<texto>'}"
    )

    claim_name = claim_data.get("Name", "")
    complaint = claim_data.get("Complaint__c", "") or ""
    correction = claim_data.get("Correction__c", "") or ""
    summary = claim_data.get("Summary", "") or ""

    user_text = f"""
    Analiza las imagenes adjuntas buscando un documento tipo WORK ORDER (orden de trabajo/service order).

    Informacion del Claim {claim_name}:
    - Queja: {complaint}
    - Correccion: {correction}
    - Resumen: {summary}

    Verifica que:
    1. Exista al menos un documento que sea Work Order / Service Order
    2. El trabajo descrito en el Work Order tenga relacion con la queja y correccion del reclamo
    3. Las fechas del Work Order sean coherentes con el reclamo

    Si existe Work Order y es relevante: score = 0.10, reason = 'OK'
    Si existe pero no es relevante: score = 0.05, reason explicando
    Si no existe Work Order: score = 0, reason = 'No se encontro Work Order'
    Responde SOLO un diccionario Python válido.
    """

    urls_limitadas = seleccionar_imagenes_para_ia(urls_sas, max_images=5)

    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                *[{"type": "image_url", "image_url": {"url": url}} for url in urls_limitadas],
            ],
        },
    ]

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=0.10)


# =============================================================
# 11) Validar Purchase Invoice con IA (para PC)
# =============================================================
def validar_purchase_invoice_con_ia(urls_sas: list[str], claim_data: dict) -> dict:
    """
    Valida que exista una factura de compra del componente.
    Retorna: {'score': <float>, 'reason': '<texto>'}
    """
    if not urls_sas:
        return {"score": 0, "reason": "No hay documentos adjuntos para validar Purchase Invoice"}

    from API_Salesforce import seleccionar_imagenes_para_ia

    system = (
        "Eres un analista tecnico de Komatsu. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'score': <float>, 'reason': '<texto>'}"
    )

    claim_name = claim_data.get("Name", "")
    causal_part = claim_data.get("CausalPart__c", "") or ""
    parts_amount = claim_data.get("Parts_Requested_Amount__c", 0) or 0

    user_text = f"""
    Analiza las imagenes adjuntas buscando una FACTURA DE COMPRA del componente/parte.

    Informacion del Claim {claim_name}:
    - Parte causal: {causal_part}
    - Monto reclamado: {parts_amount} USD

    Verifica que:
    1. Exista al menos un documento que sea Purchase Invoice / Factura de compra / Invoice
    2. La factura sea del componente/parte que se esta reclamando
    3. El monto de la factura sea coherente con el monto reclamado
    4. La fecha de la factura sea anterior a la fecha del reclamo

    Si existe factura y es relevante: score = 0.10, reason = 'OK'
    Si existe pero no es relevante: score = 0.05, reason explicando
    Si no existe factura: score = 0, reason = 'No se encontro factura de compra'
    Responde SOLO un diccionario Python válido.
    """

    urls_limitadas = seleccionar_imagenes_para_ia(urls_sas, max_images=5)

    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                *[{"type": "image_url", "image_url": {"url": url}} for url in urls_limitadas],
            ],
        },
    ]

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=0.10)


# =============================================================
# 8) Clasificar documento adjunto con IA
# =============================================================
def clasificar_documento_adjunto(
    urls_sas: list[str],
    modelo_esperado: str = "",
    serial_esperado: str = "",
) -> dict:
    """
    Clasifica un adjunto de Salesforce leyendo su contenido con Azure OpenAI.
    Categorias: reporte_tecnico, plm, fotografias, analisis_aceite, otro
    """
    if not urls_sas:
        return {"categoria": "otro", "confianza": 0.0, "razon": "Sin URLs"}

    from API_Salesforce import seleccionar_imagenes_para_ia

    system = (
        "Eres un analista tecnico de Komatsu especializado en clasificacion de documentos. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'categoria': '<cat>', 'confianza': <0.0-1.0>, 'razon': '<texto>'}"
    )

    user_text = f"""
    Analiza las imagenes del documento adjunto y clasificalo en UNA de estas categorias:

    - "reporte_tecnico": Technical report, failure analysis, informe tecnico, reporte de reparacion, procedimiento
    - "plm": Payload Meter (documento que muestra peso/carga transportada por la maquina en toneladas)
    - "fotografias": Evidencia fotografica, fotos de la falla, reparacion, maquina funcionando, videos
    - "analisis_aceite": Oil analysis, analisis de aceite, muestra de lubricante, laboratorio de aceite
    - "otro": Facturas, ordenes de compra, work orders, certificados, cualquier otro documento

    Contexto del Claim:
    - Modelo esperado: {modelo_esperado}
    - Numero de serie esperado: {serial_esperado}

    Responde SOLO un diccionario Python valido con:
    - categoria: una de las 5 opciones
    - confianza: float entre 0.0 y 1.0
    - razon: explicacion breve (max 100 caracteres)
    """

    urls_limitadas = seleccionar_imagenes_para_ia(urls_sas, max_images=5)

    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                *[{"type": "image_url", "image_url": {"url": url}} for url in urls_limitadas],
            ],
        },
    ]

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=1.0, parse_mode="clasificacion")



# =============================================================
# 7) Validar fotografías con IA
# =============================================================
def validar_photographs_con_ia(
    urls_sas: list[str],
    complaint: str,
    cause: str,
    ponderacion: float,
) -> dict:
    """
    Valida que las fotografías correspondan a la queja y causa del reclamo.
    Primera imagen = portada, luego hasta 9 adicionales.
    """
    from API_Salesforce import seleccionar_imagenes_para_ia

    if not urls_sas:
        return {"score": 0, "reason": "No se encontraron fotografías"}

    system = (
        "Eres un analista técnico. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'score': <float>, 'reason': '<texto>'}"
    )

    user_text = f"""
    Analiza las fotografías adjuntas.

    Información del Claim:
    - Queja: {complaint}
    - Causa: {cause}

    Las fotografías deben evidenciar la falla mencionada en la queja.
    Si están relacionadas: score = {ponderacion}, reason = 'OK'
    Si no hay relación: score < {ponderacion}, reason explicando
    Responde SOLO un diccionario Python válido.
    """

    urls_limitadas = seleccionar_imagenes_para_ia(urls_sas, max_images=10)

    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                *[{"type": "image_url", "image_url": {"url": url}} for url in urls_limitadas],
            ],
        },
    ]

    return call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=ponderacion)