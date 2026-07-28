import pandas as pd
import pyodbc
from pathlib import Path

from sql_storage import bulk_upsert_reclamos, _connection_string


def main():
    csv_path = Path(__file__).resolve().parent.parent / "Mr-Warranty-KHSA (1).csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV no encontrado: {csv_path}")

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    records = df.where(pd.notna(df), None).to_dict(orient="records")

    processed = bulk_upsert_reclamos(records)

    with pyodbc.connect(_connection_string()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM dbo.reclamos_procesados")
        total_db = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM dbo.reclamos_procesados WHERE plataforma = ?", "SQIS")
        total_sqis = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM dbo.reclamos_procesados WHERE plataforma = ?", "Salesforce")
        total_sf = cur.fetchone()[0]

    print(f"Rows in CSV: {len(df)}")
    print(f"Rows processed: {processed}")
    print(f"Total rows in DB: {total_db}")
    print(f"Rows in DB SQIS: {total_sqis}")
    print(f"Rows in DB Salesforce: {total_sf}")


if __name__ == "__main__":
    main()
