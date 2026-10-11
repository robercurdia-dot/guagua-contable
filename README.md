# guagua-contable

Motor de facturación con cumplimiento **Verifactu** (AEAT, España).
Python 3.11+ · FastAPI · PostgreSQL 16 · SQLAlchemy 2.

Calcula una factura, la encadena con el registro anterior, genera el XML y lo
valida contra el esquema oficial de la Agencia Tributaria, listo para enviarlo
a su servicio web. El sistema de facturación tiene que cumplir la normativa
antifraude española (obligatoria desde enero de 2027 para sociedades y julio de
2027 para autónomos), y buena parte del trabajo está en que ese cumplimiento
sea verificable y no una suposición.

> **Estado: en desarrollo.** Todavía no se ha enviado ningún registro a la AEAT:
> falta el certificado electrónico, y el cliente SOAP está probado con
> respuestas simuladas. No es un producto en producción.

## Decisiones de diseño que merecen mención

**La huella se valida contra los ejemplos oficiales, no contra mi implementación.**
El hash encadenado de cada registro reproduce bit a bit los tres vectores de la
especificación de la AEAT. Están fijados como tests: si el cálculo se desvía,
la AEAT marcaría el registro «aceptado con errores».

**El XML se valida contra el XSD oficial.** El orden de los elementos lo manda
el esquema. Esto reveló un fallo real del modelo inicial: el encadenamiento
exige la identidad completa del registro anterior (NIF, número y fecha), no solo
su huella, y el primer registro lleva `PrimerRegistro` en lugar de una huella
vacía.

**El dinero es `Decimal` con `ROUND_HALF_UP`, nunca `float`.** La cuota de IVA
se calcula sobre la base agregada por tipo, no línea a línea, para no acumular
error de redondeo. Estos importes entran literalmente en la huella: un céntimo
de diferencia la cambia.

**La cadena de registros no se bifurca con emisiones concurrentes.** La cadena
es única por obligado, no por serie. Emitir bloquea la fila de la organización
(`SELECT … FOR UPDATE`), que además guarda la punta de la cadena. Un test lanza
20 emisiones simultáneas en hilos y conexiones separadas; quitando el bloqueo,
los tres tests de concurrencia fallan.

**Aislamiento entre empresas en la base de datos.** Row-Level Security forzado,
con la empresa fijada por transacción (`set_config`). Sin empresa fijada no se
ve nada: falla en cerrado. Los registros de facturación son inalterables por
triggers. Todo verificado contra un Postgres real; una de esas verificaciones
descubrió que `SET LOCAL` no admite parámetros vinculados.

**Interpretar la respuesta de la AEAT sin duplicar registros.** Un registro
«aceptado con errores» ya está almacenado en la AEAT; reenviarlo crea un
duplicado. El tipo `Respuesta` separa `almacenado_en_aeat`, `debe_reenviarse` y
`necesita_subsanacion`, y solo se reintentan automáticamente los fallos de red
y 5xx.

## Estado

| Pieza | Estado |
|---|---|
| Huella y encadenamiento | Validado contra los 3 vectores oficiales |
| XML de alta y anulación | Valida contra el XSD oficial |
| Código QR | Contrastado con la especificación v0.5.0 y su ejemplo |
| Cálculo de factura (IVA, recargo de equivalencia) | Implementado y testeado |
| Emisión persistida y concurrencia | Implementado, probado con Postgres real |
| RLS y registros inalterables | Verificado con Postgres real |
| Cliente SOAP + interpretación de respuesta | Probado con respuestas simuladas |
| Envío real a la AEAT | **Pendiente: certificado electrónico** |
| La API usa la emisión persistida | Pendiente (hoy calcula y devuelve) |
| Firma XAdES (modo No-Verifactu) | Pendiente |
| Usuarios, roles y multiempresa | Pendiente; hoy hay una clave de API única |
| Contabilidad de partida doble, conciliación, modelo 303 | Fases posteriores, no iniciadas |

**164 tests**, `ruff` limpio y CI en GitHub Actions con Postgres.

## Estructura

```
src/app/
  verifactu/     Motor aislado: huella, XML, QR, SOAP, errores, esquemas AEAT
  facturacion/   Cálculo, numeración, emisión y anulación
  servicios/     Emisión persistida y contexto de empresa (tenant)
  models/        SQLAlchemy 2
  api/           FastAPI: emitir, anular, verificar cadena
migrations/      Alembic: esquema, RLS y triggers de inalterabilidad
docs/            Plan técnico y documentación oficial de la AEAT
tests/
```

`verifactu/` no depende del resto de la aplicación. Los XSD, el WSDL y el
catálogo de errores oficiales están en `src/app/verifactu/schemas/`; el único
cambio es redirigir el import de `xmldsig-core-schema.xsd` a una copia local
para poder validar sin red.

## Puesta en marcha

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q          # los tests que necesitan Postgres se saltan solos si no hay base
```

Con Postgres, para ejecutar también esos 32 tests:

```bash
docker compose up -d db      # crea el rol "guagua" y las bases guagua y guagua_test
alembic upgrade head
pytest -q
```

Sin Docker: instala Postgres 16 y crea el rol y las bases a mano
(`CREATE ROLE guagua LOGIN PASSWORD 'guagua' CREATEDB;`, ver `docker/init.sql`).
**El rol de la aplicación no puede ser superusuario**: los superusuarios se
saltan el RLS aunque esté forzado.

API:

```bash
API_KEY=una-clave uvicorn app.main:app --app-dir src --reload   # http://localhost:8000/docs

curl -s -X POST http://localhost:8000/facturas/emitir \
  -H 'X-API-Key: una-clave' -H 'content-type: application/json' \
  -d '{"nif_emisor":"B12345678","serie":"A/2026","ultimo_numero":0,
       "fecha_expedicion":"2026-01-15","generado_en":"2026-01-15T10:30:00+01:00",
       "lineas":[{"descripcion":"Consultoría","cantidad":"10","precio":"60"}]}'
```

Sin `API_KEY` configurada la API responde 503 en lugar de quedarse abierta.

## Documentación

- `docs/PLAN.md`: plan técnico y desglose de fases.
- `docs/GUIA.md`: qué hace cada módulo y qué falta para entregarlo.
- `docs/aeat/`: especificaciones oficiales de la AEAT en las que se apoya el código.
