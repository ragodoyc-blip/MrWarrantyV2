"""
Backfill de columnas modelo y serial_number para registros Salesforce existentes.
Procesa TODOS los Claims de Salesforce (cualquier tipo_garantia).
"""
import sys
import pyodbc

sys.path.insert(0, r'C:\Users\Komatsu\OneDrive - Komatsu Ltd\Documents\Python\002 Mr. Warranty\Proyecto')

from config import SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD, SQL_DRIVER
from API_Salesforce import connect_salesforce, obtener_modelo_serial_tsi
from logger import log


def _connect_sql():
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


def main():
    log.info("=" * 60)
    log.info("BACKFILL: modelo y serial_number")
    log.info("=" * 60)

    sf = connect_salesforce()
    log.info("Conexion Salesforce OK")

    conn = _connect_sql()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT claim_number
        FROM mr_warranty.reclamos_procesados
        WHERE plataforma = 'Salesforce'
        AND (modelo IS NULL OR modelo = '' OR serial_number IS NULL OR serial_number = '')
        ORDER BY claim_number
    """)
    claims = [row[0] for row in cursor.fetchall()]
    log.info("Claims Salesforce a actualizar: %d", len(claims))

    if not claims:
        log.info("No hay Claims para actualizar. Saliendo.")
        return

    actualizados = 0
    sin_tsi = 0
    errores = 0

    for i, claim_number in enumerate(claims, 1):
        try:
            query_claim = f"SELECT TSINumber__c FROM Claim WHERE Name = '{claim_number}'"
            data = sf.query(query_claim)
            records = data.get("records", [])

            if not records:
                log.warning("[%d/%d] %s: Claim no encontrado en Salesforce", i, len(claims), claim_number)
                errores += 1
                continue

            tsi_id = records[0].get("TSINumber__c")

            if not tsi_id:
                log.info("[%d/%d] %s: sin TSI asociado", i, len(claims), claim_number)
                sin_tsi += 1
                continue

            modelo_serial = obtener_modelo_serial_tsi(tsi_id)
            modelo = modelo_serial.get("modelo", "")
            serial = modelo_serial.get("serial", "")

            cursor.execute("""
                UPDATE mr_warranty.reclamos_procesados
                SET modelo = ?, serial_number = ?, updated_at = SYSUTCDATETIME()
                WHERE claim_number = ? AND plataforma = 'Salesforce'
            """, modelo, serial, claim_number)

            if cursor.rowcount > 0:
                actualizados += 1
                log.info("[%d/%d] %s: modelo='%s', serial='%s'",
                         i, len(claims), claim_number, modelo, serial)

            if i % 10 == 0:
                conn.commit()
                log.info("Checkpoint: %d/%d procesados (%d OK, %d sin TSI, %d errores)",
                         i, len(claims), actualizados, sin_tsi, errores)

        except Exception as e:
            errores += 1
            log.error("[%d/%d] %s: %s", i, len(claims), claim_number, e)
            continue

    conn.commit()
    conn.close()

    log.info("=" * 60)
    log.info("BACKFILL COMPLETADO")
    log.info("  Total procesados:    %d", len(claims))
    log.info("  Actualizados:        %d", actualizados)
    log.info("  Sin TSI asociado:    %d", sin_tsi)
    log.info("  Errores:             %d", errores)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
