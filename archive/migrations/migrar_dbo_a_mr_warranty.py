"""
Migracion de dbo a mr_warranty.
"""

import pyodbc
from config import SQL_DRIVER, SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD


def get_conn():
    return pyodbc.connect(
        f"DRIVER={{{SQL_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};PWD={SQL_PASSWORD};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )


def agregar_columnas_mr_warranty():
    """Paso 1: Agregar columnas attachments a mr_warranty.reclamos_procesados"""
    print("Paso 1: Agregar columnas a mr_warranty.reclamos_procesados...")
    conn = get_conn()
    cur = conn.cursor()

    # Verificar si la columna ya existe
    cur.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'mr_warranty' AND TABLE_NAME = 'reclamos_procesados'
        AND COLUMN_NAME = 'attachments_plm'
    """)
    existe = cur.fetchone()[0]

    if existe == 0:
        cur.execute("""
            ALTER TABLE mr_warranty.reclamos_procesados
            ADD 
                attachments_plm DECIMAL(10,4) NULL,
                attachments_plm_reason NVARCHAR(MAX) NULL,
                attachments_oil_analysis DECIMAL(10,4) NULL,
                attachments_oil_analysis_reason NVARCHAR(MAX) NULL,
                attachments_datapacks DECIMAL(10,4) NULL,
                attachments_datapacks_reason NVARCHAR(MAX) NULL,
                attachments_technical_report_sf DECIMAL(10,4) NULL,
                attachments_technical_report_sf_reason NVARCHAR(MAX) NULL,
                attachments_photographs_sf DECIMAL(10,4) NULL,
                attachments_photographs_sf_reason NVARCHAR(MAX) NULL,
                total_adjuntos INT NULL,
                adjuntos_en_claim INT NULL,
                adjuntos_en_case INT NULL
        """)
        conn.commit()
        print("  [OK] Columnas agregadas a mr_warranty.reclamos_procesados")
    else:
        print("  [INFO] Las columnas ya existen")

    conn.close()


def crear_ponderaciones_mr_warranty():
    """Paso 2: Crear tabla mr_warranty.ponderaciones"""
    print("\nPaso 2: Crear tabla mr_warranty.ponderaciones...")
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        IF OBJECT_ID('mr_warranty.ponderaciones', 'U') IS NULL
        BEGIN
            CREATE TABLE mr_warranty.ponderaciones (
                id INT IDENTITY(1,1) NOT NULL,
                grupo NVARCHAR(50) NOT NULL,
                categoria NVARCHAR(100) NOT NULL,
                ponderacion DECIMAL(10,4) NOT NULL,
                descripcion NVARCHAR(500) NULL,
                activo BIT NOT NULL CONSTRAINT DF_ponderaciones_activo DEFAULT 1,
                created_at DATETIME2 NOT NULL CONSTRAINT DF_ponderaciones_created_at DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 NOT NULL CONSTRAINT DF_ponderaciones_updated_at DEFAULT SYSUTCDATETIME(),
                CONSTRAINT PK_ponderaciones PRIMARY KEY (id),
                CONSTRAINT UQ_ponderaciones_grupo_categoria UNIQUE (grupo, categoria)
            )
            CREATE INDEX IX_ponderaciones_grupo ON mr_warranty.ponderaciones (grupo)
        END
    """)
    conn.commit()
    print("  [OK] Tabla mr_warranty.ponderaciones creada/verificada")

    conn.close()


def migrar_ponderaciones():
    """Paso 3: Migrar datos de dbo.ponderaciones a mr_warranty.ponderaciones"""
    print("\nPaso 3: Migrar datos de dbo.ponderaciones a mr_warranty...")
    conn = get_conn()
    cur = conn.cursor()

    # Verificar si ya hay datos
    cur.execute("SELECT COUNT(*) FROM mr_warranty.ponderaciones")
    count_mr = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM dbo.ponderaciones")
    count_dbo = cur.fetchone()[0]

    if count_mr == 0 and count_dbo > 0:
        cur.execute("""
            INSERT INTO mr_warranty.ponderaciones (grupo, categoria, ponderacion, descripcion, activo, created_at, updated_at)
            SELECT grupo, categoria, ponderacion, descripcion, activo, created_at, updated_at
            FROM dbo.ponderaciones
        """)
        conn.commit()
        print(f"  [OK] {count_dbo} registros migrados")
    else:
        print(f"  [INFO] mr_warranty ya tiene {count_mr} registros, no se migran")

    conn.close()


