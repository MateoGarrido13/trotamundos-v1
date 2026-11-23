# SPEC: SPEC-REF-04
# ELEMENTO PASO 5: Módulo de control de acceso y auditoría (ITERACION_4)
# ADRs: ADR-IT4-007
# DRIVERS: QA-SEG-02
"""T-REF-04-02: la matriz de roles y permisos de la spec, celda por celda."""
import pytest

from trotamundos.orquestador.control_acceso import (
    Decision,
    ModuloControlAcceso,
    Permiso,
    Rol,
    alcanza,
    decidir,
)
from trotamundos.persistencia.base_viajes import BaseViajes
from trotamundos.persistencia.repositorio_gestion import RepositorioGestion

C, D, P = Decision.CONCEDIDO, Decision.DENEGADO, Decision.SOLO_PROPIAS


@pytest.mark.parametrize("rol,permiso,esperada", [
    (Rol.ORGANIZADOR, Permiso.VER, C),
    (Rol.ORGANIZADOR, Permiso.REGISTRAR, C),
    (Rol.ORGANIZADOR, Permiso.MODIFICAR, C),
    (Rol.ORGANIZADOR, Permiso.ADMINISTRAR_MIEMBROS, C),
    (Rol.PARTICIPANTE, Permiso.VER, C),
    (Rol.PARTICIPANTE, Permiso.REGISTRAR, C),
    (Rol.PARTICIPANTE, Permiso.MODIFICAR, P),
    (Rol.PARTICIPANTE, Permiso.ADMINISTRAR_MIEMBROS, D),
])
def test_matriz_de_roles_y_permisos_de_la_spec(rol, permiso, esperada):
    assert decidir(rol, permiso) is esperada


@pytest.mark.parametrize("permiso", list(Permiso))
def test_AC_REF_04_05_sin_membresia_no_hay_ningun_permiso(permiso):
    assert decidir(None, permiso) is D  # denegación por defecto


def test_AC_REF_04_07_participante_alcanza_solo_lo_que_creo():
    assert alcanza(P, creado_por="luis", cuenta="luis")


def test_AC_REF_04_08_participante_no_alcanza_lo_ajeno_ni_lo_de_proveedor_o_correo():
    assert not alcanza(P, creado_por="ana", cuenta="luis")
    assert not alcanza(P, creado_por=None, cuenta="luis")  # vino de un proveedor o del correo


def test_AC_REF_04_09_organizador_alcanza_cualquier_reserva():
    for creado_por in ("ana", "luis", None):
        assert alcanza(C, creado_por=creado_por, cuenta="ana")


def test_denegado_nunca_alcanza():
    assert not alcanza(D, creado_por="luis", cuenta="luis")


@pytest.mark.db
def test_verificar_permiso_lee_la_membresia_de_la_base(bases_limpias):
    base = BaseViajes.desde_config(bases_limpias)
    base.escribir(lambda c: RepositorioGestion.agregar_membresia(c, "it1", "ana", "organizador"))
    base.escribir(lambda c: RepositorioGestion.agregar_membresia(c, "it1", "luis", "participante"))
    modulo = ModuloControlAcceso()

    def decision(cuenta, itinerario, permiso):
        return base.leer(lambda c: modulo.verificar_permiso(c, cuenta, itinerario, permiso))

    assert decision("ana", "it1", Permiso.MODIFICAR) is C
    assert decision("luis", "it1", Permiso.MODIFICAR) is P
    assert decision("luis", "it1", Permiso.ADMINISTRAR_MIEMBROS) is D
    assert decision("intruso", "it1", Permiso.VER) is D  # sin membresía
    assert decision("ana", "otro-itinerario", Permiso.VER) is D  # la membresía es por itinerario
