"""POST /perfil/contrasena: el usuario cambia la suya y el administrador queda avisado.

Se monta sólo el router de perfil, con las dependencias sustituidas, para no necesitar Supabase ni
configuración real. Lo que se verifica es la lógica de las ramas: confirmar la contraseña actual,
rechazar la repetida y dejar siempre el renglón en `eventos_cuenta`.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import UsuarioActual, usuario_actual
from app.config import obtener_configuracion
from app.db.cliente import obtener_cliente
from app.routers import perfil

USUARIO = UsuarioActual(id=uuid4(), nombre="Vendedora de prueba", rol="vendedor", email="prueba@minimal40.local")
ACTUAL = "contrasena-vieja"


class TablaFalsa:
    """Acumula los insert de `eventos_cuenta` en una lista compartida."""

    def __init__(self, registro: list[dict[str, Any]]) -> None:
        self._registro = registro
        self._fila: dict[str, Any] = {}

    def insert(self, fila: dict[str, Any]) -> "TablaFalsa":
        self._fila = fila
        return self

    async def execute(self) -> None:
        self._registro.append(self._fila)


class AdminFalso:
    def __init__(self, cambios: list[tuple[str, dict[str, Any]]]) -> None:
        self._cambios = cambios

    async def update_user_by_id(self, usuario_id: str, datos: dict[str, Any]) -> None:
        self._cambios.append((usuario_id, datos))


class DbFalsa:
    def __init__(self) -> None:
        self.eventos: list[dict[str, Any]] = []
        self.cambios: list[tuple[str, dict[str, Any]]] = []
        self.auth = type("Auth", (), {"admin": AdminFalso(self.cambios)})()

    def table(self, nombre: str) -> TablaFalsa:
        assert nombre == "eventos_cuenta"
        return TablaFalsa(self.eventos)


class ConfigFalsa:
    supabase_url = "https://proyecto.supabase.co"
    supabase_service_role_key = "llave-de-prueba"


@pytest.fixture
def cliente(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, DbFalsa]:
    db = DbFalsa()
    app = FastAPI()
    app.include_router(perfil.router)
    app.dependency_overrides[usuario_actual] = lambda: USUARIO
    app.dependency_overrides[obtener_cliente] = lambda: db
    app.dependency_overrides[obtener_configuracion] = ConfigFalsa

    async def verificar(_config: Any, correo: str, contrasena: str) -> bool:
        assert correo == USUARIO.email
        return contrasena == ACTUAL

    monkeypatch.setattr(perfil, "_contrasena_es_correcta", verificar)
    return TestClient(app), db


def test_cambio_correcto_actualiza_y_avisa(cliente: tuple[TestClient, DbFalsa]) -> None:
    api, db = cliente
    respuesta = api.post("/perfil/contrasena", json={"contrasena_actual": ACTUAL, "contrasena_nueva": "contrasena-nueva"})

    assert respuesta.status_code == 204
    assert db.cambios == [(str(USUARIO.id), {"password": "contrasena-nueva"})]
    assert [evento["tipo"] for evento in db.eventos] == ["cambio_contrasena"]
    assert db.eventos[0]["usuario_id"] == str(USUARIO.id)


def test_contrasena_actual_equivocada_no_cambia_nada_pero_deja_aviso(cliente: tuple[TestClient, DbFalsa]) -> None:
    api, db = cliente
    respuesta = api.post("/perfil/contrasena", json={"contrasena_actual": "no-es-esa", "contrasena_nueva": "contrasena-nueva"})

    assert respuesta.status_code == 401
    assert db.cambios == []
    assert [evento["tipo"] for evento in db.eventos] == ["intento_fallido"]


def test_la_nueva_no_puede_ser_la_misma(cliente: tuple[TestClient, DbFalsa]) -> None:
    api, db = cliente
    respuesta = api.post("/perfil/contrasena", json={"contrasena_actual": ACTUAL, "contrasena_nueva": ACTUAL})

    assert respuesta.status_code == 422
    assert db.cambios == []
    assert db.eventos == []


def test_contrasena_nueva_corta_la_rechaza_el_modelo(cliente: tuple[TestClient, DbFalsa]) -> None:
    api, db = cliente
    respuesta = api.post("/perfil/contrasena", json={"contrasena_actual": ACTUAL, "contrasena_nueva": "corta"})

    assert respuesta.status_code == 422
    assert db.cambios == []


def test_un_evento_que_no_se_puede_guardar_no_tumba_el_cambio(cliente: tuple[TestClient, DbFalsa]) -> None:
    """Si el aviso al administrador falla, la persona igual se queda con su contraseña nueva."""
    api, db = cliente

    def table_que_falla(_nombre: str) -> Any:
        raise RuntimeError("tabla caída")

    db.table = table_que_falla  # type: ignore[method-assign]
    respuesta = api.post("/perfil/contrasena", json={"contrasena_actual": ACTUAL, "contrasena_nueva": "contrasena-nueva"})

    assert respuesta.status_code == 204
    assert db.cambios == [(str(USUARIO.id), {"password": "contrasena-nueva"})]
