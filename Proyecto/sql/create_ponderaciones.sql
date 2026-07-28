-- ============================================================
-- Tabla de Ponderaciones para Mr. Warranty
-- Schema: dbo
-- ============================================================

IF OBJECT_ID('dbo.ponderaciones', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ponderaciones (
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
    );

    CREATE INDEX IX_ponderaciones_grupo ON dbo.ponderaciones (grupo);

    PRINT 'Tabla dbo.ponderaciones creada exitosamente';
END
ELSE
BEGIN
    PRINT 'Tabla dbo.ponderaciones ya existe';
END
GO

-- ============================================================
-- Datos Iniciales: Field Campaign (SQIS)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM dbo.ponderaciones WHERE grupo = 'FC')
BEGIN
    INSERT INTO dbo.ponderaciones (grupo, categoria, ponderacion, descripcion) VALUES
    ('FC', 'fc_expiration', 0.20, 'Vigencia de campaña de campo'),
    ('FC', 'repair_deadline', 0.05, 'Plazo de reparación'),
    ('FC', 'claim_deadline', 0.20, 'Plazo del reclamo'),
    ('FC', 'technical_report', 0.05, 'Reporte técnico'),
    ('FC', 'invoices', 0.15, 'Facturas'),
    ('FC', 'work_order', 0.05, 'Orden de trabajo'),
    ('FC', 'photographs', 0.15, 'Fotografías'),
    ('FC', 'labor_coverage', 0.05, 'Cobertura de mano de obra'),
    ('FC', 'mileage_coverage', 0.05, 'Cobertura de kilometraje'),
    ('FC', 'other_expenses_coverage', 0.05, 'Cobertura de otros gastos');

    PRINT 'Datos FC insertados';
END
GO

-- ============================================================
-- Datos Iniciales: Standard Warranty (SQIS)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM dbo.ponderaciones WHERE grupo = 'STD')
BEGIN
    INSERT INTO dbo.ponderaciones (grupo, categoria, ponderacion, descripcion) VALUES
    ('STD', 'within_standard_warranty', 0.15, 'Dentro de garantía estándar'),
    ('STD', 'repair_deadline', 0.15, 'Plazo de reparación'),
    ('STD', 'claim_deadline', 0.15, 'Plazo del reclamo'),
    ('STD', 'technical_report', 0.15, 'Reporte técnico'),
    ('STD', 'invoices', 0.10, 'Facturas'),
    ('STD', 'work_order', 0.05, 'Orden de trabajo'),
    ('STD', 'photographs', 0.10, 'Fotografías'),
    ('STD', 'standard_rate', 0.15, 'Tarifa estándar');

    PRINT 'Datos STD insertados';
END
GO

-- ============================================================
-- Datos Iniciales: Parts Warranty
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM dbo.ponderaciones WHERE grupo = 'PARTS')
BEGIN
    INSERT INTO dbo.ponderaciones (grupo, categoria, ponderacion, descripcion) VALUES
    ('PARTS', 'within_standard_warranty', 0.15, 'Dentro de garantía estándar'),
    ('PARTS', 'repair_deadline', 0.15, 'Plazo de reparación'),
    ('PARTS', 'claim_deadline', 0.15, 'Plazo del reclamo'),
    ('PARTS', 'technical_report', 0.10, 'Reporte técnico'),
    ('PARTS', 'invoices', 0.10, 'Facturas'),
    ('PARTS', 'work_order', 0.10, 'Orden de trabajo'),
    ('PARTS', 'photographs', 0.10, 'Fotografías'),
    ('PARTS', 'standard_rate', 0.15, 'Tarifa estándar');

    PRINT 'Datos PARTS insertados';
END
GO

-- ============================================================
-- Datos Iniciales: Standard Warranty (Salesforce)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM dbo.ponderaciones WHERE grupo = 'STD_SF')
BEGIN
    INSERT INTO dbo.ponderaciones (grupo, categoria, ponderacion, descripcion) VALUES
    ('STD_SF', 'within_standard_warranty', 0.15, 'Dentro de garantía estándar'),
    ('STD_SF', 'repair_deadline', 0.15, 'Plazo de reparación'),
    ('STD_SF', 'claim_deadline', 0.15, 'Plazo del reclamo'),
    ('STD_SF', 'technical_report', 0.15, 'Reporte técnico (adjunto)'),
    ('STD_SF', 'photographs', 0.10, 'Fotografías (adjunto)'),
    ('STD_SF', 'plm', 0.10, 'PLM (adjunto)'),
    ('STD_SF', 'analisis_aceite', 0.10, 'Análisis de aceite (adjunto)'),
    ('STD_SF', 'datapacks', 0.10, 'Datapacks (adjunto)');

    PRINT 'Datos STD_SF insertados';
