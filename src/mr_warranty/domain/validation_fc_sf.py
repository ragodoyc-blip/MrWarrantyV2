from datetime import timedelta

import pandas as pd

from mr_warranty.core.ponderaciones import PONDERACIONES_STD_SF, PONDERACIONES_FC_SF
from mr_warranty.core.utils import parse_datetime, strip_tz

# ── Ponderacion STD SF ──────────────────────────────────────
_std_within_standard_warranty = PONDERACIONES_STD_SF.get("within_standard_warranty")
_std_repair_deadline = PONDERACIONES_STD_SF.get("repair_deadline")
_std_claim_deadline = PONDERACIONES_STD_SF.get("claim_deadline")

# ── Ponderacion FC SF ───────────────────────────────────────
_fc_fc_expiration = PONDERACIONES_FC_SF.get("fc_expiration")
_fc_repair_deadline = PONDERACIONES_FC_SF.get("repair_deadline")
_fc_claim_deadline = PONDERACIONES_FC_SF.get("claim_deadline")
_fc_technical_report = PONDERACIONES_FC_SF.get("technical_report")
_fc_labor_coverage = PONDERACIONES_FC_SF.get("labor_coverage")
_fc_mileage_coverage = PONDERACIONES_FC_SF.get("mileage_coverage")
_fc_parts_coverage = PONDERACIONES_FC_SF.get("parts_coverage")


def ValidacionFC_SF(Diccionario_Salesforce_Reclamo: dict) -> dict:
    FailureDate__c = strip_tz(parse_datetime(Diccionario_Salesforce_Reclamo.get("FailureDate__c")))
    MachineRepairCompletionDate__c = strip_tz(parse_datetime(Diccionario_Salesforce_Reclamo.get("MachineRepairCompletionDate__c")))
    CreatedDate = strip_tz(parse_datetime(Diccionario_Salesforce_Reclamo.get("CreatedDate")))
    EndDate__c = strip_tz(parse_datetime(Diccionario_Salesforce_Reclamo.get("EndDate__c")))

    # Repair Deadline
    if FailureDate__c is None or MachineRepairCompletionDate__c is None:
        Repair_deadline_reason = "Falta Fecha de Falla o Fecha de Reparación para calcular el plazo de reparación."
        Repair_deadline_score = 0
    else:
        Repair_deadline_days = (MachineRepairCompletionDate__c - FailureDate__c).days
        if Repair_deadline_days >= 30:
            Repair_deadline_reason = f"Fecha Falla - Fecha Reparación = {Repair_deadline_days} dias, excede los 30 días"
            Repair_deadline_score = 0
        else:
            Repair_deadline_reason = f"Fecha Falla - Fecha Reparación = {Repair_deadline_days} dias, no excede los 30 días"
            Repair_deadline_score = _fc_repair_deadline

    # Claim Deadline
    if MachineRepairCompletionDate__c is None or CreatedDate is None:
        Claim_Deadline_reason = "Falta Fecha de Reparación o Fecha de Creación para calcular el plazo del reclamo."
        Claim_Deadline_score = 0
    else:
        Claim_Deadline_days = (CreatedDate - MachineRepairCompletionDate__c).days
        if Claim_Deadline_days <= 30:
            Claim_Deadline_reason = f"Fecha Creación - Fecha Reparación = {Claim_Deadline_days} dias, no excede los 30 días"
            Claim_Deadline_score = _fc_claim_deadline
        else:
            Claim_Deadline_reason = f"Fecha Creación - Fecha Reparación = {Claim_Deadline_days} dias, excede los 30 días"
            Claim_Deadline_score = 0

    # FC Expiration
    if EndDate__c is None or CreatedDate is None:
        fc_expiration_reason = "Falta Fecha de Expiración de Campaña o Fecha de Creación para validar la vigencia de la campaña."
        fc_expiration_score = 0
    else:
        FC_expiration_date = (EndDate__c - CreatedDate).days
        if FC_expiration_date >= 0:
            fc_expiration_reason = "La fecha de creación del Claim es anterior a la fecha de expiración de la campaña"
            fc_expiration_score = _fc_fc_expiration
        else:
            fc_expiration_reason = "La fecha de creación del Claim es posterior a la fecha de expiración de la campaña"
            fc_expiration_score = 0

    return {
        "Repair_deadline_reason": Repair_deadline_reason,
        "Repair_deadline_score": Repair_deadline_score,
        "Claim_Deadline_reason": Claim_Deadline_reason,
        "Claim_Deadline_score": Claim_Deadline_score,
        "FC_expiration_reason": fc_expiration_reason,
        "FC_expiration_score": fc_expiration_score,
    }


