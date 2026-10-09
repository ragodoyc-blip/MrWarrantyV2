-- ============================================================
-- Migracion: Agregar columnas de costo IA por reclamo procesado
-- Aplica a mr_warranty.reclamos_procesados
-- Historicos quedan en NULL (no reconstruible)
-- ============================================================

IF OBJECT_ID('mr_warranty.reclamos_procesados', 'U') IS NOT NULL
BEGIN
    PRINT 'Tabla mr_warranty.reclamos_procesados encontrada';

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'ia_calls')
        ALTER TABLE mr_warranty.reclamos_procesados ADD ia_calls INT NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'ia_input_tokens')
        ALTER TABLE mr_warranty.reclamos_procesados ADD ia_input_tokens BIGINT NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'ia_output_tokens')
        ALTER TABLE mr_warranty.reclamos_procesados ADD ia_output_tokens BIGINT NULL;

    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados') AND name = 'ia_estimated_cost_usd')
        ALTER TABLE mr_warranty.reclamos_procesados ADD ia_estimated_cost_usd DECIMAL(10,4) NULL;

    PRINT 'Columnas IA verificadas/agregadas';
END
ELSE
BEGIN
    PRINT 'ERROR: La tabla mr_warranty.reclamos_procesados no existe';
END
GO
