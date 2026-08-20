import os
import sys
from pathlib import Path
import pandas as pd
import pyodbc
from dotenv import load_dotenv

# Cargar .env de la carpeta Proyecto
HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

EXCEL_PATH = HERE.parent / "Reclamos_Procesados.xlsx"
DB_NAME = "free-sql-db-3266075"
SCHEMA_NAME = "mr_warranty"

def _conn_string_for(database):
    driver = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server").strip()
    server = os.getenv("SQL_SERVER", "").strip()
    username = os.getenv("SQL_USERNAME", "").strip()
    password = os.getenv("SQL_PASSWORD", "").strip()
    if not server or not username or not password:
        raise ValueError("Faltan variables SQL_SERVER, SQL_USERNAME o SQL_PASSWORD en entorno/.env")

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def ensure_schema_exists():
    if not DB_NAME:
        raise ValueError("SQL_DATABASE no está configurada en el entorno/.env")
    # Conectar a 'master' y ejecutar CREATE SCHEMA en el contexto de la BD objetivo
    # usando SQL dinámico con identificadores entre corchetes para evitar errores
    # con guiones u otros caracteres especiales.
    conn = pyodbc.connect(_conn_string_for('master'), autocommit=True)
    cursor = conn.cursor()
    # Construir SQL dinámico seguro: usamos EXEC con un literal que contiene USE [DB]; ...
    sql = (
        "EXEC('USE [" + DB_NAME.replace("']", "'' ]") + "]; "
        "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N''" + SCHEMA_NAME.replace("'", "''") + "'') "
        "CREATE SCHEMA [" + SCHEMA_NAME.replace("]", "]]") + "]')"
    )
    try:
        cursor.execute(sql)
    finally:
        cursor.close()
        conn.close()

    print(f"Schema '{SCHEMA_NAME}' garantizado en BD '{DB_NAME}' (creado si no existía).")


def import_excel_to_sql():
    print(f"Inicio import: Excel={EXCEL_PATH}, DB={DB_NAME}, schema={SCHEMA_NAME}")
    if not EXCEL_PATH.exists():
        print(f"No existe el archivo Excel en: {EXCEL_PATH}")
        sys.exit(1)

    df = pd.read_excel(EXCEL_PATH)
    records = df.to_dict(orient='records')

    # Asegurar columnas mínimas
    sample = records[0] if records else None
    if sample is None:
        print("Excel vacío: no hay registros para importar.")
        return

    if 'ClaimNumber' not in df.columns and 'claim_number' in df.columns:
        # normalizar nombre
        df = df.rename(columns={'claim_number': 'ClaimNumber'})
        records = df.to_dict(orient='records')

    if 'ClaimNumber' not in df.columns:
        print("El Excel no contiene la columna 'ClaimNumber' necesaria.")
        sys.exit(1)

    # El usuario creó el schema manualmente; no intentamos crearlo desde el script.
    print("Saltando creación de schema (asumido creado por el usuario).")

    # Asegurarse de que usamos la BD objetivo para sql_storage
    os.environ['SQL_DATABASE'] = DB_NAME

    try:
        print("Importando registros a SQL...")
        import sql_storage

        # Forzar que sql_storage use el schema.table adecuado
        sql_storage.TABLE_NAME = f"{SCHEMA_NAME}.reclamos_procesados"

        # Crear la tabla si no existe usando la función existente
        try:
            print("Ejecutando ensure_sql_schema() para crear tabla si hace falta...")
            sql_storage.ensure_sql_schema()
            print("ensure_sql_schema() ejecutado.")
        except Exception as e:
            print(f"Advertencia: no se pudo ejecutar ensure_sql_schema(): {e}")

        print(f"Subiendo {len(records)} registros...")
        total = sql_storage.bulk_upsert_reclamos(records)
        print(f"Importación completada: {total} registros subidos a {DB_NAME}.{SCHEMA_NAME}.reclamos_procesados")
    except Exception as e:
        print(f"Error al importar a SQL: {type(e).__name__}: {e}")
        raise


if __name__ == '__main__':
    import_excel_to_sql()