def ValidacionCostCoverage_SF(Diccionario_Salesforce_Reclamo: dict) -> dict:
    LaborRequestedQuantity__c = pd.to_numeric(
        Diccionario_Salesforce_Reclamo.get("LaborRequestedQuantity__c"), errors="coerce"
    )
    Labor_Limit_hours__c = pd.to_numeric(
        Diccionario_Salesforce_Reclamo.get("Labor_Limit_hours__c"), errors="coerce"
    )

    # Labor Coverage
    if LaborRequestedQuantity__c > Labor_Limit_hours__c:
        labor_reason = f"Labor solicitada ({LaborRequestedQuantity__c} hrs) excede el límite de la campaña ({Labor_Limit_hours__c} hrs)"
        labor_score = 0
    else:
        labor_reason = f"Labor solicitada ({LaborRequestedQuantity__c} hrs) dentro del límite de la campaña ({Labor_Limit_hours__c} hrs)"
        labor_score = _fc_labor_coverage

    # Parts Claimed
    PartsRequestedQuantity__c = pd.to_numeric(
        Diccionario_Salesforce_Reclamo.get("PartsRequestedQuantity__c"), errors="coerce"
    )
    Parts_Required__c = Diccionario_Salesforce_Reclamo.get("Parts_Required__c")

    if PartsRequestedQuantity__c > 0 and Parts_Required__c == "No":
        parts_reason = f"Hay partes reclamadas ({PartsRequestedQuantity__c} unidades) pero la campaña no las cubre."
        parts_score = 0
    elif PartsRequestedQuantity__c > 0 and Parts_Required__c == "Yes":
        parts_reason = f"Hay partes reclamadas ({PartsRequestedQuantity__c} unidades) y la campaña las cubre."
        parts_score = _fc_parts_coverage
    elif pd.isna(PartsRequestedQuantity__c) or PartsRequestedQuantity__c == 0:
        parts_reason = "No hay partes reclamadas."
        parts_score = _fc_parts_coverage

    # Mileage Coverage
    if Diccionario_Salesforce_Reclamo.get("Mileage__c") is None or Diccionario_Salesforce_Reclamo.get("Mileage__c") == "No":
        mileage_reason = "No hay mileage reclamado."
        mileage_score = _fc_mileage_coverage
    elif Diccionario_Salesforce_Reclamo.get("Mileage__c") == "Yes" and Diccionario_Salesforce_Reclamo.get("Mileage__c_field") == "Yes":
        mileage_reason = "Mileage cubierto por la campaña y solicitado en el reclamo."
        mileage_score = _fc_mileage_coverage
    elif Diccionario_Salesforce_Reclamo.get("Mileage__c") == "Yes" and Diccionario_Salesforce_Reclamo.get("Mileage__c_field") == "No":
        mileage_reason = "Mileage solicitado en el reclamo pero no cubierto por la campaña."
        mileage_score = 0

    return {
        "Labor_reason": labor_reason,
        "Labor_score": labor_score,
        "Parts_reason": parts_reason,
        "Parts_score": parts_score,
        "Mileage_reason": mileage_reason,
        "Mileage_score": mileage_score,
    }


