"""RBAC por proyecto. El servidor comprueba pertenencia y permiso en CADA consulta y acción.

Roles de proyecto:  lead (Responsable) · engineer (Ingeniero/analista) · reviewer (Revisor) · reader (Lector)
Rol global:         is_admin (Administrador) → acceso total y administración del sistema.
"""
import uuid
from enum import Enum

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, ProjectMember, User


class Perm(str, Enum):
    VIEW = "view"
    EDIT_PROJECT = "edit_project"
    MANAGE_MEMBERS = "manage_members"
    DESIGN = "design"              # crear arquitecturas y datasets
    TRAIN = "train"                # iniciar / cancelar / reintentar entrenamientos
    REVIEW_MODEL = "review_model"  # marcar revisado / aprobado
    RETIRE_MODEL = "retire_model"
    DOWNLOAD_MODEL = "download_model"
    EXPORT = "export"
    VIEW_AUDIT = "view_audit"


ROLE_PERMS: dict[str, set[Perm]] = {
    "lead": set(Perm),
    "engineer": {Perm.VIEW, Perm.DESIGN, Perm.TRAIN, Perm.DOWNLOAD_MODEL, Perm.EXPORT},
    "reviewer": {Perm.VIEW, Perm.REVIEW_MODEL, Perm.DOWNLOAD_MODEL, Perm.EXPORT, Perm.VIEW_AUDIT},
    "reader": {Perm.VIEW},
}

ROLE_LABELS = {"lead": "Responsable de proyecto", "engineer": "Ingeniero/analista de IA",
               "reviewer": "Revisor", "reader": "Lector"}


def member_role(db: Session, project_id: uuid.UUID, user: User) -> str | None:
    if user.is_admin:
        return "lead"
    return db.scalar(select(ProjectMember.role).where(ProjectMember.project_id == project_id,
                                                      ProjectMember.user_id == user.id))


def permissions_for(role: str | None) -> set[Perm]:
    return ROLE_PERMS.get(role or "", set())


def authorize(db: Session, project_id: uuid.UUID, user: User, perm: Perm) -> Project:
    """Devuelve el proyecto si el usuario tiene el permiso. 404 si no es miembro (no revela existencia)."""
    project = db.get(Project, project_id)
    role = member_role(db, project_id, user) if project else None
    if project is None or role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")
    if perm not in permissions_for(role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Tu rol ({ROLE_LABELS.get(role, role)}) no permite esta acción")
    return project
