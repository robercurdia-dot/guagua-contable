# guagua-contable

Software de contabilidad y facturacion para autonomos, pymes y despachos, con
**Verifactu** como base legal. Producto de The Guagua Project · AI.

Estado: **Fase 0–1** (esqueleto + motor Verifactu). Ver `docs/PLAN.md`.

## Arquitectura

- **API**: Python 3.12 + FastAPI
- **Datos**: PostgreSQL 16 + SQLAlchemy 2 (Alembic para migraciones)
- **Motor Verifactu**: paquete aislado en `src/app/verifactu/` (sin dependencias
  de la app: hashlib, segno para QR). Se puede extraer a servicio propio.
- **Cola/async**: Redis (para el envio a AEAT con reintentos)

## Estado

| Pieza | Estado |
|---|---|
| Motor de huella Verifactu | **Validado contra los 3 vectores oficiales AEAT** |
| Calculo de factura (IVA, recargo, totales) | Implementado y testeado |
| Emision + anulacion encadenada | Implementado y testeado |
| API de facturacion | Implementada (sin persistencia todavia) |
| Migraciones + RLS + append-only | **Verificadas contra Postgres 16 real** |
| Emision persistida | Implementada, con bloqueo que impide bifurcar la cadena |
| Usuarios, roles y auth de API | Pendiente (resto de E5) |
| Serializacion XML | **Valida contra el XSD oficial de la AEAT** |
| Catalogo de errores AEAT | Cargado y clasificado por severidad |
| Endpoints del web service | Confirmados desde el WSDL oficial |
| Cliente SOAP + cola de envio | Pendiente (E1) |
| Codigo QR | **Confirmado contra la spec oficial v0.5.0**, reproduce el vector de ejemplo |
| Persistencia + auth multi-tenant | Pendiente (E5) |

139 tests, `ruff` limpio. 32 de ellos necesitan Postgres y se saltan solos si
no hay base a mano.

### Base de datos para desarrollo

```bash
brew install postgresql@16 && brew services start postgresql@16
createdb -O guagua guagua && createdb -O guagua guagua_test
alembic upgrade head
```

## Documentacion oficial de la AEAT

En `src/app/verifactu/schemas/` estan los XSD, el WSDL y el catalogo de errores
oficiales. Son la fuente de verdad: el codigo se valida contra ellos, no contra
lo que creamos recordar.

El unico cambio que se les ha hecho es redirigir el import de
`xmldsig-core-schema.xsd` de w3.org al fichero local, para poder validar sin red.

## El motor Verifactu (corazon del producto)

`src/app/verifactu/`:

- `huella.py` — hash chain SHA-256 (encadenamiento de registros).
  **Gate de la Fase 0: SUPERADO** — reproduce bit a bit los 3 vectores de
  ejemplo oficiales de la AEAT (spec 0.1.2). Cubre alta, anulacion y evento.
- `registros.py` — construccion de registros de alta / anulacion.
- `qr.py` — URL de cotejo AEAT + PNG del QR.
- `modos.py` — VERIFACTU vs NO_VERIFACTU.

`src/app/facturacion/`:

- `calculo.py` — bases, desglose de IVA, recargo de equivalencia y totales.
  Todo con `Decimal` y `ROUND_HALF_UP`; la cuota se calcula sobre la base
  AGREGADA por tipo, no linea a linea (evita acumular error de redondeo).
  **Estos importes entran literalmente en la huella**: un centimo de diferencia
  cambia el hash y la AEAT marca el registro "Aceptado con errores".
- `numeracion.py` — numeracion correlativa por serie.
- `emision.py` — emitir / anular generando el registro encadenado.

> Orden y formato de los campos implementados contra el documento oficial de la
> AEAT (copia en `docs/aeat/`). Los vectores oficiales estan clavados en
> `tests/test_huella_vectores_aeat.py` y corren en CI: si la huella no coincide
> con el calculo de la AEAT, el registro se marca "Aceptado con errores".

## Puesta en marcha (dev)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# infra local
docker compose up -d db redis

# tests (el motor Verifactu no necesita DB)
pytest -q

# API
uvicorn app.main:app --reload --app-dir src
# -> http://localhost:8000/docs
```

Emitir una factura (sin DB):

```bash
curl -s -X POST http://localhost:8000/facturas/emitir \
  -H 'content-type: application/json' \
  -d '{"nif_emisor":"B12345678","serie":"A/2026","ultimo_numero":0,
       "fecha_expedicion":"2026-01-15","generado_en":"2026-01-15T10:30:00+01:00",
       "lineas":[{"descripcion":"Consultoria","cantidad":"10","precio":"60"}]}'
```

Endpoints: `POST /facturas/emitir`, `POST /facturas/anular`,
`POST /facturas/verificar-cadena`.

## Proximos pasos

Ver `docs/PLAN.md` (roadmap Fase 0–1).

- [x] **Huella validada contra los vectores oficiales de la AEAT** (gate Fase 0)
- [x] Motor de calculo de factura (IVA, recargo, desglose, totales)
- [x] Emision / anulacion con encadenamiento verificable
- [x] Migraciones con RLS y append-only *(escritas; falta probarlas con Postgres)*
- [ ] Descargar diseno de registros + XSD oficiales *(en curso: cowork)*
- [ ] Serializacion a XML contra el XSD (`verifactu/xml.py`)
- [ ] Cliente del web service AEAT (pruebas) con cola de reintentos
- [x] Confirmar URL/parametros del QR contra la spec oficial
- [ ] Persistencia + auth multi-tenant (E5)
- [ ] Modelo 303 (E4)
