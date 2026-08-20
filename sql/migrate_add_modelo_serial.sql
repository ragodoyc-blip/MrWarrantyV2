-- ============================================================
-- Migración: Agregar columnas modelo y serial_number
-- Aplica a mr_warranty.reclamos_procesados
-- ============================================================

IF OBJECT_ID('mr_warranty.reclamos_procesados', 'U') IS NOT NULL
BEGIN
    PRINT 'Tabla mr_warranty.reclamos_procesados encontrada';

    IF NOT EXISTS (SELECT 1 FROM sys.columns
                   WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados')
                   AND name = 'modelo')
    BEGIN
        ALTER TABLE mr_warranty.reclamos_procesados
        ADD modelo NVARCHAR(100) NULL;
        PRINT 'Columna modelo agregada';
    END
    ELSE
    BEGIN
        PRINT 'Columna modelo ya existe';
    END

    IF NOT EXISTS (SELECT 1 FROM sys.columns
                   WHERE object_id = OBJECT_ID('mr_warranty.reclamos_procesados')
                   AND name = 'serial_number')
    BEGIN
        ALTER TABLE mr_warranty.reclamos_procesados
        ADD serial_number NVARCHAR(100) NULL;
        PRINT 'Columna serial_number agregada';
    END
    ELSE
    BEGIN
        PRINT 'Columna serial_number ya existe';
    END
END
ELSE
BEGIN
    PRINT 'ERROR: La tabla mr_warranty.reclamos_procesados no existe';
END
GO
