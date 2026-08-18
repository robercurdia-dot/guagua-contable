"""Punta de la cadena Verifactu en la organizacion.

Revision ID: 0002
Revises: 0001

POR QUE: la cadena de registros es UNICA por obligado/SIF, no por serie. Al
emitir hay que (a) leer el ultimo registro y (b) anadir el siguiente sin que
dos emisiones simultaneas lean el mismo "ultimo" y BIFURQUEN la cadena.

Guardar la punta en la propia fila de organizacion permite hacerlo atomico:
se bloquea esa fila (SELECT ... FOR UPDATE), se lee la punta y se actualiza en
la misma transaccion. Una bifurcacion es una anomalia de trazabilidad de las
que el SIF esta obligado a detectar y registrar como evento (tipos 04-08 de
EventosSIF.xsd); es mejor hacerla imposible que detectarla despues.

Se guarda la identidad COMPLETA del ultimo registro porque el XSD
(EncadenamientoFacturaAnteriorType) exige NIF + num/serie + fecha ademas de la
huella.
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizacion",
                  sa.Column("cadena_huella", sa.String(64), nullable=False, server_default=""))
    op.add_column("organizacion",
                  sa.Column("cadena_num_serie", sa.String(60), nullable=False, server_default=""))
    op.add_column("organizacion",
                  sa.Column("cadena_fecha_expedicion", sa.String(10), nullable=False, server_default=""))


def downgrade() -> None:
    for c in ("cadena_fecha_expedicion", "cadena_num_serie", "cadena_huella"):
        op.drop_column("organizacion", c)
