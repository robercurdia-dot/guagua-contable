# Plan tecnico ejecutable — resumen

Documento maestro: `plan_tecnico_ejecutable.docx` (fuera del repo, entregado
al equipo). Resumen de secuencia de la Fase 0–1:

## Fase 0 (0–6 sem) — Motor Verifactu (spike). DoD:
1. Huella coincide con ejemplos oficiales de la AEAT.
2. XML de alta/anulacion valida contra XSD.
3. QR con URL de cotejo correcta.
4. Envio de lote de prueba a preproduccion AEAT + respuesta por registro.
5. Decision de modo documentada (recomendado: VERIFACTU).
6. Modelo de datos revisado por perfil fiscal.

## Fase 1 (2–4 meses) — MVP legal. Epicas:
- E1 Nucleo Verifactu (integrar motor + envio AEAT)
- E2 Facturacion de venta (series, IVA, PDF con QR, rectificativas)
- E3 Clientes y productos
- E4 Modelo 303 basico
- E5 Cuentas, auth y multi-tenant (RLS)
- E6 Infra y DevOps

## Secuencia: Fase 0 -> E6 -> E5 -> E2 -> E1 (AEAT preprod) -> E3/E4 -> prod.
