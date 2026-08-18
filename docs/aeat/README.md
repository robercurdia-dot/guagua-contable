# Documentacion oficial AEAT (fuente de verdad)

| Fichero | Documento | Version | Estado |
|---|---|---|---|
| `AEAT_especificaciones_huella_hash_v0.1.2.pdf` | Especificaciones tecnicas para generacion de la huella o hash de los registros de facturacion | 0.1.2 (27/08/2024) | **Implementado y validado** |

Origen:
https://www.agenciatributaria.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/Veri-Factu_especificaciones_huella_hash_registros.pdf

## Resumen del algoritmo de huella (implementado en `app/verifactu/huella.py`)

- **Algoritmo**: SHA-256 (unico permitido, Lista L12 del anexo de la orden).
- **Cadena de entrada**: `nombreCampo1=valor1&nombreCampo2=valor2&...`
- **Valores**: se eliminan espacios al inicio y al final. Campo sin valor ->
  solo el nombre y `=` (p.ej. primer registro: `&Huella=&`).
- **Numericos**: una o dos posiciones decimales son indistintas; los ceros a la
  derecha no son relevantes (`123.1` == `123.10`).
- **Codificacion**: UTF-8.
- **Salida**: hexadecimal, MAYUSCULAS, 64 caracteres.

Orden de campos (no reordenar):

- **Alta**: IDEmisorFactura, NumSerieFactura, FechaExpedicionFactura,
  TipoFactura, CuotaTotal, ImporteTotal, Huella (la del registro anterior),
  FechaHoraHusoGenRegistro.
- **Anulacion**: IDEmisorFacturaAnulada, NumSerieFacturaAnulada,
  FechaExpedicionFacturaAnulada, Huella, FechaHoraHusoGenRegistro.
- **Evento**: NIF, ID, IdSistemaInformatico, Version, NumeroInstalacion, NIF
  (ObligadoEmision), TipoEvento, HuellaEvento, FechaHoraHusoGenEvento.

> Si la huella informada no coincide con el calculo de la AEAT, el registro se
> marca como **"Aceptado con errores"**. Por eso los vectores oficiales estan
> clavados en `tests/test_huella_vectores_aeat.py` y corren en CI.

## Pendiente de descargar

- Diseno de registros + **XSD** de los servicios web (para `verifactu/xml.py`).
- Especificaciones del **QR** (confirmar URL de cotejo y parametros).
- Especificaciones de la **firma electronica** (XAdES, solo No-Verifactu).
- Documentacion del **web service** de remision (SOAP, entorno de pruebas).
