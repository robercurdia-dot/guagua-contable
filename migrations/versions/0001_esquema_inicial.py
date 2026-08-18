"""Esquema inicial: facturacion, Verifactu, multi-tenant (RLS) y append-only.

Revision ID: 0001
Revises:
Create Date: 2026-08-18

Decisiones que esta migracion implementa (ver docs/PLAN.md):
  - Aislamiento multi-tenant por Row-Level Security sobre organizacion_id.
  - registro_facturacion es APPEND-ONLY: se revoca UPDATE/DELETE y se refuerza
    con un trigger. Una factura no se corrige: se anula con un registro de
    anulacion encadenado.
  - Numeracion de facturas correlativa y unica por (organizacion, serie).
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Tablas de negocio sujetas a aislamiento multi-tenant.
TABLAS_TENANT = (
    "serie", "cliente", "producto", "factura", "linea_factura",
    "registro_facturacion", "evento_sif",
)


def upgrade() -> None:
    op.create_table(
        "organizacion",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("nif", sa.String(20), nullable=False, unique=True),
        sa.Column("razon_social", sa.String(255), nullable=False),
        sa.Column("modo_operacion", sa.String(20), nullable=False,
                  server_default="VERIFACTU"),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("modo_operacion IN ('VERIFACTU','NO_VERIFACTU')",
                           name="ck_organizacion_modo"),
    )

    op.create_table(
        "serie",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organizacion_id", sa.String(36), sa.ForeignKey("organizacion.id"),
                  nullable=False, index=True),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("ultimo_numero", sa.Integer, nullable=False, server_default="0"),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organizacion_id", "codigo", name="uq_serie_org_codigo"),
        sa.CheckConstraint("ultimo_numero >= 0", name="ck_serie_numero_no_negativo"),
    )

    op.create_table(
        "cliente",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organizacion_id", sa.String(36), sa.ForeignKey("organizacion.id"),
                  nullable=False, index=True),
        sa.Column("nif", sa.String(20), nullable=False, index=True),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "producto",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organizacion_id", sa.String(36), sa.ForeignKey("organizacion.id"),
                  nullable=False, index=True),
        sa.Column("descripcion", sa.String(255), nullable=False),
        sa.Column("precio", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tipo_iva", sa.Numeric(5, 2), nullable=False, server_default="21"),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "factura",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organizacion_id", sa.String(36), sa.ForeignKey("organizacion.id"),
                  nullable=False, index=True),
        sa.Column("serie_id", sa.String(36), sa.ForeignKey("serie.id"), nullable=False),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("fecha_expedicion", sa.Date, nullable=False),
        sa.Column("tipo_factura", sa.String(4), nullable=False, server_default="F1"),
        sa.Column("cliente_id", sa.String(36), sa.ForeignKey("cliente.id"), nullable=False),
        sa.Column("base_imponible", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cuota_iva", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("estado", sa.String(20), nullable=False, server_default="emitida"),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # Numeracion correlativa sin huecos ni duplicados dentro de la serie.
        sa.UniqueConstraint("organizacion_id", "serie_id", "numero",
                            name="uq_factura_org_serie_numero"),
        sa.CheckConstraint("numero > 0", name="ck_factura_numero_positivo"),
    )

    op.create_table(
        "linea_factura",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organizacion_id", sa.String(36), sa.ForeignKey("organizacion.id"),
                  nullable=False, index=True),
        sa.Column("factura_id", sa.String(36), sa.ForeignKey("factura.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("descripcion", sa.String(255), nullable=False),
        sa.Column("cantidad", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("precio", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tipo_iva", sa.Numeric(5, 2), nullable=False, server_default="21"),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "registro_facturacion",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organizacion_id", sa.String(36), sa.ForeignKey("organizacion.id"),
                  nullable=False, index=True),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("factura_id", sa.String(36), nullable=False, index=True),
        sa.Column("huella", sa.String(64), nullable=False, index=True),
        sa.Column("huella_anterior", sa.String(64), nullable=False, server_default=""),
        sa.Column("fecha_hora_huso", sa.String(40), nullable=False),
        sa.Column("xml", sa.Text, nullable=False, server_default=""),
        sa.Column("estado_aeat", sa.String(24), nullable=False, server_default="pendiente"),
        sa.Column("respuesta_aeat", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("tipo IN ('alta','anulacion')", name="ck_registro_tipo"),
        sa.CheckConstraint(
            "estado_aeat IN ('pendiente','enviado','aceptado','aceptado_con_errores','rechazado')",
            name="ck_registro_estado_aeat"),
        # La huella es unica dentro de la organizacion (detecta duplicados).
        sa.UniqueConstraint("organizacion_id", "huella", name="uq_registro_org_huella"),
    )

    op.create_table(
        "evento_sif",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organizacion_id", sa.String(36), sa.ForeignKey("organizacion.id"),
                  nullable=False, index=True),
        sa.Column("tipo_evento", sa.String(40), nullable=False),
        sa.Column("detalle", sa.Text, nullable=False, server_default=""),
        sa.Column("ocurrido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---------------- Multi-tenant: Row-Level Security ----------------
    # La app fija el tenant por sesion con:  SET LOCAL app.organizacion_id = '<id>'
    # Ninguna consulta puede ver filas de otra organizacion.
    for tabla in TABLAS_TENANT:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_aislamiento ON {tabla}
            USING (organizacion_id = current_setting('app.organizacion_id', true))
            WITH CHECK (organizacion_id = current_setting('app.organizacion_id', true))
        """)

    # ---------------- registro_facturacion: APPEND-ONLY ----------------
    # Requisito legal de inalterabilidad: los registros no se editan ni borran.
    # Excepcion controlada: el estado del envio a AEAT SI debe poder anotarse,
    # pero solo esos campos y nunca los que entran en la huella.
    op.execute("""
        CREATE OR REPLACE FUNCTION registro_facturacion_append_only()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION
                    'registro_facturacion es append-only: no se puede borrar (id=%)', OLD.id;
            END IF;

            -- Solo se permite actualizar el resultado del envio a la AEAT.
            IF NEW.id                IS DISTINCT FROM OLD.id
            OR NEW.organizacion_id   IS DISTINCT FROM OLD.organizacion_id
            OR NEW.tipo              IS DISTINCT FROM OLD.tipo
            OR NEW.factura_id        IS DISTINCT FROM OLD.factura_id
            OR NEW.huella            IS DISTINCT FROM OLD.huella
            OR NEW.huella_anterior   IS DISTINCT FROM OLD.huella_anterior
            OR NEW.fecha_hora_huso   IS DISTINCT FROM OLD.fecha_hora_huso
            OR NEW.xml               IS DISTINCT FROM OLD.xml
            OR NEW.creado_en         IS DISTINCT FROM OLD.creado_en THEN
                RAISE EXCEPTION
                    'registro_facturacion es inalterable: solo se puede actualizar el estado del envio a AEAT (id=%)', OLD.id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_registro_facturacion_append_only
        BEFORE UPDATE OR DELETE ON registro_facturacion
        FOR EACH ROW EXECUTE FUNCTION registro_facturacion_append_only();
    """)

    # Lo mismo para el registro de eventos del SIF.
    op.execute("""
        CREATE OR REPLACE FUNCTION evento_sif_append_only()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'evento_sif es append-only (id=%)', OLD.id;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_evento_sif_append_only
        BEFORE UPDATE OR DELETE ON evento_sif
        FOR EACH ROW EXECUTE FUNCTION evento_sif_append_only();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_evento_sif_append_only ON evento_sif")
    op.execute("DROP FUNCTION IF EXISTS evento_sif_append_only()")
    op.execute("DROP TRIGGER IF EXISTS trg_registro_facturacion_append_only ON registro_facturacion")
    op.execute("DROP FUNCTION IF EXISTS registro_facturacion_append_only()")
    for tabla in TABLAS_TENANT:
        op.execute(f"DROP POLICY IF EXISTS tenant_aislamiento ON {tabla}")
    for tabla in ("evento_sif", "registro_facturacion", "linea_factura", "factura",
                  "producto", "cliente", "serie", "organizacion"):
        op.drop_table(tabla)
