-- ============================================================
-- Script de Migración: Agregar columnas de adjuntos EDT
-- Ejecutar solo si la tabla ya existe sin estas columnas
-- ============================================================

-- Verificar si la tabla existe
IF OBJECT_ID('dbo.reclamos_procesados', 'U') IS NOT NULL
BEGIN
    PRINT 'Tabla dbo.reclamos_procesados encontrada';
    
    -- Agregar columnas de adjuntos si no existen
    IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.reclamos_procesados') AND name = 'attachments_plm')
    BEGIN
        ALTER TABLE dbo.reclamos_procesados
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
            adjuntos_en_case INT NULL;
        
        PRINT 'Columnas de adjuntos agregadas exitosamente';
    END
    ELSE
    BEGIN
        PRINT 'Las columnas de adjuntos ya existen';
    END
END
ELSE
BEGIN
    PRINT 'ERROR: La tabla dbo.reclamos_procesados no existe';
    PRINT 'Ejecutar primero create_reclamos_procesados.sql';
END
GO

-- Verificar estructura final
SELECT 
    COLUMN_NAME, 
    DATA_TYPE, 
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'reclamos_procesados'
AND TABLE_SCHEMA = 'dbo'
ORDER BY ORDINAL_POSITION;
GO
