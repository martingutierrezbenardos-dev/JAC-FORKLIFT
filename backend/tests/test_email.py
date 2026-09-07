import pytest

from app.core.errors import ValidationDomainError
from app.core.permissions import UserRole
from app.integrations.email.gmail_provider import GmailEmailProvider
from app.integrations.email.provider import EmailNotConfiguredError
from app.services import email_service
from app.tools.registry import get_tool, tools_available_to_role
from tests.conftest import make_user


class _FakeEmailProvider:
    def __init__(self) -> None:
        self.drafts_created: list[dict] = []
        self.sent: list[str] = []

    def search_emails(self, query, limit=10):
        return [{"id": "m1", "de": "alguien@x.cl", "asunto": "Hola", "fecha": "hoy", "resumen": "..."}]

    def create_draft(self, draft):
        self.drafts_created.append({"to": draft.to, "subject": draft.subject, "body": draft.body})
        return "draft-1"

    def send_draft(self, draft_id):
        self.sent.append(draft_id)


def test_gmail_provider_requiere_configuracion(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "google_service_account_json", None)

    with pytest.raises(EmailNotConfiguredError):
        GmailEmailProvider(impersonate_email="alguien@jacobea.cl")


def test_gerente_marketing_no_tiene_acceso_a_correo():
    tools = {t.name for t in tools_available_to_role(UserRole.GERENTE_MARKETING)}
    assert "preparar_correo" not in tools
    assert "enviar_correo" not in tools


def test_preparar_correo_sin_email_falla(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900555001", email=None)

    with pytest.raises(ValidationDomainError):
        email_service.preparar_correo(
            db_session, actor=tecnico, destinatarios_telefonos=[], destinatarios_email=["x@y.cl"],
            asunto="Asunto", cuerpo="Cuerpo", provider_factory=lambda email: _FakeEmailProvider(),
        )


def test_preparar_correo_resuelve_destinatario_por_telefono(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900555002", email="t@jacobea.cl")
    otro = make_user(
        db_session, rol=UserRole.ADMINISTRACION, telefono="+56900555003", nombre="Otro", email="otro@jacobea.cl"
    )
    fake_provider = _FakeEmailProvider()

    resultado = email_service.preparar_correo(
        db_session, actor=tecnico, destinatarios_telefonos=[otro.telefono_whatsapp], destinatarios_email=[],
        asunto="Informe", cuerpo="Contenido", provider_factory=lambda email: fake_provider,
    )

    assert resultado["draft_id"] == "draft-1"
    assert "otro@jacobea.cl" in resultado["destinatarios"]
    assert fake_provider.drafts_created[0]["subject"] == "Informe"


def test_preparar_correo_destinatario_desconocido_falla(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900555004", email="t2@jacobea.cl")

    with pytest.raises(ValidationDomainError):
        email_service.preparar_correo(
            db_session, actor=tecnico, destinatarios_telefonos=["+56999999999"], destinatarios_email=[],
            asunto="x", cuerpo="y", provider_factory=lambda email: _FakeEmailProvider(),
        )


def test_enviar_correo_envia_el_borrador(db_session):
    tecnico = make_user(db_session, rol=UserRole.TECNICO, telefono="+56900555005", email="t3@jacobea.cl")
    fake_provider = _FakeEmailProvider()

    resultado = email_service.enviar_correo(
        db_session, actor=tecnico, draft_id="draft-1", provider_factory=lambda email: fake_provider
    )

    assert resultado["enviado"] is True
    assert fake_provider.sent == ["draft-1"]


def test_enviar_correo_es_siempre_nivel_2(db_session):
    gerente = make_user(db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56900555006", email="g@jacobea.cl")
    tool = get_tool("enviar_correo")

    from app.schemas.email import EnviarCorreoInput

    assert tool.confirmation_level_for(EnviarCorreoInput(draft_id="d1"), gerente) == 2


def test_buscar_correos(db_session):
    gerente = make_user(db_session, rol=UserRole.GERENTE_GENERAL, telefono="+56900555007", email="g2@jacobea.cl")
    fake_provider = _FakeEmailProvider()

    resultado = email_service.buscar_correos(
        db_session, actor=gerente, query="from:x", provider_factory=lambda email: fake_provider
    )

    assert resultado["cantidad"] == 1
