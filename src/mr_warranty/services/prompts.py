import ast
import time

from openai import OpenAI

from mr_warranty.config.config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY
from mr_warranty.core.logger import log
from mr_warranty.core.ponderaciones import PONDERACIONES_STD, PONDERACIONES_FC, Ajuste_Parts, PONDERACIONES_STD_SF

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

    # Algunos modelos devuelven una proporción 0..1 en lugar del valor ponderado.
    # Convertirla evita descartar una evaluación válida por escala incorrecta.
    try:
        score = float(parsed["score"])
    except (TypeError, ValueError) as e:
        raise ValueError(f"El score no es numérico: {parsed['score']}") from e

    if score < 0:
        raise ValueError(f"El score ({score}) no puede ser negativo.")
    if score > max_ponderacion:
        if 0 <= score <= 1:
            parsed["score"] = round(score * max_ponderacion, 6)
            parsed["reason"] = f"PARCIAL: Escala IA normalizada. {parsed['reason']}"
        else:
            raise ValueError(f"El score ({score}) excede la ponderación máxima permitida ({max_ponderacion}).")
    else:
        parsed["score"] = score

    return parsed


def score_from_criteria(result: dict, max_score: float, criteria_keys: list[str]) -> dict:
    """Calcula el puntaje desde criterios booleanos devueltos por la IA."""
    criteria = result.get("criteria")
    if not isinstance(criteria, dict):
        return result

    def is_true(value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "yes", "si", "sí", "1", "ok"}

    fulfilled = sum(is_true(criteria.get(key)) for key in criteria_keys)
    result["score"] = round(max_score * fulfilled / len(criteria_keys), 6)
    # Post-proceso Plan A: asegura salto de línea antes de cada número para PowerApps/Excel
    if "reason" in result and isinstance(result["reason"], str):
        import re

        reason = result["reason"].strip()
        # Inserta \n antes de cada " 1) " " 2) " si no existe
        reason = re.sub(r" (\d+\) )", r"\n\1", reason)
        # Normaliza múltiples saltos y asegura que empiece sin \n extra
        reason = re.sub(r"\n{2,}", "\n", reason)
        result["reason"] = reason.strip()
    return result


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
# 6) Validar adjunto con IA (technical_report, plm)
# =============================================================
def validar_adjunto_con_ia(
    urls_sas: list[str],
    modelo: str,
    serial: str,
    tipo_adjunto: str,
    ponderacion: float,
    claim_context: dict | None = None,
) -> dict:
    """
    Envía imágenes del adjunto a Azure OpenAI para validar modelo y serial.
    Primera imagen = portada, luego hasta 9 adicionales.
    """
    from mr_warranty.core.utils import seleccionar_imagenes_para_ia

    if not urls_sas:
        return {"score": 0, "reason": f"No se encontró {tipo_adjunto}"}

    system = (
        "Eres un analista técnico. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'score': <float>, 'reason': '<texto>'}"
    )

    if tipo_adjunto.lower() in {"reporte técnico", "reporte tecnico", "technical report"} and claim_context:
        user_text = f"""
        Analiza las imágenes del informe técnico adjunto y compáralas con el Claim y el Case.

        Datos esperados:
        - Modelo: {modelo}
        - Número de serie: {serial}
        - Queja del Claim: {claim_context.get("complaint", "")}
        - Causa del Claim: {claim_context.get("cause", "")}
        - Corrección del Claim: {claim_context.get("correction", "")}
        - Resumen del Claim: {claim_context.get("summary", "")}
        - Descripción del Case: {claim_context.get("case_description", "")}
        - Resolución del Case: {claim_context.get("case_resolution", "")}

        Evalúa cinco criterios independientes:
        1. El modelo coincide.
        2. El número de serie coincide.
        3. El componente reclamado aparece en el documento.
        4. Las imágenes del informe evidencian la falla descrita.
        5. Existen imágenes de antes y después de la reparación dentro del informe.

        Asigna score = {ponderacion} multiplicado por criterios cumplidos / 5.
        Si existe una contradicción clara entre el informe y el Claim/Case, no otorgues ese criterio.
        No supongas datos que no sean visibles o que no estén en el contexto.
        Devuelve también criteria con estas claves booleanas exactas:
        model_match, serial_match, component_match, failure_evidence, before_after.
        El score debe ser el valor absoluto entre 0 y {ponderacion}.
        Explica en reason qué criterios cumplieron, cuáles faltaron y cualquier contradicción.
        Responde SOLO un diccionario Python válido.
        """
    elif tipo_adjunto.lower() == "plm" and claim_context:
        user_text = f"""
        Analiza las imágenes del PLM adjunto.

        Datos esperados:
        - Modelo: {modelo}
        - Número de serie: {serial}
        - Fecha de falla: {claim_context.get("failure_date", "")}
        - Inicio del período válido: {claim_context.get("plm_period_start", "")}
        - Fin del período válido: {claim_context.get("plm_period_end", "")}

        Verifica tres criterios independientes:
        1. El modelo coincide.
        2. El número de serie coincide.
        3. La información o fecha del PLM pertenece al período válido indicado.

        El período válido es el último año antes de la falla. Si el equipo tiene menos de un año,
        el período comienza en MachineCommissionedDate__c y termina en la fecha de falla.
        Devuelve criteria con estas claves booleanas exactas:
        model_match, serial_match, period_valid.
        El score debe ser el valor absoluto entre 0 y {ponderacion}.
        No supongas datos que no sean visibles.
        Responde SOLO un diccionario Python válido.
        """
    else:
        user_text = f"""
        Analiza las imágenes del {tipo_adjunto} adjunto.

        Datos esperados del Claim:
        - Modelo: {modelo}
        - Número de serie: {serial}

        Evalúa dos criterios independientes:
        1. El modelo coincide.
        2. El número de serie coincide.

        Asigna score = {ponderacion} multiplicado por criterios cumplidos / 2.
        Devuelve también criteria con estas claves booleanas exactas:
        model_match, serial_match.
        El score debe ser el valor absoluto entre 0 y {ponderacion}.
        Explica en reason qué dato coincide y cuál falta o no coincide.
        No supongas datos que no sean visibles.
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

    result = call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=ponderacion)
    if tipo_adjunto.lower() in {"reporte técnico", "reporte tecnico", "technical report"} and claim_context:
        return score_from_criteria(
            result,
            ponderacion,
            ["model_match", "serial_match", "component_match", "failure_evidence", "before_after"],
        )
    if tipo_adjunto.lower() == "plm" and claim_context:
        return score_from_criteria(
            result,
            ponderacion,
            ["model_match", "serial_match", "period_valid"],
        )
    return score_from_criteria(result, ponderacion, ["model_match", "serial_match"])


# =============================================================
# 6b) Validar Oil Analysis con IA
# =============================================================
def validar_oil_analysis_con_ia(
    urls_sas: list[str],
    modelo: str,
    serial: str,
    component: str,
    ponderacion: float,
) -> dict:
    """Valida máquina, serial y componente en un análisis de aceite."""
    if not urls_sas:
        return {"score": 0, "reason": "No se encontró Oil Analysis"}

    from mr_warranty.core.utils import seleccionar_imagenes_para_ia

    system = (
        "Eres un analista técnico de Komatsu. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'score': <float>, 'reason': '<texto>'}"
    )
    user_text = f"""
    Analiza las imágenes del Oil Analysis adjunto.

    Datos esperados:
    - Máquina/modelo: {modelo}
    - Número de serie: {serial}
    - Componente: {component}

    Evalúa tres criterios independientes:
    1. La máquina o modelo coincide.
    2. El número de serie coincide.
    3. El componente analizado coincide con el componente reclamado.

    Asigna score = {ponderacion} multiplicado por criterios cumplidos / 3.
    Devuelve también criteria con estas claves booleanas exactas:
    machine_match, serial_match, component_match.
    El score debe ser el valor absoluto entre 0 y {ponderacion}.
    No supongas datos que no sean visibles. Explica coincidencias y faltantes.
    Responde SOLO un diccionario Python válido.
    """
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                *[
                    {"type": "image_url", "image_url": {"url": url}}
                    for url in seleccionar_imagenes_para_ia(urls_sas, max_images=10)
                ],
            ],
        },
    ]
    result = call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=ponderacion)
    return score_from_criteria(result, ponderacion, ["machine_match", "serial_match", "component_match"])


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

    from mr_warranty.core.utils import seleccionar_imagenes_para_ia

    system = (
        "Eres un analista tecnico de Komatsu. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'score': <float>, 'reason': '<texto>'}"
    )

    claim_name = claim_data.get("Name", "")
    modelo = claim_data.get("Modelo", claim_data.get("modelo", "")) or ""
    serial = claim_data.get("Serial", claim_data.get("serial", "")) or ""
    work_order_number = claim_data.get("WorkOrderNumber", "") or ""
    failure_date = claim_data.get("FailureDate__c", "") or ""
    repair_date = claim_data.get("MachineRepairCompletionDate__c", "") or ""
    component = claim_data.get("CausalPart__c", "") or claim_data.get("Product_Code__c", "") or ""
    complaint = claim_data.get("Complaint__c", "") or ""
    correction = claim_data.get("Correction__c", "") or ""
    summary = claim_data.get("Summary", "") or ""

    user_text = f"""
    Analiza las imagenes adjuntas buscando un documento tipo WORK ORDER (orden de trabajo/service order).

    Informacion del Claim {claim_name}:
    - Queja: {complaint}
    - Correccion: {correction}
    - Resumen: {summary}

    Datos técnicos esperados:
    - Modelo: {modelo}
    - Serial: {serial}
    - Número de Work Order de referencia: {work_order_number}
    - Componente: {component}
    - Fecha de falla: {failure_date}
    - Fecha de reparación: {repair_date}

    Evalúa cinco criterios independientes:
    1. Existe un número de Work Order legible y, si hay referencia, coincide.
    2. La máquina y el serial coinciden.
    3. La fecha del documento es legible y coherente con el reclamo.
    4. El trabajo realizado está descrito claramente y se relaciona con la queja/corrección.
    5. El componente intervenido coincide con el componente reclamado.

    Asigna score = 0.10 multiplicado por criterios cumplidos / 6.
    Devuelve también criteria con estas claves booleanas exactas:
    work_order_number, machine_serial, date, work_performed, component_match, english.
    El score debe ser el valor absoluto entre 0 y 0.10.
    No supongas datos que no sean visibles. Explica criterios cumplidos, faltantes y contradicciones.
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

    result = call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=0.10)
    return score_from_criteria(
        result,
        0.10,
        ["work_order_number", "machine_serial", "date", "work_performed", "component_match", "english"],
    )


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

    from mr_warranty.core.utils import seleccionar_imagenes_para_ia

    system = (
        "Eres un analista tecnico de Komatsu. "
        "Debes responder SIEMPRE en formato diccionario Python. "
        "Formato: {'score': <float>, 'reason': '<texto>'}"
    )

    claim_name = claim_data.get("Name", "")
    causal_part = claim_data.get("CausalPart__c", "") or ""
    product_code = claim_data.get("Product_Code__c", "") or ""
    installation_date = claim_data.get("PartInstallationDate", "") or ""
    claim_date = claim_data.get("CreatedDate", "") or ""
    repair_date = claim_data.get("RepairDate", "") or claim_data.get("MachineRepairCompletionDate__c", "") or ""
    quantity = claim_data.get("Parts_Requested_Quantity__c", 0) or claim_data.get("PartsRequiredQuantity", 0) or 0

    user_text = f"""
    Analiza las imagenes adjuntas buscando una FACTURA DE COMPRA del componente/parte.

    Informacion del Claim {claim_name}:
    - Parte causal: {causal_part}
    - Código de producto: {product_code}
    - Fecha de instalación de la pieza: {installation_date}
    - Fecha de reparación: {repair_date}
    - Fecha del Claim: {claim_date}
    - Cantidad reclamada: {quantity}

    Evalúa cinco criterios independientes:
    1. El número de parte es legible.
    2. La fecha de compra es legible.
    3. La fecha de compra es anterior a la fecha de instalación/reemplazo y a la fecha de reparación.
    4. La cantidad facturada es legible y coherente con la cantidad reclamada.
    5. La pieza facturada se relaciona con la pieza instalada y reclamada.

    Asigna score = 0.10 multiplicado por criterios cumplidos / 5.
    Devuelve también criteria con estas claves booleanas exactas:
    part_number, purchase_date, before_installation_and_repair, quantity, installed_part_match.
    El score debe ser el valor absoluto entre 0 y 0.10.
    No supongas datos que no sean visibles. Explica criterios cumplidos, faltantes y contradicciones.
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

    result = call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=0.10)
    return score_from_criteria(
        result,
        0.10,
        ["part_number", "purchase_date", "before_installation_and_repair", "quantity", "installed_part_match"],
    )


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
    Categorias: reporte_tecnico, plm, fotografias, analisis_aceite, work_order, purchase_invoice, otro
    """
    if not urls_sas:
        return {"categoria": "otro", "confianza": 0.0, "razon": "Sin URLs"}

    from mr_warranty.core.utils import seleccionar_imagenes_para_ia

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
    - "work_order": Work Order, Service Order, orden de trabajo, repair order
    - "purchase_invoice": Purchase Invoice, factura de compra, invoice de una pieza
    - "otro": Facturas, ordenes de compra, work orders, certificados, cualquier otro documento

    Contexto del Claim:
    - Modelo esperado: {modelo_esperado}
    - Numero de serie esperado: {serial_esperado}

    Responde SOLO un diccionario Python valido con:
    - categoria: una de las 7 opciones más "otro"
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
    correction: str = "",
    component: str = "",
) -> dict:
    """
    Valida que las fotografías correspondan a la queja y causa del reclamo.
    Primera imagen = portada, luego hasta 9 adicionales.
    """
    from mr_warranty.core.utils import seleccionar_imagenes_para_ia

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
    - Corrección: {correction}
    - Componente reclamado: {component}

    Evalúa tres criterios independientes:
    1. Las imágenes muestran realmente el componente reclamado.
    2. Las imágenes evidencian la falla descrita.
    3. Existen evidencias de antes y después de la reparación.

    Asigna score = {ponderacion} multiplicado por criterios cumplidos / 3.
    Si las imágenes son genéricas, ilegibles o no tienen relación, no otorgues ese criterio.
    Devuelve también criteria con estas claves booleanas exactas:
    component_match, failure_evidence, before_after.
    El score debe ser el valor absoluto entre 0 y {ponderacion}.
    Explica en reason qué criterios se cumplieron y cuáles faltaron.
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

    result = call_azure_gpt(messages, deployment="gpt-4.1", max_ponderacion=ponderacion)
    return score_from_criteria(result, ponderacion, ["component_match", "failure_evidence", "before_after"])
