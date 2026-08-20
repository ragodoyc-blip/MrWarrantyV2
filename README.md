# Mr. Warranty

## Objetivo

Mr. Warranty evalúa reclamos de **Factory Warranty** provenientes de Salesforce. El sistema revisa la información del reclamo, el caso técnico asociado y los documentos adjuntos, y genera un puntaje con las razones de cada resultado.

La evaluación busca identificar rápidamente si la evidencia presentada es coherente con la falla, la reparación y el componente reclamado.

## Tipos De Factory Warranty

### Factory Warranty normal

La vigencia se calcula usando la fecha de puesta en marcha del equipo (`MachineCommissionedDate__c`) y la fecha de falla.

### PC - Parts and Components

La vigencia se calcula usando la fecha de instalación o reemplazo de la pieza y la fecha de falla. El resto de los criterios documentales se evalúa de la misma forma.

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

Para Factory Warranty normal:

- Se compara la fecha de puesta en marcha del equipo con la fecha de falla.
- Si han transcurrido 365 días o menos, la garantía está vigente.
- Si han transcurrido 366 días o más, la garantía se considera expirada.

Para PC:

- Se compara la fecha de instalación o reemplazo de la pieza con la fecha de falla.
- Si no se puede determinar la fecha de instalación, el criterio obtiene 0 puntos.

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

Se valida:

- Número de parte.
- Fecha de compra.
- La fecha de compra debe ser anterior a la fecha de instalación o reemplazo.
- La fecha de compra debe ser anterior a la fecha de reparación.
- Cantidad facturada coherente con la cantidad reclamada.
- Coincidencia entre la pieza facturada y la pieza instalada y reclamada.

El puntaje se calcula proporcionalmente según los criterios cumplidos.

## Resultado De La Evaluación

Cada criterio puede obtener:

- **Puntaje completo:** todos sus criterios se cumplen.
- **Puntaje parcial:** solo algunos criterios se cumplen.
- **0 puntos:** el documento falta, existe una contradicción o no se cumple ningún criterio.
- **No aplica:** el criterio no corresponde al caso y se asigna el total de su ponderación cuando la regla lo establece, como en Oil Analysis para componentes que no utilizan aceite hidráulico.

Las razones describen los criterios cumplidos, los datos faltantes y las contradicciones encontradas.

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

También se conservan datos de contexto como modelo, serial, fechas, tipo de cobertura y cantidad de adjuntos encontrados en Claim y Case.