END
GO

-- ============================================================
-- Datos Iniciales: Field Campaign (Salesforce)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM dbo.ponderaciones WHERE grupo = 'FC_SF')
BEGIN
    INSERT INTO dbo.ponderaciones (grupo, categoria, ponderacion, descripcion) VALUES
    ('FC_SF', 'fc_expiration', 0.20, 'Vigencia de campaña de campo'),
    ('FC_SF', 'repair_deadline', 0.05, 'Plazo de reparación'),
    ('FC_SF', 'claim_deadline', 0.20, 'Plazo del reclamo'),
    ('FC_SF', 'technical_report', 0.10, 'Reporte técnico'),
    ('FC_SF', 'labor_coverage', 0.05, 'Cobertura de mano de obra'),
    ('FC_SF', 'mileage_coverage', 0.05, 'Cobertura de kilometraje'),
    ('FC_SF', 'other_expenses_coverage', 0.05, 'Cobertura de otros gastos'),
    ('FC_SF', 'parts_coverage', 0.10, 'Cobertura de partes');

    PRINT 'Datos FC_SF insertados';
END
GO

-- ============================================================
-- Datos Iniciales: SF Attachments (EDT Factory Warranty)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM dbo.ponderaciones WHERE grupo = 'SF_ATTACHMENTS')
BEGIN
    INSERT INTO dbo.ponderaciones (grupo, categoria, ponderacion, descripcion) VALUES
    ('SF_ATTACHMENTS', 'plm', 0.10, 'Documentos PLM'),
    ('SF_ATTACHMENTS', 'analisis_aceite', 0.10, 'Análisis de aceite'),
    ('SF_ATTACHMENTS', 'datapacks', 0.10, 'Datapacks (DSC, haulcycle, etc.)'),
    ('SF_ATTACHMENTS', 'reporte_tecnico', 0.15, 'Reporte técnico Salesforce'),
    ('SF_ATTACHMENTS', 'fotografias', 0.15, 'Fotografías de evidencia');

    PRINT 'Datos SF_ATTACHMENTS insertados';
END
GO

-- ============================================================
-- Vista de Resumen
-- ============================================================
IF OBJECT_ID('dbo.v_ponderaciones_resumen', 'V') IS NOT NULL
    DROP VIEW dbo.v_ponderaciones_resumen;
GO

CREATE VIEW dbo.v_ponderaciones_resumen AS
SELECT 
    id,
    grupo,
    categoria,
    ponderacion,
    CAST(ponderacion * 100 AS DECIMAL(5,2)) AS porcentaje,
    descripcion,
    activo,
    CASE 
        WHEN grupo = 'FC' THEN 'Field Campaign (SQIS)'
        WHEN grupo = 'STD' THEN 'Standard Warranty (SQIS)'
        WHEN grupo = 'PARTS' THEN 'Parts Warranty'
        WHEN grupo = 'STD_SF' THEN 'Standard Warranty (Salesforce)'
        WHEN grupo = 'FC_SF' THEN 'Field Campaign (Salesforce)'
        WHEN grupo = 'SF_ATTACHMENTS' THEN 'Adjuntos EDT (Salesforce)'
        ELSE grupo
    END AS grupo_descripcion
FROM dbo.ponderaciones;
GO

PRINT 'Vista dbo.v_ponderaciones_resumen creada';
GO

-- ============================================================
-- Verificación: Total por grupo
-- ============================================================
SELECT 
    grupo,
    COUNT(*) AS categorias,
    SUM(ponderacion) AS total_ponderacion,
    CAST(SUM(ponderacion) * 100 AS DECIMAL(5,2)) AS total_porcentaje
FROM dbo.ponderaciones
WHERE activo = 1
GROUP BY grupo
ORDER BY grupo;
GO
