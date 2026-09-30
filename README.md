# Mr. Warranty

## Objetivo

Mr. Warranty evalúa reclamos de **Factory Warranty** provenientes de Salesforce. El sistema revisa la información del reclamo, el caso técnico asociado y los documentos adjuntos, y genera un puntaje con las razones de cada resultado.

La evaluación busca identificar rápidamente si la evidencia presentada es coherente con la falla, la reparación y el componente reclamado.

## Tipos De Factory Warranty

### Factory Warranty normal

La vigencia se calcula usando la fecha de puesta en marcha del equipo (`MachineCommissionedDate__c`) y la fecha de falla.

### PC - Parts and Components

La vigencia se calcula usando la fecha de instalación o reemplazo de la pieza y la fecha de falla. El resto de los criterios documentales se evalúa de la misma forma.

### PC - Part DB Installed

Variante de PC con `CoverageType = PC - Parts and Components` y `Claim_Type__c = PC - Part DB Installed`:

- `within_standard_warranty` invertido sobre el equipo: dentro de 1 año = 0, sobre 1 año = 100% (15%). El equipo debe estar fuera de garantía.
- La vigencia de la pieza la valida Salesforce al crear el claim; Mr. Warranty no calcula año de pieza.
- `Invoices` exige doble respaldo: factura 1 = pieza que falla, factura 2 = pieza instalada (misma escala 0.10, proporcional 5 criterios). Con menos de 2 documentos = 0.
- Ambas partes pueden venir solo en texto libre (`Correction__c`, `Cause__c`, `Description`, `Resolution_Details__c`, Chatter); los campos `CausalPart__c` / `Product_Code__c` se usan solo como pista.
- Repair/Claim deadline, informe técnico, PLM, Oil, Datapacks y Work Order mantienen la lógica normal.

### PA - Special Policy

Variante con `CoverageType = PA - Special Policy` y `Claim_Type__c = PA - Special Policy`:

- Misma matriz y ponderaciones que S1 - Standard Warranty (`within` = 15% con `No aplica.`; resto idéntico).
- Adjunto adicional: formulario `Special Policy Consideration Request & Authorization` (`MAN38.1-F7`, formato único para todo reclamo PA). Solo se evalúa presencia/contenido: debe coincidir modelo (Sección A campo 6) y número de serie (Sección A campo 7).
- El SPCR es **informativo 0–1** (3 criterios proporcionales: formulario reconocible + modelo + serie) y **no resta peso** a ningún criterio.
- Se guarda en 2 columnas nuevas: `attachments_special_policy` (puntaje) y `attachments_special_policy_reason` (motivo), igual que los otros análisis.

## Ponderaciones

| Criterio | Ponderación |
| --- | ---: |
| Within standard warranty | 15% |
| Repair deadline | 15% |
| Claim deadline | 15% |
| Informe técnico integrado con fotografías | 20% |
| PLM | 5% |
| Oil Analysis | 5% |
| Datapacks | 5% |
| Work Order | 10% |
| Invoice | 10% |
| **Total** | **100%** |

Las fotografías no tienen una ponderación independiente porque se analizan dentro del informe técnico.

## Criterios De Evaluación

### 1. Within Standard Warranty - 15%

Para Factory Warranty con Claim_Type__c vacío o no listado (fallback por fechas):

- Se compara la fecha de puesta en marcha del equipo con la fecha de falla.
- Si han transcurrido 365 días o menos, la garantía está vigente.
- Si han transcurrido 366 días o más, la garantía se considera expirada.

Para PC:

- Se compara la fecha de instalación o reemplazo de la pieza con la fecha de falla.
- Si no se puede determinar la fecha de instalación, el criterio obtiene 0 puntos.

Para PC - Part DB Installed (vigencia invertida del equipo):

