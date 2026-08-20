"""
Verificar datos en mr_warranty schema.
"""

import pyodbc
from mr_warranty.config.config import SQL_DRIVER, SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD


def get_conn():
    return pyodbc.connect(
        f"DRIVER={{{SQL_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};PWD={SQL_PASSWORD};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


def main():
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 80)
    print("mr_warranty.reclamos_procesados - Registros Salesforce (EDT Factory Warranty)")
    print("=" * 80)
    print()

    cur.execute("""
        SELECT 
            claim_number,
            status,
            tipo_garantia,
            ISNULL(repair_deadline, 0) as repair,
            ISNULL(claim_deadline, 0) as claim_dl,
            ISNULL(within_standard_warranty, 0) as warranty,
            ISNULL(root_cause_analysis, 0) as root_cause,
            ISNULL(attachments_plm, 0) as plm,
            ISNULL(attachments_oil_analysis, 0) as oil,
            ISNULL(attachments_datapacks, 0) as datapacks,
            ISNULL(attachments_technical_report_sf, 0) as tr,
            ISNULL(attachments_photographs_sf, 0) as photos
        FROM mr_warranty.reclamos_procesados
        WHERE plataforma = 'Salesforce'
        AND claim_number IN ('001954', '001972', '001982', '001985', '001992', '002001', '002003')
        ORDER BY claim_number
    """)

    print(f"{'Claim':<10} {'Repair':<8} {'ClaimDL':<8} {'Warranty':<8} {'Root':<8} {'PLM':<6} {'Oil':<6} {'Data':<6} {'TR':<6} {'Photos':<6}")
    print("-" * 80)

    for r in cur.fetchall():
        print(f"{r[0]:<10} {r[3]:<8.2f} {r[4]:<8.2f} {r[5]:<8.2f} {r[6]:<8.2f} {r[7]:<6.2f} {r[8]:<6.2f} {r[9]:<6.2f} {r[10]:<6.2f} {r[11]:<6.2f}")

    print()
    print("=" * 80)
    print("mr_warranty.ponderaciones")
    print("=" * 80)
    print()

    cur.execute("""
        SELECT grupo, categoria, ponderacion, descripcion
        FROM mr_warranty.ponderaciones
        WHERE grupo = 'SF_ATTACHMENTS'
        ORDER BY categoria
    """)

    print(f"{'Grupo':<18} {'Categoria':<25} {'Ponderacion':<12} {'Descripcion'}")
    print("-" * 80)
    for r in cur.fetchall():
        print(f"{r[0]:<18} {r[1]:<25} {r[2]:<12.2f} {r[3] or ''}")

    print()
    cur.execute("SELECT COUNT(*) FROM mr_warranty.ponderaciones")
    print(f"Total ponderaciones: {cur.fetchone()[0]}")

    conn.close()


if __name__ == "__main__":
    main()
