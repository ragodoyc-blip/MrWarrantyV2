-- ============================================================
-- Migracion: Agregar columna Claim_Type__c (ClaimCoverage.Claim_Type__c)
-- Aplica a mr_warranty.reclamos_procesados
-- Historicos quedan en NULL (solo nuevos, sin backfill)
-- ============================================================

IF OBJECT_ID('mr_warranty.reclamos_procesados', 'U') IS NOT NULL
BEGIN
    PRINT 'Tabla mr_warranty.reclamos_procesados encontrada';

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'claim_type__c')
        ALTER TABLE mr_warranty.reclamos_procesados ADD claim_type__c NVARCHAR(100) NULL;

    PRINT 'Columna claim_type__c verificada/agregada';
END
ELSE
BEGIN
    PRINT 'ERROR: La tabla mr_warranty.reclamos_procesados no existe';
END
GO