- Se compara `MachineCommissionedDate__c` con la fecha de falla.
- Si han transcurrido 365 días o menos (equipo en garantía), el criterio obtiene 0 puntos.
- Si han transcurrido 366 días o más (equipo fuera de garantía), obtiene el puntaje máximo (15%).
- No se calcula vigencia de pieza; Salesforce la valida al crear el claim.

Para SK - Repair prior to commissioning, S1 - Standard Warranty, MA - Missing or Damaged Part prior to commissioning y PA - Special Policy:

- `within_standard_warranty` siempre obtiene el puntaje máximo (15%) con razón `No aplica.`.
- El resto del análisis se mantiene: fechas, documentos adjuntos, Work Order e Invoice.
- El valor de `ClaimCoverage.Claim_Type__c` se guarda en la columna `claim_type__c` de `[mr_warranty].[reclamos_procesados]`.

### 2. Repair Deadline - 15%

- Se compara la fecha de falla con la fecha de reparación.
- La reparación debe realizarse en menos de 30 días desde la falla.
- Con 30 días o más, el criterio no cumple.
- Si falta una de las fechas, el criterio obtiene 0 puntos.

### 3. Claim Deadline - 15%

- Se compara la fecha de reparación con la fecha de creación del reclamo.
- El reclamo debe crearse dentro de los 30 días posteriores a la reparación.
- Con más de 30 días, el criterio no cumple.
- Si falta una de las fechas, el criterio obtiene 0 puntos.

### 4. Informe Técnico Integrado Con Fotografías - 20%

El informe técnico se analiza junto con sus imágenes y se compara con la información del Claim y del Case.

Se revisan cinco criterios:

- El modelo coincide.
- El número de serie coincide.
- El informe muestra el componente reclamado.
- Las imágenes evidencian la falla descrita.
- Existen imágenes de antes y después de la reparación.

El puntaje se calcula proporcionalmente. Por ejemplo, 4 de 5 criterios cumplidos representan el 80% de la ponderación del informe técnico.

La columna de fotografías se conserva para compatibilidad histórica, pero su ponderación es 0% porque las fotografías están integradas en este criterio.

### 5. PLM - 5%

Se valida:

- Modelo.
- Número de serie.
- Que la información o fecha del documento esté dentro del período válido.

El período válido es:

- El último año contado hacia atrás desde la fecha de falla.
- Si el equipo tiene menos de un año, desde `MachineCommissionedDate__c` hasta la fecha de falla.

Si hay archivos PLM detectados por nombre pero en formato no legible por la IA (ej. ZIP), se otorga puntaje parcial por presencia: mitad de la ponderación (2.5%) con razón que lista los nombres.

Para SK - Repair prior to commissioning y MA - Missing or Damaged Part prior to commissioning el PLM no es requerido: puntaje máximo (5%) con razón `no es requerido PLM.`, sin validación.

### 6. Oil Analysis - 5%

Este criterio solo aplica cuando el componente utiliza aceite hidráulico.

Cuando aplica, se valida:

- Máquina o modelo.
- Número de serie.
- Componente analizado.

Cuando el componente no utiliza aceite hidráulico:

- El resultado se marca como **No aplica**.
- Se asigna el 100% de la ponderación, equivalente a 5 puntos porcentuales.

### 7. Datapacks - 5%

- Solo se verifica que exista al menos un Datapack asociado al reclamo.
- No se evalúa su contenido técnico dentro de este criterio.

### 8. Work Order - 10%

Se valida:

- Número de Work Order.
- Máquina y número de serie.
- Fecha del documento.
- La fecha debe ser igual o posterior a la fecha de falla.
- La fecha debe estar como máximo 10 días después de la falla.
- Descripción del trabajo realizado.
- Relación del trabajo con el TSI, el Claim y la corrección reportada.
- Componente intervenido.
- Descripción escrita en inglés.

El puntaje se calcula proporcionalmente según los criterios cumplidos.

### 9. Invoice - 10%

Si `Claim.PartsRequestedQuantity__c` es 0 (o vacío/ilegible), no se exigen facturas: puntaje máximo (10%) con razón `no es requerida la factura, partes solicitadas = 0.`, sin análisis IA. Solo con partes > 0 se validan las facturas:

- Número de parte.
- Fecha de compra.
- La fecha de compra debe ser anterior a la fecha de instalación o reemplazo.
- La fecha de compra debe ser anterior a la fecha de reparación.
- Cantidad facturada coherente con la cantidad reclamada.
- Coincidencia entre la pieza facturada y la pieza instalada y reclamada.

El puntaje se calcula proporcionalmente según los criterios cumplidos.

Para PC - Part DB Installed el gate de partes = 0 no aplica: siempre se exige doble factura (falla + instalada), sin cálculo de vigencia. Con menos de 2 respaldos = 0. Misma escala 0.10 con 5 criterios (factura1 legible, match falla, factura2 legible, match instalada, cantidades).

Para Chile (`Claim_country__c = CL`), el respaldo suele ser un recorte SAP (Visual.KCC Orden Garantía) en vez de factura tradicional. Si el país viene vacío, se usa la oficina del Case (`Sales_Office__c` Komatsu Chile / JGI Chile) para aplicar la misma variante. La IA auto-detecta el tipo: si es recorte SAP evalúa número de orden ZM01, parte en la columna Componente, cantidad en Ctd.neces., denominación relacionada y layout SAP reconocible; si es factura tradicional aplica los criterios anteriores. Misma escala 0.10. Si no hay documentos en la categoría invoice pero aplica la variante SAP, se evalúan las fotografías como posible captura SAP.

## Resultado De La Evaluación

Cada criterio puede obtener:

- **Puntaje completo:** todos sus criterios se cumplen.
- **Puntaje parcial:** solo algunos criterios se cumplen.
- **0 puntos:** el documento falta, existe una contradicción o no se cumple ningún criterio.
- **No aplica:** el criterio no corresponde al caso y se asigna el total de su ponderación cuando la regla lo establece, como en Oil Analysis para componentes que no utilizan aceite hidráulico.

Las razones describen los criterios cumplidos, los datos faltantes y las contradicciones encontradas.

## Clasificación De Adjuntos

Los adjuntos se rutean por contenido con IA, no por título: PLM y datapacks conservan keywords; los videos van a fotografías por extensión; los ZIPs no visibles van a datapacks u otro; todo lo demás legible (imagen, PDF, Excel, Word, CSV/TXT/EML/HTML) lo clasifica la IA por contenido (incluye recortes SAP como invoice).

## Columnas De Resultados

Los puntajes y razones se guardan en las columnas existentes:

| Resultado | Puntaje | Razón |
| --- | --- | --- |
| Informe técnico | `attachments_technical_report_sf` | `attachments_technical_report_sf_reason` |
| PLM | `attachments_plm` | `attachments_plm_reason` |
| Oil Analysis | `attachments_oil_analysis` | `attachments_oil_analysis_reason` |
| Datapacks | `attachments_datapacks` | `attachments_datapacks_reason` |
| Work Order | `work_order` | `work_order_reason` |
| Invoice | `invoices` | `invoices_reason` |
| Costo IA estimado | `ia_estimated_cost_usd` | — |
| Llamadas IA | `ia_calls` | — |
| Tokens IA entrada/salida | `ia_input_tokens` / `ia_output_tokens` | — |

El costo IA se calcula por reclamo desde los tokens reales (`usage`) de cada llamada a GPT-4.1: `(in × tarifa_in + out × tarifa_out) / 1M`. Tarifas por defecto `$2.00/$8.00` por millón (sobre-escribibles con `IA_PRICE_INPUT_USD_PER_MTOK` e `IA_PRICE_OUTPUT_USD_PER_MTOK`). Cada intento cuenta; aciertos de caché cuestan 0. Históricos previos quedan en NULL.

También se conservan datos de contexto como modelo, serial, fechas, tipo de cobertura y cantidad de adjuntos encontrados en Claim y Case.
