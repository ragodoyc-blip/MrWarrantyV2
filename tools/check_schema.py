import os
from pathlib import Path
from dotenv import load_dotenv
import pyodbc

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
SCHEMA = "free-sql-db-3266075"

if not (SQL_SERVER and SQL_USERNAME and SQL_PASSWORD and SQL_DATABASE):
    print("Missing SQL config in .env")
    raise SystemExit(1)

conn_str = (
    f"DRIVER={{{SQL_DRIVER}}};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE=master;"
    f"UID={SQL_USERNAME};"
    f"PWD={SQL_PASSWORD};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)

try:
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()
    sql = f"SELECT COUNT(*) FROM [{SQL_DATABASE}].sys.schemas WHERE name = ?"
    cursor.execute(sql, SCHEMA)
    row = cursor.fetchone()
    count = row[0] if row else 0
    if count and count > 0:
        print(f"EXISTS")
    else:
        print(f"NOT FOUND")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"ERROR: {e}")
    raise
