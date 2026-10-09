"""
Consulta ClaimCoverage para reclamos específicos de Salesforce.

Uso:
    python tools/consultar_claim_coverage.py
    python tools/consultar_claim_coverage.py 002264 002255 001973 001957
    python tools/consultar_claim_coverage.py --all-fields

Busca Claim por Name y trae todos los ClaimCoverage asociados (no LIMIT 1).
Guarda CSV en data/ y muestra tabla en consola.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

# Asegurar que src esté en path si se ejecuta como script suelto
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.adapters.salesforce_client import connect_salesforce
from mr_warranty.core.logger import log

DEFAULT_CLAIMS = ["002264", "002255", "001973", "001957"]

CAMPOS_CLAIM = ["Id", "Name", "Status", "ClaimType", "TSINumber__c", "CreatedDate", "Servicing_Distributor__c"]
CAMPOS_COVERAGE = [
    "Id", "ClaimId", "Claim.Name", "CoverageType", "Claim_Type__c",
    "CausalPart__c", "Parts_Requested_Quantity__c", "Parts_Requested_Amount__c",
    "Labor_Requested_Quantity__c", "Labor_Requested_Amount__c",
]


def fetch_claims(sf, claim_names: list[str]) -> pd.DataFrame:
    names_in = "', '".join(claim_names)
    query = f"SELECT {', '.join(CAMPOS_CLAIM)} FROM Claim WHERE Name IN ('{names_in}')"
    log.info("SOQL Claim: %s", query)
    data = sf.query_all(query)
    df = pd.DataFrame(data["records"]).drop(columns="attributes", errors="ignore")
    return df


def fetch_coverages(sf, claim_ids: list[str], claim_names: list[str], all_fields: bool = False) -> pd.DataFrame:
    if not claim_ids:
        return pd.DataFrame()

    # Usar Claim.Name para legibilidad, pero filtrar por ClaimId es más robusto
    ids_in = "', '".join(claim_ids)

    if all_fields:
        # Traer todos los campos via describe (útil para descubrir campos extra)
        meta = sf.__getattr__("ClaimCoverage").describe()
        campos = [f["name"] for f in meta["fields"]]
        campos_str = ", ".join(campos)
    else:
        campos_str = ", ".join(CAMPOS_COVERAGE)

    query = f"SELECT {campos_str} FROM ClaimCoverage WHERE ClaimId IN ('{ids_in}')"
    # Fallback por si ClaimId no trae nada (ej. permisos), intentar via Claim.Name
    log.info("SOQL ClaimCoverage: %s", query)
    data = sf.query_all(query)
    records = data.get("records", [])

    # Si no hay registros por Id, intentar por Name (algunas orgs usan relación distinta)
    if not records:
        names_in = "', '".join(claim_names)
        query2 = f"SELECT {campos_str} FROM ClaimCoverage WHERE Claim.Name IN ('{names_in}')"
        log.info("SOQL ClaimCoverage (fallback Name): %s", query2)
        data = sf.query_all(query2)
        records = data.get("records", [])

    df = pd.DataFrame(records).drop(columns="attributes", errors="ignore")

    # Aplanar Claim.Name si viene como dict
    if "Claim" in df.columns:
        df["Claim_Name"] = df["Claim"].apply(lambda x: x.get("Name") if isinstance(x, dict) else x)
    return df


def main():
    parser = argparse.ArgumentParser(description="Consulta ClaimCoverage para reclamos")
    parser.add_argument("claims", nargs="*", default=DEFAULT_CLAIMS, help="Nombres de Claim (ej. 002264)")
    parser.add_argument("--all-fields", action="store_true", help="Trae todos los campos de ClaimCoverage (describe)")
    parser.add_argument("--csv", type=str, default="", help="Ruta CSV salida (default: data/claim_coverage_<nombres>.csv)")
    args = parser.parse_args()

    claim_names = [c.strip() for c in args.claims if c.strip()]
    if not claim_names:
        claim_names = DEFAULT_CLAIMS

    print(f"\n=== CONSULTA CLAIM COVERAGE ===")
    print(f"Reclamos: {', '.join(claim_names)}\n")

    sf = connect_salesforce()

    # 1. Claims
    df_claim = fetch_claims(sf, claim_names)
    if df_claim.empty:
        print(f"[WARN] No se encontraron Claims con Name IN {claim_names}")
        # Intentar LIKE por si tienen prefijo distinto
        log.warning("Sin resultados exactos, probando LIKE")
        for name in claim_names:
            q = f"SELECT {', '.join(CAMPOS_CLAIM)} FROM Claim WHERE Name LIKE '%{name}%' LIMIT 5"
            data = sf.query_all(q)
            df_like = pd.DataFrame(data["records"]).drop(columns="attributes", errors="ignore")
            if not df_like.empty:
                print(f"  LIKE '%{name}%':")
                print(df_like.to_string(index=False))
        return

    print(f"--- CLAIMS ({len(df_claim)}) ---")
    print(df_claim.to_string(index=False))
    print()

    # 2. Coverages
    claim_ids = df_claim["Id"].dropna().unique().tolist()
    df_cov = fetch_coverages(sf, claim_ids, claim_names, all_fields=args.all_fields)

    if df_cov.empty:
        print(f"[INFO] No se encontraron ClaimCoverage para Claims {claim_names} (Ids: {claim_ids})")
        # Mostrar qué Claims sí existen pero sin coverage
        for _, row in df_claim.iterrows():
            print(f"  Claim {row['Name']} ({row['Id']}) -> sin ClaimCoverage")
        return

    # Ordenar por Claim.Name
    sort_col = "Claim_Name" if "Claim_Name" in df_cov.columns else ("ClaimId" if "ClaimId" in df_cov.columns else df_cov.columns[0])
    df_cov = df_cov.sort_values(by=sort_col)

    print(f"--- CLAIM COVERAGE ({len(df_cov)} registros) ---")
    # Mostrar columnas legibles
    cols_show = [c for c in ["Claim_Name", "CoverageType", "Claim_Type__c", "CausalPart__c", "Parts_Requested_Quantity__c", "Parts_Requested_Amount__c", "Id", "ClaimId"] if c in df_cov.columns]
    if cols_show:
        print(df_cov[cols_show].to_string(index=False))
    else:
        print(df_cov.to_string(index=False))
    print()

    # Resumen por reclamo
    print("--- RESUMEN POR RECLAMO ---")
    for name in claim_names:
        # Filtrar por Claim_Name o ClaimId
        if "Claim_Name" in df_cov.columns:
            sub = df_cov[df_cov["Claim_Name"] == name]
        else:
            # mapear Id -> Name
            id_map = dict(zip(df_claim["Id"], df_claim["Name"]))
            sub = df_cov[df_cov["ClaimId"].map(id_map) == name]
        if sub.empty:
            print(f"  {name}: 0 coverages")
        else:
            print(f"  {name}: {len(sub)} coverage(s)")
            for _, r in sub.iterrows():
                print(f"    - CoverageType={r.get('CoverageType','')} | Claim_Type__c={r.get('Claim_Type__c','')} | CausalPart={r.get('CausalPart__c','')} | Qty={r.get('Parts_Requested_Quantity__c','')} | Amt={r.get('Parts_Requested_Amount__c','')}")

    # Guardar CSV
    if args.csv:
        out_path = Path(args.csv)
    else:
        out_path = REPO_ROOT / "data" / f"claim_coverage_{'_'.join(claim_names)}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_cov.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n[OK] CSV guardado: {out_path}")

    # También guardar claims para referencia
    claims_csv = out_path.with_name(out_path.stem + "_claims.csv")
    df_claim.to_csv(claims_csv, index=False, encoding="utf-8-sig")
    print(f"[OK] Claims CSV: {claims_csv}")


if __name__ == "__main__":
    main()
