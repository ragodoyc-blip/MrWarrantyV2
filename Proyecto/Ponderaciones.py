# Archivo de configuración para centralizar las ponderaciones

PONDERACIONES_FC = {
    "fc_expiration": 0.2,
    "repair_deadline": 0.05,
    "claim_deadline": 0.2,
    "technical_report": 0.05,
    "invoices": 0.15,
    "work_order": 0.05,
    "photographs": 0.15,
    "labor_coverage": 0.05,
    "mileage_coverage": 0.05,
    "other_expenses_coverage": 0.05,
}

PONDERACIONES_STD = {
    "within_standard_warranty": 0.15,
    "repair_deadline": 0.15,
    "claim_deadline": 0.15,
    "technical_report": 0.15,
    "invoices": 0.10,
    "work_order": 0.05,
    "photographs": 0.10,
    "standard_rate": 0.15
}

PONDERACIONES_STD_SF =  {
    "within_standard_warranty": 0.15,
    "repair_deadline": 0.15,
    "claim_deadline": 0.15,
    "technical_report": 0.20,
    "photographs": 0.0,
    "plm": 0.05,
    "analisis_aceite": 0.05,
    "datapacks": 0.05,
    "work_order": 0.10,
    "purchase_invoice": 0.10,
}

PONDERACIONES_STD_SF_PC = {
    "within_standard_warranty": 0.15,
    "repair_deadline": 0.15,
    "claim_deadline": 0.15,
    "technical_report": 0.20,
    "photographs": 0.0,
    "plm": 0.05,
    "analisis_aceite": 0.05,
    "datapacks": 0.05,
    "work_order": 0.10,
    "purchase_invoice": 0.10,
}

PONDERACIONES_FC_SF = {
    "fc_expiration": 0.2,
    "repair_deadline": 0.05,
    "claim_deadline": 0.2,
    "technical_report": 0.1,
    "labor_coverage": 0.05,
    "mileage_coverage": 0.05,
    "other_expenses_coverage": 0.05,
    "parts_coverage": 0.1
}



Ajuste_Parts = {
  "211A": 1.68,
  "2125": 1.48,
  "215A": 1.45,
  "2161": 1.34,
  "2181": 1.49,
  "2195": 1.39,
  "2208": 1.80,
  "2213": 1.22,
  "2221": 1.67,
  "2241": 1.72,
  "225K": 1.38,
  "2264": 1.3172,
  "2278": 1.37,
  "2279": 1.37,
  "2281": 1.43,
  "2297": 1.42,
  "2303": 1.96,
  "2304": 1.96,
  "231C": 1.79,
  "232A": 1.16,
  "2323": 1.45,
  "2362": 1.70,
  "214B": 1.0075,
  "9463": 0.7022
}

# PONDERACIONES_SF_ATTACHMENTS eliminada - usar PONDERACIONES_STD_SF
