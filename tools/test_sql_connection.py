"""
Prueba de conexión SQL y estructura de tablas.
"""

import pyodbc
from mr_warranty.config.config import SQL_DRIVER, SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD


def get_connection_string():
    return (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def test_connection():
    """Prueba la conexión a SQL Server."""
    print("\n=== Prueba de Conexion SQL ===\n")
    
    try:
        conn = pyodbc.connect(get_connection_string())
        print("[OK] Conexion exitosa")
        
        cursor = conn.cursor()
        
        # Verificar tablas
        print("\n--- Tablas en el esquema dbo ---")
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA = 'dbo' 
            AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """)
        for row in cursor.fetchall():
            print(f"  - {row[0]}")
        
        # Verificar estructura de reclamos_procesados
        print("\n--- Columnas de dbo.reclamos_procesados ---")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'reclamos_procesados'
            AND TABLE_SCHEMA = 'dbo'
            ORDER BY ORDINAL_POSITION
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]:40} {row[1]:20} {'NULL' if row[2] == 'YES' else 'NOT NULL'}")
        
        # Verificar estructura de ponderaciones
        print("\n--- Columnas de dbo.ponderaciones ---")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'ponderaciones'
            AND TABLE_SCHEMA = 'dbo'
            ORDER BY ORDINAL_POSITION
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]:40} {row[1]:20} {'NULL' if row[2] == 'YES' else 'NOT NULL'}")
        
        # Contar registros en ponderaciones
        print("\n--- Registros en dbo.ponderaciones ---")
        cursor.execute("SELECT grupo, COUNT(*) as total FROM ponderaciones GROUP BY grupo ORDER BY grupo")
        for row in cursor.fetchall():
            print(f"  {row[0]:20} {row[1]} registros")
        
        conn.close()
        print("\n[OK] Pruebas completadas")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")


if __name__ == "__main__":
    test_connection()
