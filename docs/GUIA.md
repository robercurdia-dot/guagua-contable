# Guagua Contable — guía de entrega

Motor de facturación con cumplimiento Verifactu para la AEAT.
Versión web de este documento: https://claude.ai/code/artifact/1611b33b-ed3b-449a-9a97-5943d0eb6e7c

## Estado

164 tests en verde · 2.383 líneas · lo único que falta para enviar de verdad es el certificado.

El ciclo completo funciona y está probado: calcular una factura, encadenarla,
generar el XML y validarlo contra el esquema oficial de la AEAT.

## Las herramientas

### Motor Verifactu — el núcleo legal (no depende del resto)

| Módulo | Qué hace | Cómo se usa |
|---|---|---|
| `verifactu/huella.py` | Hash SHA-256 de cada registro, encadenado con el anterior | Es lo que valida la AEAT. Reproduce los 3 ejemplos oficiales; no tocar sin repasarlos |
| `verifactu/xml.py` | Convierte los registros al XML de la AEAT y lo valida | El orden de los campos lo manda el esquema. Reordenar = deja de validar |
| `verifactu/soap.py` | Envía los lotes y gestiona reintentos | Aquí se enchufa el certificado. Hoy usa transporte simulado |
| `verifactu/respuesta.py` | Interpreta lo que contesta la AEAT | Usa `a_reenviar()`. Nunca reenviar a ojo |
| `verifactu/qr.py` | El QR impreso en la factura | Verifactu y No-Verifactu usan direcciones distintas (parámetro `modo`) |
| `verifactu/errores.py` | Catálogo de errores de la AEAT por gravedad | Separa lo reenviable de lo que solo hay que subsanar |
| `verifactu/endpoints.py` | Direcciones del servicio | Por defecto pruebas; producción se pide a propósito |
| `verifactu/schemas/` | Esquemas y errores oficiales | Fuente de verdad. Ante la duda, se mira aquí |

### Facturación — los importes que entran en el hash legal

| Módulo | Qué hace | Cómo se usa |
|---|---|---|
| `facturacion/calculo.py` | Bases, IVA, recargo y totales | Decimales exactos, nunca coma flotante |
| `facturacion/emision.py` | Emite y anula encadenando | Anular no borra: genera otro registro |
| `facturacion/numeracion.py` | Numeración correlativa por serie | Los números no se reutilizan |

### Persistencia

| Módulo | Qué hace | Cómo se usa |
|---|---|---|
| `servicios/emision_persistida.py` | Emite y guarda en un paso indivisible | Bloquea la empresa. Sin ese bloqueo, dos facturas a la vez parten la cadena |
| `servicios/tenant.py` | Fija de qué empresa es cada consulta | Si se olvida, no se ve nada en vez de verse todo |
| `migrations/` | Esquema, aislamiento e inmutabilidad | La base impide borrar o alterar registros aunque el código lo intente |

### API

| Módulo | Qué hace | Cómo se usa |
|---|---|---|
| `api/facturas.py` | Emitir, anular, verificar cadena | Todavía sin guardar en base de datos |
| `api/auth.py` | Clave por cabecera | Provisional: solo evita dejar la puerta abierta |

## Cómo se usa

```bash
# base de datos
brew install postgresql@16 && brew services start postgresql@16
createdb -O guagua guagua && createdb -O guagua guagua_test
alembic upgrade head

# arrancar y probar
uvicorn app.main:app --app-dir src --reload
pytest
ruff check src tests migrations
```

Los 32 tests que necesitan Postgres se saltan solos si no hay base de datos.

## Qué falta para entregarlo

1. **Conseguir el certificado electrónico.** Único punto que depende de terceros.
   Antes de un trámite nuevo, comprobar si ya hay uno de representante o sello.
2. **Convertirlo a PEM.** Si es `.p12` de la FNMT, los comandos están en `soap.py`.
3. **Enchufarlo al cliente.** `Certificado(ruta_cert=…, ruta_clave=…)` y quitar el
   transporte simulado. Dos líneas.
4. **Probar contra el entorno de pruebas de la AEAT.** Primer envío real.
5. **Conectar la API con la base de datos.** La lógica de guardado ya existe y está
   probada; falta unirlas.
6. **Usuarios y permisos.** Para despachos multiempresa. Trabajo de producto.

## Reglas que no conviene romper

- **Un registro «aceptado con errores» ya está guardado en la AEAT.** No se reenvía:
  se corrige. Reenviarlo crea un duplicado en Hacienda.
- **El dinero se calcula con decimales exactos.** El IVA, sobre el total de cada tipo,
  no línea a línea. Cambiarlo desplaza céntimos y el hash deja de coincidir.
- **El orden de los campos del XML lo manda el esquema.** Reordenar = rechazo del envío.
- **Las facturas no se editan ni se borran.** Se anulan con otro registro encadenado.
- **Ante la duda, manda el documento de la AEAT** (`verifactu/schemas/`, `docs/aeat/`).
  Las suposiciones razonables ya han fallado una vez aquí.

---

Plazos legales: obligatorio desde el 1-ene-2027 (sociedades) y el 1-jul-2027 (autónomos).
