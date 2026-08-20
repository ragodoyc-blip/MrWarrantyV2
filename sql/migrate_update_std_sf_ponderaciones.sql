-- ============================================================
-- Migración: Refactorización de ponderaciones Factory Warranty Salesforce
-- Solo afecta a STD_SF. SQIS, FC_SF y otros grupos no se tocan.
-- ============================================================

-- Paso 1: Limpiar ponderaciones obsoletas del Factory Warranty Salesforce
DELETE FROM dbo.ponderaciones
WHERE grupo = 'STD_SF'
  AND categoria IN ('RootCause_analysis', 'invoices', 'standard_rate');

-- Paso 2: Insertar/actualizar las nuevas ponderaciones
MERGE dbo.ponderaciones AS target
USING (VALUES
    ('within_standard_warranty', 0.15, 'Dentro de garantía estándar'),
    ('repair_deadline', 0.15, 'Plazo de reparación'),
    ('claim_deadline', 0.15, 'Plazo del reclamo'),
    ('technical_report', 0.15, 'Reporte técnico (adjunto)'),
    ('photographs', 0.10, 'Fotografías (adjunto)'),
    ('plm', 0.10, 'PLM (adjunto)'),
    ('analisis_aceite', 0.10, 'Análisis de aceite (adjunto)'),
    ('datapacks', 0.10, 'Datapacks (adjunto)')
) AS src(categoria, ponderacion, descripcion)
ON target.grupo = 'STD_SF' AND target.categoria = src.categoria
WHEN MATCHED THEN
    UPDATE SET ponderacion = src.ponderacion, descripcion = src.descripcion
WHEN NOT MATCHED THEN
    INSERT (grupo, categoria, ponderacion, descripcion)
    VALUES ('STD_SF', src.categoria, src.ponderacion, src.descripcion);

-- Paso 3: Verificación (debe sumar 1.00)
SELECT grupo, SUM(ponderacion) AS total_ponderacion
FROM dbo.ponderaciones
WHERE grupo = 'STD_SF' AND activo = 1
GROUP BY grupo;
GO

PRINT 'Migración STD_SF completada';
GO
