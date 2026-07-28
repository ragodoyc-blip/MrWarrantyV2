"""
Verifica los resultados en SQL.
"""

import pyodbc
from config import SQL_DRIVER, SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD


def verify_results():
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

    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    print("=" * 100)
    print("REGISTROS EN dbo.reclamos_procesados (Salesforce)")
    print("=" * 100)
    print()

    cursor.execute("""
        SELECT 
            claim_number,
            tipo_garantia,
            status,
            ISNULL(repair_deadline, 0) as repair_deadline,
            ISNULL(claim_deadline, 0) as claim_deadline,
            ISNULL(within_standard_warranty, 0) as within_standard_warranty,
            ISNULL(root_cause_analysis, 0) as root_cause_analysis,
            ISNULL(attachments_plm, 0) as attachments_plm,
            ISNULL(attachments_oil_analysis, 0) as attachments_oil_analysis,
            ISNULL(attachments_datapacks, 0) as attachments_datapacks,
            ISNULL(attachments_technical_report_sf, 0) as attachments_technical_report_sf,
            ISNULL(attachments_photographs_sf, 0) as attachments_photographs_sf
        FROM dbo.reclamos_procesados
        WHERE plataforma = 'Salesforce'
        ORDER BY claim_number
    """)

    header = f"{'Claim':<10} {'Repair':<8} {'ClaimDL':<8} {'Warranty':<8} {'Root':<8} {'PLM':<6} {'Oil':<6} {'Data':<6} {'TR':<6} {'Photos':<6}"
    print(header)
    print("-" * len(header))

    total_repair = 0
    total_claimdl = 0
    total_warranty = 0
    total_root = 0
    total_plm = 0
    total_oil = 0
    total_data = 0
    total_tr = 0
    total_photos = 0
    count = 0

    for row in cursor.fetchall():
        claim = row[0]
        repair = row[3] or 0
        claimdl = row[4] or 0
        warranty = row[5] or 0
        root = row[6] or 0
        plm = row[7] or 0
        oil = row[8] or 0
        data = row[9] or 0
        tr = row[10] or 0
        photos = row[11] or 0

        print(f"{claim:<10} {repair:<8.2f} {claimdl:<8.2f} {warranty:<8.2f} {root:<8.2f} {plm:<6.2f} {oil:<6.2f} {data:<6.2f} {tr:<6.2f} {photos:<6.2f}")

        total_repair += repair
        total_claimdl += claimdl
        total_warranty += warranty
        total_root += root
        total_plm += plm
        total_oil += oil
        total_data += data
        total_tr += tr
        total_photos += photos
        count += 1

    print("-" * len(header))
    
    if count > 0:
        print(f"{'PROMEDIO':<10} {total_repair/count:<8.2f} {total_claimdl/count:<8.2f} {total_warranty/count:<8.2f} {total_root/count:<8.2f} {total_plm/count:<6.2f} {total_oil/count:<6.2f} {total_data/count:<6.2f} {total_tr/count:<6.2f} {total_photos/count:<6.2f}")
    
    print()
    print(f"Total registros: {count}")
    
    # Verificar ponderaciones
    print()
    print("=" * 60)
    print("PONDERACIONES EN dbo.ponderaciones")
    print("=" * 60)
    print()
    
    cursor.execute("""
        SELECT grupo, categoria, ponderacion, descripcion
        FROM dbo.ponderaciones
        WHERE activo = 1
        ORDER BY grupo, categoria
    """)
    
    current_grupo = None
    for row in cursor.fetchall():
        if row[0] != current_grupo:
            print(f"\n[{row[0]}]")
            current_grupo = row[0]
        print(f"  {row[1]:<25} {row[2]:<8.2f} {row[3] or ''}")
    
    conn.close()


if __name__ == "__main__":
    verify_results()
