-- ============================================================
-- Migracion: Agregar columna submitted_date
-- Aplica a mr_warranty.reclamos_procesados
-- ============================================================

IF OBJECT_ID('mr_warranty.reclamos_procesados', 'U') IS NOT NULL
BEGIN
    PRINT 'Tabla mr_warranty.reclamos_procesados encontrada';

    IF NOT EXISTS (SELECT 1 FROM sys.columns
                   WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados')
                   AND name = 'submitted_date')
    BEGIN
        ALTER TABLE mr_warranty.reclamos_procesados
        ADD submitted_date DATETIMEOFFSET NULL;
        PRINT 'Columna submitted_date agregada';
    END
    ELSE
    BEGIN
        PRINT 'Columna submitted_date ya existe';
    END
END
ELSE
BEGIN
    PRINT 'ERROR: La tabla mr_warranty.reclamos_procesados no existe';
END
GO
