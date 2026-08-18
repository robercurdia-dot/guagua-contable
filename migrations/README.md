# Migraciones (Alembic)

Pendiente de inicializar en la epica E6:

    alembic init migrations

Requisitos de esquema ya decididos:

- **Row-Level Security** en cada tabla con `organizacion_id` (aislamiento
  multi-tenant). Ejemplo de politica por tabla:

      ALTER TABLE factura ENABLE ROW LEVEL SECURITY;
      CREATE POLICY tenant_isolation ON factura
        USING (organizacion_id = current_setting('app.organizacion_id')::text);

- **Append-only** en `registro_facturacion`: revocar UPDATE/DELETE a nivel de
  rol de aplicacion; solo INSERT. La anulacion es un nuevo registro encadenado.
