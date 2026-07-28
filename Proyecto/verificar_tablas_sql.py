"""
Verificar tablas y datos en SQL Server.
"""

import pyodbc
from config import SQL_DRIVER, SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD


def get_conn():
    conn_str = (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def verificar():
    conn = get_conn()
    cursor = conn.cursor()

    # 1. Ver esquema de las tablas
    print("=== ESQUEMA DE TABLAS ===")
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME IN ('reclamos_procesados', 'ponderaciones')
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}.{row[1]}")

    # 2. Verificar reclamos_procesados
    print("\n=== RECLAMOS_PROCESADOS ===")
    cursor.execute("SELECT COUNT(*) FROM reclamos_procesados")
    count = cursor.fetchone()[0]
    print(f"Total registros: {count}")

    cursor.execute("""
        SELECT TOP 5 claim_number, plataforma, status, tipo_garantia,
               ISNULL(repair_deadline,0), ISNULL(attachments_plm,0)
        FROM reclamos_procesados
        ORDER BY claim_number
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]} | Repair={row[4]} | PLM={row[5]}")

    # 3. Verificar ponderaciones
    print("\n=== PONDERACIONES ===")
    cursor.execute("SELECT COUNT(*) FROM ponderaciones")
    count = cursor.fetchone()[0]
    print(f"Total registros: {count}")

    cursor.execute("""
        SELECT TOP 10 grupo, categoria, ponderacion, descripcion
        FROM ponderaciones
        ORDER BY grupo, categoria
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]} | {row[1]} | {row[2]} | {row[3]}")

    # 4. Verificar columnas nuevas
    print("\n=== COLUMNAS DE ADJUNTOS EN reclamos_procesados ===")
    cursor.execute("""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'reclamos_procesados' 
        AND COLUMN_NAME LIKE 'attachments%'
        ORDER BY COLUMN_NAME
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}")

    conn.close()
    print("\n=== VERIFICACION COMPLETADA ===")


if __name__ == "__main__":
    verificar()