def migrar_registros_edt():
    """Paso 4: Migrar registros EDT de dbo a mr_warranty"""
    print("\nPaso 4: Migrar registros EDT de dbo a mr_warranty...")
    conn = get_conn()
    cur = conn.cursor()

    # Obtener registros de dbo
    cur.execute("""
        SELECT claim_number, plataforma, 
               CONVERT(VARCHAR(30), createdon, 126) as createdon,
               status, tipo_garantia,
               ISNULL(repair_deadline, 0), repair_deadline_reason,
               ISNULL(claim_deadline, 0), claim_deadline_reason,
               ISNULL(within_standard_warranty, 0), within_standard_warranty_reason,
               ISNULL(root_cause_analysis, 0), root_cause_analysis_reason,
               ISNULL(attachments_plm, 0), attachments_plm_reason,
               ISNULL(attachments_oil_analysis, 0), attachments_oil_analysis_reason,
               ISNULL(attachments_datapacks, 0), attachments_datapacks_reason,
               ISNULL(attachments_technical_report_sf, 0), attachments_technical_report_sf_reason,
               ISNULL(attachments_photographs_sf, 0), attachments_photographs_sf_reason,
               total_adjuntos, adjuntos_en_claim, adjuntos_en_case
        FROM dbo.reclamos_procesados
        WHERE plataforma = 'Salesforce'
    """)

    records = cur.fetchall()
    print(f"  [INFO] Encontrados {len(records)} registros en dbo")

    migrados = 0
    for row in records:
        # Primero verificar si ya existe
        cur.execute("""
            SELECT COUNT(*) FROM mr_warranty.reclamos_procesados
            WHERE claim_number = ? AND plataforma = ?
        """, (row[0], row[1]))
        existe = cur.fetchone()[0]
        
        if existe > 0:
            # Ya existe, hacer UPDATE
            cur.execute("""
                UPDATE mr_warranty.reclamos_procesados SET
                    status = ?, tipo_garantia = ?,
                    repair_deadline = ?, repair_deadline_reason = ?,
                    claim_deadline = ?, claim_deadline_reason = ?,
                    within_standard_warranty = ?, within_standard_warranty_reason = ?,
                    root_cause_analysis = ?, root_cause_analysis_reason = ?,
                    attachments_plm = ?, attachments_plm_reason = ?,
                    attachments_oil_analysis = ?, attachments_oil_analysis_reason = ?,
                    attachments_datapacks = ?, attachments_datapacks_reason = ?,
                    attachments_technical_report_sf = ?, attachments_technical_report_sf_reason = ?,
                    attachments_photographs_sf = ?, attachments_photographs_sf_reason = ?,
                    total_adjuntos = ?, adjuntos_en_claim = ?, adjuntos_en_case = ?,
                    updated_at = SYSUTCDATETIME()
                WHERE claim_number = ? AND plataforma = ?
            """, (
                row[3], row[4],
                row[5], row[6],
                row[7], row[8],
                row[9], row[10],
                row[11], row[12],
                row[13], row[14],
                row[15], row[16],
                row[17], row[18],
                row[19], row[20],
                row[21], row[22],
                row[23], row[24], row[25],
                row[0], row[1]
            ))
        else:
            # No existe, hacer INSERT
            cur.execute("""
                INSERT INTO mr_warranty.reclamos_procesados (
                    claim_number, plataforma, createdon, status, tipo_garantia,
                    repair_deadline, repair_deadline_reason,
                    claim_deadline, claim_deadline_reason,
                    within_standard_warranty, within_standard_warranty_reason,
                    root_cause_analysis, root_cause_analysis_reason,
                    attachments_plm, attachments_plm_reason,
                    attachments_oil_analysis, attachments_oil_analysis_reason,
                    attachments_datapacks, attachments_datapacks_reason,
                    attachments_technical_report_sf, attachments_technical_report_sf_reason,
                    attachments_photographs_sf, attachments_photographs_sf_reason,
                    total_adjuntos, adjuntos_en_claim, adjuntos_en_case
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row[0], row[1], row[2], row[3], row[4],
                row[5], row[6],
                row[7], row[8],
                row[9], row[10],
                row[11], row[12],
                row[13], row[14],
                row[15], row[16],
                row[17], row[18],
                row[19], row[20],
                row[21], row[22],
                row[23], row[24], row[25]
            ))
        migrados += 1

    conn.commit()
    print(f"  [OK] {migrados} registros procesados")

    conn.close()


def eliminar_tablas_dbo():
    """Paso 5: Eliminar tablas en dbo"""
    print("\nPaso 5: Eliminar tablas dbo...")
    conn = get_conn()
    cur = conn.cursor()

    # Eliminar dbo.reclamos_procesados
    cur.execute("""
        IF OBJECT_ID('dbo.reclamos_procesados', 'U') IS NOT NULL
        BEGIN
            DROP TABLE dbo.reclamos_procesados
        END
    """)
    print("  [OK] dbo.reclamos_procesados eliminada")

    # Eliminar dbo.ponderaciones
    cur.execute("""
        IF OBJECT_ID('dbo.ponderaciones', 'U') IS NOT NULL
        BEGIN
            DROP TABLE dbo.ponderaciones
        END
    """)
    print("  [OK] dbo.ponderaciones eliminada")

    conn.commit()
    conn.close()


def verificar_migracion():
    """Verificar el estado final de la migración"""
    print("\n" + "=" * 70)
    print("VERIFICACION FINAL")
    print("=" * 70)

    conn = get_conn()
    cur = conn.cursor()

    # Verificar tablas en mr_warranty
    cur.execute("""
        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = 'mr_warranty' AND TABLE_NAME IN ('reclamos_procesados', 'ponderaciones')
    """)
    print("\nTablas en mr_warranty:")
    for r in cur.fetchall():
        print(f"  mr_warranty.{r[0]}")

    # Contar registros
    cur.execute("SELECT COUNT(*) FROM mr_warranty.reclamos_procesados")
    print(f"\nTotal mr_warranty.reclamos_procesados: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM mr_warranty.reclamos_procesados WHERE plataforma = 'Salesforce'")
    print(f"  - Salesforce: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM mr_warranty.ponderaciones")
    print(f"\nTotal mr_warranty.ponderaciones: {cur.fetchone()[0]}")

    # Verificar tablas dbo
    cur.execute("""
        SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME IN ('reclamos_procesados', 'ponderaciones')
    """)
    print("\nTablas restantes en dbo (deberian estar vacias):")
    tables = cur.fetchall()
    if not tables:
        print("  Ninguna - dbo limpio correctamente")
    else:
        for r in tables:
            print(f"  dbo.{r[0]}")

    # Verificar columnas nuevas
    cur.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'mr_warranty' AND TABLE_NAME = 'reclamos_procesados'
        AND COLUMN_NAME LIKE 'attachments%'
    """)
    print(f"\nColumnas de adjuntos en mr_warranty.reclamos_procesados: {cur.fetchone()[0]}")

    conn.close()


def main():
    print("=" * 70)
    print("MIGRACION: dbo -> mr_warranty")
    print("=" * 70)

    agregar_columnas_mr_warranty()
    crear_ponderaciones_mr_warranty()
    migrar_ponderaciones()
    migrar_registros_edt()
    eliminar_tablas_dbo()
    verificar_migracion()

    print("\n" + "=" * 70)
    print("MIGRACION COMPLETADA")
    print("=" * 70)


if __name__ == "__main__":
    main()
