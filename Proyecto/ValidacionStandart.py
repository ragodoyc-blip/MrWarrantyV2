from API_SQIS import getWarrantyclaimid, getwarrantyclaim, getwarrantyclaimdetails, getkom_warrantyclaimworks
from datetime import datetime
from pathlib import Path
from logger import log
from Ponderaciones import PONDERACIONES_STD
import pandas as pd

_STANRATE_PATH = Path(__file__).resolve().parent.parent / "StanRate.xlsx"
stanrate = pd.read_excel(_STANRATE_PATH)

within_standard_warranty = PONDERACIONES_STD.get("within_standard_warranty")
repair_deadline = PONDERACIONES_STD.get("repair_deadline")
claim_deadline = PONDERACIONES_STD.get("claim_deadline")
technical_report = PONDERACIONES_STD.get("technical_report")
invoices = PONDERACIONES_STD.get("invoices")
work_order = PONDERACIONES_STD.get("work_order")
photographs = PONDERACIONES_STD.get("photographs")
standard_rate = PONDERACIONES_STD.get("standard_rate")

from utils import parse_datetime


def ValidacionStandadWC(RFNumber: str):
    DictWarrantyClaim = getwarrantyclaim(RFNumber)

    # Garantia vigente
    Delivery_Date = datetime.strptime(DictWarrantyClaim.get("kom_deliverydate"), "%Y-%m-%d")
    FechacreatedOn = parse_datetime(DictWarrantyClaim.get("createdon"))

    DiasdesdeEntrega = (FechacreatedOn - Delivery_Date).days
    if DiasdesdeEntrega > 365:
        withinstandadwarranty_reason = "Excede los 365 días, no aplica garantía Standard."
        withinstandadwarranty = 0
    else:
        withinstandadwarranty_reason = "Se encuentra en periodo de garantía aún."
        withinstandadwarranty = within_standard_warranty

    # Claim Deadline
    FechaReparación = parse_datetime(DictWarrantyClaim.get("kom_repaircompleteddate"))
    FechacreatedOn = parse_datetime(DictWarrantyClaim.get("createdon"))
    restafechasreparacion = (FechacreatedOn - FechaReparación).days

    if restafechasreparacion > 30:
        log.info("Claim Deadline: %d dias, excede 30", restafechasreparacion)
        Claim_Deadline_ponderacion = 0
        Claim_Deadline_reason = f"Fecha creación - Fecha Reparación = {restafechasreparacion} dias, excede los 30 días"
    else:
        log.info("Claim Deadline: %d dias, OK", restafechasreparacion)
        Claim_Deadline_ponderacion = claim_deadline
        Claim_Deadline_reason = "Ok"

    FechaFalla = parse_datetime(DictWarrantyClaim.get("kom_failuredate"))
    restafechaRepacionyFalla = (FechaReparación - FechaFalla).days

    # Repair Deadline
    if restafechaRepacionyFalla >= 30:
        log.info("Repair Deadline: %d dias, excede 30", restafechaRepacionyFalla)
        Repair_Deadline_ponderacion = 0
        Repair_deadline_reason = f"Fecha Falla - Fecha Reparación = {restafechaRepacionyFalla} dias, excede los 30 días"
    else:
        log.info("Repair Deadline: %d dias, OK", restafechaRepacionyFalla)
        Repair_Deadline_ponderacion = repair_deadline
        Repair_deadline_reason = "Ok"

    return DictWarrantyClaim, {
        "Repair deadline": Repair_Deadline_ponderacion,
        "repair deadline reason": Repair_deadline_reason,
        "Claim deadline": Claim_Deadline_ponderacion,
        "Claim deadline reason": Claim_Deadline_reason,
        "within standard warranty": withinstandadwarranty,
        "within standard warranty reason": withinstandadwarranty_reason,
    }


def ValidacionStandartPartes(RFnumber: str):
    IdReclamo = getWarrantyclaimid(RFnumber)
    df = getwarrantyclaimdetails(IdReclamo)

    df_Parts_Detail_Flag = df[~df["kom_name"].str.contains("FOC Parts", case=False, na=False)]
    df_Parts_Detail_Flag = df_Parts_Detail_Flag[df_Parts_Detail_Flag["kom_name"].str.contains("Parts", case=False, na=False)]
    df_Parts_Detail_Flag = df_Parts_Detail_Flag[["kom_name", "kom_productserialnumber", "kom_offerquantity", "kom_offercost", "kom_distributorcode"]]

    if len(df_Parts_Detail_Flag) == 0:
        return 0
    else:
        return df_Parts_Detail_Flag.to_dict()


def Stanrate(RFnumber: str) -> dict:
    IdReclamo = getWarrantyclaimid(RFnumber)
    df = getkom_warrantyclaimworks(IdReclamo)

    try:
        df_filter = df[df["statuscode"] == 1]
    except Exception as e:
        log.warning("No existe un Claim Job Asociado al reclamo %s: %s", RFnumber, e)
        return {
            "standard_rate": 0,
            "standard_rate_reason": "No hay un claim job asociado al reclamo",
        }

    standard_rate_reason = "No se encontró el código de trabajo en el documento StanRate"

    sumhorasStanrate = 0
    if len(df_filter) == 0:
        return {"standard_rate": 0, "standard_rate_reason": "No hay trabajos registrados"}

    for index, row in df_filter.iterrows():
        Codigo_trabajo = row["kom_operationcode"]
        horasstanrateddocumento = stanrate[stanrate["Job Code"] == Codigo_trabajo]["Standard man hour[H] (Main Job + Related Job)"]
        if not horasstanrateddocumento.empty:
            sumhorasStanrate += horasstanrateddocumento.iloc[0]
        else:
            standard_rate_reason = standard_rate_reason + f" {Codigo_trabajo}"
            return {"standard_rate": 0, "standard_rate_reason": standard_rate_reason}

    df_Labor = getwarrantyclaimdetails(IdReclamo)
    df_Labor = df[df["kom_name"].str.contains("Labor", case=False, na=False)]

    try:
        df_Labor = df_Labor[["kom_name", "kom_offerproductioncost"]]
        df_labor_sum = df_Labor["kom_offerproductioncost"].sum()
    except Exception as e:
        log.warning("No hay costos de mano de obra registrados: %s", e)
        return {"standard_rate": 0, "standard_rate_reason": "No hay costos de mano de obra registrados"}

    if df_labor_sum <= sumhorasStanrate:
        return {"standard_rate": standard_rate, "standard_rate_reason": "El costo de mano de obra está dentro del StanRate"}
    else:
        return {"standard_rate": 0, "standard_rate_reason": "El costo de mano de obra excede el StanRate"}
