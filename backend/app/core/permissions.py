"""Enum de roles y permisos, y la matriz rol -> permisos.

Esta matriz es la ÚNICA fuente de verdad de autorización. Tanto los endpoints REST como las
tools de IA dependen de ``has_permission`` / ``require_permission``. Ver docs/security.md.
"""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    GERENTE_GENERAL = "gerente_general"
    GERENTE_SUCURSAL = "gerente_sucursal"
    GERENTE_MARKETING = "gerente_marketing"
    RESPONSABLE_MERCADO_PUBLICO = "responsable_mercado_publico"
    JEFE_SERVICIOS_TECNICOS = "jefe_servicios_tecnicos"
    VENDEDOR = "vendedor"
    TECNICO = "tecnico"
    ADMINISTRACION = "administracion"
    ADMIN_SISTEMA = "admin_sistema"


class Permission(str, Enum):
    EXPENSES_CREATE_OWN = "expenses:create_own"
    EXPENSES_READ_OWN = "expenses:read_own"
    EXPENSES_READ_ALL = "expenses:read_all"
    EXPENSES_UPDATE_OWN = "expenses:update_own"
    EXPENSES_UPDATE_ALL = "expenses:update_all"
    EXPENSES_APPROVE_REIMBURSEMENT = "expenses:approve_reimbursement"

    TASKS_CREATE_OWN = "tasks:create_own"
    TASKS_ASSIGN_OTHERS = "tasks:assign_others"
    TASKS_READ_OWN = "tasks:read_own"
    TASKS_READ_ALL = "tasks:read_all"
    TASKS_COMPLETE_OWN = "tasks:complete_own"
    TASKS_COMPLETE_ALL = "tasks:complete_all"

    USERS_READ_ALL = "users:read_all"
    USERS_MANAGE = "users:manage"

    REPORTS_VIEW_OWN = "reports:view_own"
    REPORTS_VIEW_ALL = "reports:view_all"

    SERVICES_CREATE_OWN = "services:create_own"
    SERVICES_READ_OWN = "services:read_own"
    SERVICES_READ_ALL = "services:read_all"
    SERVICES_UPDATE_OWN = "services:update_own"
    SERVICES_UPDATE_ALL = "services:update_all"
    SERVICES_ASSIGN = "services:assign"
    SERVICES_CLOSE = "services:close"

    CUSTOMERS_READ = "customers:read"
    MACHINES_READ = "machines:read"

    MAINTENANCE_CREATE = "maintenance:create"
    MAINTENANCE_READ = "maintenance:read"

    CALENDAR_USE = "calendar:use"
    EMAIL_USE = "email:use"

    VEHICLES_READ = "vehicles:read"

    CRANES_REGISTER = "cranes:register"
    CRANES_READ = "cranes:read"
    CRANES_MANAGE = "cranes:manage"


_BASE_FIELD_PERMISSIONS: set[Permission] = {
    Permission.EXPENSES_CREATE_OWN,
    Permission.EXPENSES_READ_OWN,
    Permission.EXPENSES_UPDATE_OWN,
    Permission.TASKS_CREATE_OWN,
    Permission.TASKS_READ_OWN,
    Permission.TASKS_COMPLETE_OWN,
    Permission.REPORTS_VIEW_OWN,
    Permission.SERVICES_CREATE_OWN,
    Permission.SERVICES_READ_OWN,
    Permission.SERVICES_UPDATE_OWN,
    Permission.CUSTOMERS_READ,
    Permission.MACHINES_READ,
    Permission.MAINTENANCE_CREATE,
    Permission.MAINTENANCE_READ,
    Permission.CALENDAR_USE,
    Permission.EMAIL_USE,
    Permission.VEHICLES_READ,
    Permission.CRANES_REGISTER,
    Permission.CRANES_READ,
}

_BACK_OFFICE_PERMISSIONS: set[Permission] = _BASE_FIELD_PERMISSIONS | {
    Permission.EXPENSES_READ_ALL,
    Permission.EXPENSES_UPDATE_ALL,
    Permission.EXPENSES_APPROVE_REIMBURSEMENT,
    Permission.TASKS_READ_ALL,
    Permission.TASKS_ASSIGN_OTHERS,
    Permission.TASKS_COMPLETE_ALL,
    Permission.USERS_READ_ALL,
    Permission.REPORTS_VIEW_ALL,
    Permission.SERVICES_READ_ALL,
    Permission.SERVICES_UPDATE_ALL,
    Permission.CRANES_MANAGE,
}

_ALL_PERMISSIONS: set[Permission] = set(Permission)

ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.TECNICO: set(_BASE_FIELD_PERMISSIONS),
    UserRole.VENDEDOR: set(_BASE_FIELD_PERMISSIONS),
    UserRole.RESPONSABLE_MERCADO_PUBLICO: set(_BASE_FIELD_PERMISSIONS),
    UserRole.GERENTE_MARKETING: {
        Permission.TASKS_CREATE_OWN,
        Permission.TASKS_READ_OWN,
        Permission.TASKS_COMPLETE_OWN,
        Permission.REPORTS_VIEW_OWN,
    },
    UserRole.ADMINISTRACION: set(_BACK_OFFICE_PERMISSIONS),
    UserRole.JEFE_SERVICIOS_TECNICOS: (
        set(_BACK_OFFICE_PERMISSIONS)
        - {Permission.EXPENSES_APPROVE_REIMBURSEMENT, Permission.USERS_READ_ALL}
        | {Permission.SERVICES_ASSIGN, Permission.SERVICES_CLOSE}
    ),
    UserRole.GERENTE_SUCURSAL: set(_BACK_OFFICE_PERMISSIONS),
    UserRole.GERENTE_GENERAL: set(_ALL_PERMISSIONS) - {Permission.USERS_MANAGE},
    UserRole.ADMIN_SISTEMA: set(_ALL_PERMISSIONS),
}


def get_permissions_for_role(role: UserRole) -> set[Permission]:
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: UserRole, permission: Permission) -> bool:
    return permission in get_permissions_for_role(role)