# Claim_Type__c de Factory Warranty sin vigencia aplicable:
# siempre puntaje máximo en within_standard_warranty con razón "No aplica.".
CLAIM_TYPES_SIN_VIGENCIA = frozenset({
    "SK - Repair prior to commissioning",
    "S1 - Standard Warranty",
    "MA - Missing or Damaged Part prior to commissioning",
    "PA - Special Policy",
})

# PA - Special Policy: misma matriz que S1 (within = No aplica) + SPCR informativo 0-1.
CLAIM_TYPE_PA_SPECIAL_POLICY = "PA - Special Policy"


def es_pa_special_policy(claim_type__c: str | None) -> bool:
    """Indica si el reclamo es PA - Special Policy (matriz S1 + SPCR informativo)."""
    return str(claim_type__c or "").strip().lower() == CLAIM_TYPE_PA_SPECIAL_POLICY.lower()

# PC - Part DB Installed: vigencia invertida sobre el equipo.
# El equipo NO debe estar en garantía: dentro de 1 año = 0, sobre 1 año = 100%.
# La vigencia de la pieza la valida Salesforce al crear el claim (no se calcula aquí).
CLAIM_TYPE_PC_DB_INSTALLED = "PC - Part DB Installed"


def es_pc_db_installed(claim_type__c: str | None) -> bool:
    """Indica si el reclamo es PC - Part DB Installed (vigencia invertida + doble factura)."""
    return str(claim_type__c or "").strip().lower() == CLAIM_TYPE_PC_DB_INSTALLED.lower()


