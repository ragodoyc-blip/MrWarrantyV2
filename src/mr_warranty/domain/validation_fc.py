from mr_warranty.adapters.sqis_client import getWarrantyclaimid, getwarrantyclaim, getwarrantyclaimdetails
from mr_warranty.adapters.sqis_fc_client import get_fc_master, get_service_news, Partes_presentes
from mr_warranty.config.config import SQIS_DETAIL_TYPE_FOC
from mr_warranty.core.logger import log
from mr_warranty.core.ponderaciones import PONDERACIONES_FC
from mr_warranty.core.utils import parse_datetime

FC_expiration = PONDERACIONES_FC.get("fc_expiration")
Repair_deadline = PONDERACIONES_FC.get("repair_deadline")
Claim_Deadline = PONDERACIONES_FC.get("claim_deadline")
labor_coverage = PONDERACIONES_FC.get("labor_coverage")
mileage_coverage = PONDERACIONES_FC.get("mileage_coverage")
other_expenses_coverage = PONDERACIONES_FC.get("other_expenses_coverage")


def DatosGeneralesCampana(RFnumber: str):
    IdReclamo = getWarrantyclaimid(RFnumber)
    DictWarrantyClaim = getwarrantyclaim(RFnumber)

    NumeroCampana = DictWarrantyClaim.get("kom_servicenewsnumbertext")
    ServiceNewsNumber = DictWarrantyClaim.get("kom_servicenewsnumbertext")
    DictFC = get_fc_master(NumeroCampana)
    if ServiceNewsNumber is None and DictFC is not None:
        ServiceNewsNumber = DictFC.get("kom_servicenewsnumbertext")

    log.info("DatosGeneralesCampana - Reclamo: %s, ServiceNews: %s", RFnumber, ServiceNewsNumber)

    return RFnumber, IdReclamo, ServiceNewsNumber, DictFC


def ValidacionCampanaGeneral(RFNumber: str, ServiceNewsNumber: str, DictFc: dict):
    DictWarrantyClaim = getwarrantyclaim(RFNumber)
    DictPSN = get_service_news(ServiceNewsNumber)

    FechaReparación = parse_datetime(DictWarrantyClaim.get("kom_repaircompleteddate"))
    FechacreatedOn = parse_datetime(DictWarrantyClaim.get("createdon"))
    restafechasreparacion = (FechacreatedOn - FechaReparación).days

    # Claim Deadline
    if restafechasreparacion > 30:
        log.info("Claim Deadline: %d dias, excede 30", restafechasreparacion)
        Claim_Deadline_ponderacion = 0
        Claim_Deadline_reason = f"Fecha Creación - Fecha Reparación = {restafechasreparacion} dias, excede los 30 días"
    else:
        log.info("Claim Deadline: %d dias, OK", restafechasreparacion)
        Claim_Deadline_ponderacion = Claim_Deadline
        Claim_Deadline_reason = f"Fecha Creación - Fecha Reparación = {restafechasreparacion} dias, no excede los 30 días"

    FechaFalla = parse_datetime(DictWarrantyClaim.get("kom_failuredate"))
    restafechaRepacionyFalla = (FechaReparación - FechaFalla).days

    # Repair Deadline
    if restafechaRepacionyFalla >= 30:
        log.info("Repair Deadline: %d dias, excede 30", restafechaRepacionyFalla)
        Repair_Deadline_ponderacion = 0
        Repair_deadline_reason = f"Fecha Falla - Fecha Reparación = {restafechaRepacionyFalla} dias, excede los 30 días"
    else:
        log.info("Repair Deadline: %d dias, OK", restafechaRepacionyFalla)
        Repair_Deadline_ponderacion = Repair_deadline
        Repair_deadline_reason = "Ok"

    # FC Expiration
    if DictPSN is None:
        ValueFechaCierreCampaña = DictFc.get("kom_processingdeadline")
    else:
        ValueFechaCierreCampaña = DictPSN.get("kom_inputdeadlineoverseas")
    FechaCierreCampaña = parse_datetime(ValueFechaCierreCampaña)
    restafechacierrecampana = (FechaCierreCampaña - FechacreatedOn).days

    if restafechacierrecampana >= 0:
        log.info("FC Expiration: Campana vigente, cierre: %s", FechaCierreCampaña)
        fc_expiration_ponderacion = FC_expiration
        fc_expiration_reason = "Ok"
    else:
        log.info("FC Expiration: Campana cerrada en %s", FechaCierreCampaña)
        fc_expiration_ponderacion = 0
        fc_expiration_reason = f"Campana cerrada con fecha: {FechaCierreCampaña}"

    return DictWarrantyClaim, {
        "FC expiration": fc_expiration_ponderacion,
        "FC expiration reason": fc_expiration_reason,
        "Repair deadline": Repair_Deadline_ponderacion,
        "repair deadline reason": Repair_deadline_reason,
        "Claim deadline": Claim_Deadline_ponderacion,
        "Claim deadline reason": Claim_Deadline_reason,
    }


