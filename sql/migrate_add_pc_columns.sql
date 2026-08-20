-- ============================================================
-- Migracion: Agregar columnas para PC - Parts and Components
-- Aplica a mr_warranty.reclamos_procesados
-- ============================================================

IF OBJECT_ID('mr_warranty.reclamos_procesados', 'U') IS NOT NULL
BEGIN
    PRINT 'Tabla mr_warranty.reclamos_procesados encontrada';

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'coverage_type')
        ALTER TABLE mr_warranty.reclamos_procesados ADD coverage_type NVARCHAR(100) NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'repair_date')
        ALTER TABLE mr_warranty.reclamos_procesados ADD repair_date DATETIMEOFFSET NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'part_installation_date')
        ALTER TABLE mr_warranty.reclamos_procesados ADD part_installation_date DATETIMEOFFSET NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'part_installation_date_reason')
        ALTER TABLE mr_warranty.reclamos_procesados ADD part_installation_date_reason NVARCHAR(MAX) NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'work_order')
        ALTER TABLE mr_warranty.reclamos_procesados ADD work_order DECIMAL(10,4) NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'work_order_reason')
        ALTER TABLE mr_warranty.reclamos_procesados ADD work_order_reason NVARCHAR(MAX) NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'purchase_invoice')
        ALTER TABLE mr_warranty.reclamos_procesados ADD purchase_invoice DECIMAL(10,4) NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'purchase_invoice_reason')
        ALTER TABLE mr_warranty.reclamos_procesados ADD purchase_invoice_reason NVARCHAR(MAX) NULL;

    PRINT 'Columnas PC verificadas/agregadas';
END
ELSE
BEGIN
    PRINT 'ERROR: La tabla mr_warranty.reclamos_procesados no existe';
END
GO