def ValidacionStandard(Diccionario_Salesforce_Reclamo: dict, es_pc: bool = False, fecha_instalacion_parte: str = None, claim_type__c: str | None = None, es_pc_db: bool | None = None) -> dict:
    """Validación estándar para los reclamos de Salesforce (Factory Warranty)."""
    FailureDate__c = strip_tz(parse_datetime(Diccionario_Salesforce_Reclamo.get("FailureDate__c")))
    MachineRepairCompletionDate__c = strip_tz(parse_datetime(Diccionario_Salesforce_Reclamo.get("MachineRepairCompletionDate__c")))
    CreatedDate = strip_tz(parse_datetime(Diccionario_Salesforce_Reclamo.get("CreatedDate")))
    MachineCommissionedDate__c = strip_tz(parse_datetime(Diccionario_Salesforce_Reclamo.get("MachineCommissionedDate__c")))

    # Repair Deadline
    if FailureDate__c is None or MachineRepairCompletionDate__c is None:
        Repair_deadline_reason = "Falta Fecha de Falla o Fecha de Reparación para calcular el plazo de reparación."
        Repair_deadline_ponderacion = 0
    else:
        Repair_deadline_days = (MachineRepairCompletionDate__c - FailureDate__c).days
        if Repair_deadline_days >= 30:
            Repair_deadline_reason = f"Fecha Falla - Fecha Reparación = {Repair_deadline_days} dias, excede los 30 días"
            Repair_deadline_ponderacion = 0
        else:
            Repair_deadline_reason = f"Fecha Falla - Fecha Reparación = {Repair_deadline_days} dias, no excede los 30 días"
            Repair_deadline_ponderacion = _std_repair_deadline

    # Claim Deadline
    if MachineRepairCompletionDate__c is None or CreatedDate is None:
        Claim_Deadline_reason = "Falta Fecha de Reparación o Fecha de Creación para calcular el plazo del reclamo."
        Claim_Deadline_ponderacion = 0
    else:
        Claim_deadline_days = (CreatedDate - MachineRepairCompletionDate__c).days
        if Claim_deadline_days <= 30:
            Claim_Deadline_reason = f"Fecha Creación - Fecha Reparación = {Claim_deadline_days} dias, no excede los 30 días"
            Claim_Deadline_ponderacion = _std_claim_deadline
        else:
            Claim_Deadline_reason = f"Fecha Creación - Fecha Reparación = {Claim_deadline_days} dias, excede los 30 días"
            Claim_Deadline_ponderacion = 0

    # Factory Warranty Expiration
    claim_type_norm = (claim_type__c or "").strip()
    es_sin_vigencia = claim_type_norm in CLAIM_TYPES_SIN_VIGENCIA
    if es_pc_db is None:
        es_pc_db = es_pc_db_installed(claim_type__c)
    if es_pc_db:
        # PC - Part DB Installed: el equipo debe estar FUERA de garantía.
        # Dentro de 1 año = 0; sobre 1 año = puntaje máximo.
        if MachineCommissionedDate__c is None or FailureDate__c is None:
            within_standard_warranty_reason = "No hay fecha de puesta en marcha o fecha de falla para validar que el equipo esté fuera de garantía (PC DB Installed)."
            within_standard_warranty_ponderacion = 0
        else:
            within_standard_warranty_days = (FailureDate__c - MachineCommissionedDate__c).days
            if within_standard_warranty_days <= 365:
                within_standard_warranty_reason = f"El equipo está dentro del período de garantía estándar ({within_standard_warranty_days} días); PC DB Installed requiere equipo fuera de garantía."
                within_standard_warranty_ponderacion = 0
            else:
                fecha_expiracion = MachineCommissionedDate__c + timedelta(days=365)
                within_standard_warranty_reason = f"El equipo está fuera del período de garantía estándar (expiró el {fecha_expiracion.strftime('%d/%m/%Y')}); aplica PC DB Installed."
                within_standard_warranty_ponderacion = _std_within_standard_warranty
    elif es_pc and fecha_instalacion_parte:
        # Para PC: 1 año desde la fecha de instalación de la parte
        fecha_inst_dt = parse_datetime(fecha_instalacion_parte)
        if fecha_inst_dt and FailureDate__c:
            within_standard_warranty_days = (FailureDate__c - fecha_inst_dt).days
            if within_standard_warranty_days >= 366:
                fecha_expiracion = fecha_inst_dt + timedelta(days=365)
                within_standard_warranty_reason = f"Expiró la garantía de la parte instalada el {fecha_expiracion.strftime('%d/%m/%Y')}"
                within_standard_warranty_ponderacion = 0
            else:
                within_standard_warranty_reason = f"La parte está dentro del período de garantía de 12 meses (instalada el {fecha_inst_dt.strftime('%d/%m/%Y')})"
                within_standard_warranty_ponderacion = _std_within_standard_warranty
        else:
            within_standard_warranty_reason = "No se pudo determinar la fecha de instalación de la parte."
            within_standard_warranty_ponderacion = 0
    elif es_sin_vigencia:
        within_standard_warranty_reason = "No aplica."
        within_standard_warranty_ponderacion = _std_within_standard_warranty
    elif MachineCommissionedDate__c is None or FailureDate__c is None:
        within_standard_warranty_reason = "No hay fecha de puesta en marcha o fecha de falla para validar la vigencia de la garantía."
        within_standard_warranty_ponderacion = 0
    else:
        within_standard_warranty_days = (FailureDate__c - MachineCommissionedDate__c).days
        if within_standard_warranty_days >= 366:
            fecha_expiracion = MachineCommissionedDate__c + timedelta(days=365)
            within_standard_warranty_reason = f"Expiró la garantía del equipo el {fecha_expiracion.strftime('%d/%m/%Y')}"
            within_standard_warranty_ponderacion = 0
        else:
            within_standard_warranty_reason = "La máquina está dentro del período de garantía estándar de 12 meses."
            within_standard_warranty_ponderacion = _std_within_standard_warranty

    return {
        "within_standard_warranty_reason": within_standard_warranty_reason,
        "within_standard_warranty_ponderacion": within_standard_warranty_ponderacion,
        "Repair_deadline_reason": Repair_deadline_reason,
        "Repair_deadline_ponderacion": Repair_deadline_ponderacion,
        "Claim_Deadline_reason": Claim_Deadline_reason,
        "Claim_Deadline_ponderacion": Claim_Deadline_ponderacion,
    }