def ValidacionCampanaPartes(IdReclamo: str, ServiceNewsNumber: str):
    df = getwarrantyclaimdetails(IdReclamo)

    if df.empty:
        log.warning("No se encontraron detalles para reclamo %s", IdReclamo)
        return {}

    df_FOC = df[df["kom_detailtype"] == SQIS_DETAIL_TYPE_FOC]
    df_Parts_Detail_Flag = df[~df["kom_name"].str.contains("FOC Parts", case=False, na=False)]
    df_Parts_Detail_Flag = df_Parts_Detail_Flag[df_Parts_Detail_Flag["kom_name"].str.contains("Parts", case=False, na=False)]
    df_Parts_Detail_Flag = df_Parts_Detail_Flag[["kom_name", "kom_productserialnumber", "kom_offerquantity", "kom_offerprice"]]

    NumeroFOCParts = len(df_FOC)
    if NumeroFOCParts > 0:
        log.info("FOC Parts presentes: %d", NumeroFOCParts)
    else:
        log.info("No hay FOC Parts")

    if len(df_Parts_Detail_Flag) > 0:
        Partes_PSN = Partes_presentes(ServiceNewsNumber)
        if Partes_PSN is None:
            log.warning("No se encontró asignación entre PSN y FC")
            return {}
        elif len(Partes_PSN) > 0:
            reclamo_tuplas = list(df_Parts_Detail_Flag[["kom_productserialnumber", "kom_offerquantity"]].itertuples(index=False, name=None))
            psn_tuplas = list(Partes_PSN[["kom_newpartnumber", "kom_partsquantity"]].itertuples(index=False, name=None))

            no_encontradas = [x for x in reclamo_tuplas if x not in psn_tuplas]

            if not no_encontradas:
                log.info("Todas las partes y cantidades coinciden con PSN")
            else:
                log.warning("Partes que no coinciden con PSN: %s", no_encontradas)
            return df_Parts_Detail_Flag
        else:
            log.warning("No hay partes disponibles en PSN para esta campaña")
            return {}
    else:
        log.info("No hay partes presentadas en el reclamo para procesar")
        return {}


def ValidacionCostCoverage(IdReclamo: str, ServiceNewsNumber: str, DictFc: dict):
    log.info("Procesando horas Labor en el reclamo %s", IdReclamo)

    df = getwarrantyclaimdetails(IdReclamo)

    if df.empty:
        log.warning("No se encontraron detalles de costos para reclamo %s", IdReclamo)
        return {
            "Labor Score": labor_coverage,
            "Labor Reason": "No hay datos de costos disponibles",
            "Other Expenses Score": other_expenses_coverage,
            "Other Expenses Reason": "No hay datos de costos disponibles",
            "Mileage Score": mileage_coverage,
            "Mileage Reason": "No hay datos de costos disponibles",
        }

    df_Labor = df[df["kom_name"].str.contains("Labor", case=False, na=False)]
    df_Labor = df_Labor[["kom_name", "kom_offerproductioncost"]]
    Count_RegistrosLabor = len(df_Labor)

    if Count_RegistrosLabor == 0:
        Ponderacion_Labor = labor_coverage
        Ponderacion_Labor_reason = "No hay horas de labor declaradas en el reclamo"
    else:
        sum_hours = df_Labor["kom_offerproductioncost"].sum()
        Horas_PSN = get_service_news(ServiceNewsNumber)
        if Horas_PSN is None:
            Horas_Distribuidor = DictFc.get("kom_standardworkunit")
        else:
            Horas_Distribuidor = Horas_PSN.get("kom_bydistributor")
        if Horas_Distribuidor is None:
            Horas_Distribuidor = Horas_PSN.get("kom_byplant")

        if sum_hours == Horas_Distribuidor:
            Ponderacion_Labor = labor_coverage
            Ponderacion_Labor_reason = "Horas declaradas en PSN coinciden con reclamo"
        else:
            Ponderacion_Labor = 0
            Ponderacion_Labor_reason = f"Horas PSN ({Horas_Distribuidor}) != Horas Reclamo ({sum_hours})"

    # Other Expenses
    df_OtherExpenses = df[df["kom_name"].str.contains("Other Expense", case=False, na=False)]
    Count_RegistrosOtherExpenses = len(df_OtherExpenses)
    if Count_RegistrosOtherExpenses == 0:
        Ponderacion_OtherExpenses = other_expenses_coverage
        Ponderacion_OtherExpenses_reason = "No hay Other Expenses declaradas en el reclamo"
    else:
        OtherExpenses_PSN = get_service_news(ServiceNewsNumber)
        if OtherExpenses_PSN is None:
            OtherExpenses_PSN_val = DictFc.get("kom_otherexpenses")
        else:
            OtherExpenses_PSN_val = OtherExpenses_PSN.get("kom_otherexpenses")
        if OtherExpenses_PSN_val is True:
            Ponderacion_OtherExpenses = other_expenses_coverage
            Ponderacion_OtherExpenses_reason = "PSN declara Other Expenses"
        else:
            Ponderacion_OtherExpenses = 0
            Ponderacion_OtherExpenses_reason = "PSN no declara Other Expenses y en reclamo si"

    # Mileage
    df_Mileage = df[df["kom_name"].str.contains("Mileage", case=False, na=False)]
    Count_RegistrosMileage = len(df_Mileage)
    if Count_RegistrosMileage == 0:
        Ponderacion_Mileage = mileage_coverage
        Ponderacion_Mileage_reason = "No hay Mileage declaradas en el reclamo"
    else:
        Mileage_PSN = get_service_news(ServiceNewsNumber)
        if Mileage_PSN is None:
            Mileage_PSN_val = DictFc.get("kom_mileage")
        else:
            Mileage_PSN_val = Mileage_PSN.get("kom_mileage")

        if Mileage_PSN_val is True:
            Ponderacion_Mileage = mileage_coverage
            Ponderacion_Mileage_reason = "PSN declara Mileage"
        else:
            Ponderacion_Mileage = 0
            Ponderacion_Mileage_reason = "PSN no declara Mileage y en reclamo si"

    return {
        "Labor Score": Ponderacion_Labor,
        "Labor Reason": Ponderacion_Labor_reason,
        "Other Expenses Score": Ponderacion_OtherExpenses,
        "Other Expenses Reason": Ponderacion_OtherExpenses_reason,
        "Mileage Score": Ponderacion_Mileage,
        "Mileage Reason": Ponderacion_Mileage_reason,
    }
