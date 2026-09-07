"""Datos de prueba para el entorno de desarrollo (sección 33 del brief).

Uso: ``python -m app.db.seed`` desde ``backend/`` con el entorno virtual activado y
``DATABASE_URL`` apuntando a la base de datos de desarrollo (NUNCA a producción).

Todos los datos son ficticios. No usar información real de la empresa.
"""
from __future__ import annotations

from app.core.permissions import UserRole
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.customer import Customer
from app.models.machine import Machine
from app.models.user import User


def seed() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("Ya existen usuarios en la base de datos. Seed abortado para no duplicar datos.")
            return

        pedro = User(
            nombre="Pedro",
            apellido="Gerente",
            telefono_whatsapp="+56900000001",
            email="pedro.gerente@jacobea-dev.cl",
            password_hash=hash_password("dev12345"),
            cargo="Gerente General",
            area="Gerencia",
            sucursal="Santiago",
            rol=UserRole.GERENTE_GENERAL,
        )
        marcela = User(
            nombre="Marcela",
            apellido="Administración",
            telefono_whatsapp="+56900000002",
            email="marcela.admin@jacobea-dev.cl",
            password_hash=hash_password("dev12345"),
            cargo="Administración y Contabilidad",
            area="Administración",
            sucursal="Santiago",
            rol=UserRole.ADMINISTRACION,
        )
        juan = User(
            nombre="Juan",
            apellido="Técnico",
            telefono_whatsapp="+56900000003",
            cargo="Técnico",
            area="Servicio Técnico",
            sucursal="Santiago",
            rol=UserRole.TECNICO,
        )
        cristian = User(
            nombre="Cristian",
            apellido="Técnico",
            telefono_whatsapp="+56900000004",
            cargo="Técnico",
            area="Servicio Técnico",
            sucursal="Antofagasta",
            rol=UserRole.TECNICO,
        )
        db.add_all([pedro, marcela, juan, cristian])

        cliente_a = Customer(
            nombre="Cliente A", rut="76111111-1", ciudad="Santiago", comuna="Quilicura",
            contacto="Ana Pérez", telefono="+56911112222", tipo_cliente="empresa",
        )
        cliente_b = Customer(
            nombre="Cliente B", rut="76222222-2", ciudad="Antofagasta", comuna="Antofagasta",
            contacto="Luis Soto", telefono="+56933334444", tipo_cliente="empresa",
        )
        cliente_c = Customer(nombre="Cliente C", rut="76333333-3", ciudad="Santiago", tipo_cliente="empresa")
        db.add_all([cliente_a, cliente_b, cliente_c])
        db.flush()

        maquina_33 = Machine(
            numero_interno="33", marca="Toyota", modelo="8FG25", tipo="forklift",
            estado="operativa", cliente_id=cliente_a.id, horometro=1250,
        )
        maquina_42 = Machine(
            numero_interno="42", marca="Hyster", modelo="H2.5FT", tipo="forklift",
            estado="operativa", cliente_id=cliente_b.id, horometro=3400,
        )
        maquina_51 = Machine(numero_interno="51", marca="Yale", modelo="GLP050", tipo="forklift", estado="operativa")
        db.add_all([maquina_33, maquina_42, maquina_51])

        db.commit()
        print("Datos de desarrollo creados: 4 usuarios, 3 clientes, 3 máquinas (2 asociadas a clientes).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
