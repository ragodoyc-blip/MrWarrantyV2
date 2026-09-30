-- ============================================================
-- Migracion: Agregar columnas SPCR informativo 0-1 (PA - Special Policy)
-- Aplica a mr_warranty.reclamos_procesados
-- Historicos quedan en NULL (solo nuevos, sin backfill)
-- ============================================================

IF OBJECT_ID('mr_warranty.reclamos_procesados', 'U') IS NOT NULL
BEGIN
    PRINT 'Tabla mr_warranty.reclamos_procesados encontrada';

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'attachments_special_policy')
        ALTER TABLE mr_warranty.reclamos_procesados ADD attachments_special_policy DECIMAL(10,4) NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'attachments_special_policy_reason')
        ALTER TABLE mr_warranty.reclamos_procesados ADD attachments_special_policy_reason NVARCHAR(MAX) NULL;

    PRINT 'Columnas attachments_special_policy verificadas/agregadas';
END
ELSE
BEGIN
    PRINT 'ERROR: La tabla mr_warranty.reclamos_procesados no existe';
END
GO
