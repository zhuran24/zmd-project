from __future__ import annotations

from types import SimpleNamespace

from ortools.sat.python import cp_model

from src.models import _cpsat_compat


class _FakeProtoUpper:
    def __init__(self) -> None:
        self.copied = None

    def CopyFrom(self, other) -> None:
        self.copied = other


class _FakeCpModelUpper:
    def __init__(self, *, model_proto=None):
        if model_proto is not None:
            raise TypeError("model_proto keyword is unsupported in this fake old build")
        self.proto = _FakeProtoUpper()


class _FakeProtoLower:
    def __init__(self) -> None:
        self.copied = None

    def copy_from(self, other) -> None:
        self.copied = other


class _FakeCpModelLower:
    def __init__(self, *, model_proto=None):
        if model_proto is not None:
            raise TypeError("model_proto keyword is unsupported in this fake old build")
        self.proto = _FakeProtoLower()



def test_search_branching_name_normalizes_plain_integer_surface() -> None:
    assert _cpsat_compat.search_branching_name(1).endswith("FIXED_SEARCH")
    assert _cpsat_compat.search_branching_name("1").endswith("FIXED_SEARCH")



def test_search_branching_name_preserves_named_enum_surface() -> None:
    assert _cpsat_compat.search_branching_name(cp_model.FIXED_SEARCH).endswith(
        "FIXED_SEARCH"
    )



def test_cp_model_from_proto_falls_back_to_uppercase_copyfrom(monkeypatch) -> None:
    fake_module = SimpleNamespace(CpModel=_FakeCpModelUpper)
    monkeypatch.setattr(_cpsat_compat, "cp_model", fake_module)

    payload = object()
    model = _cpsat_compat.cp_model_from_proto(payload)

    assert isinstance(model, _FakeCpModelUpper)
    assert model.proto.copied is payload



def test_cp_model_from_proto_falls_back_to_lowercase_copy_from(monkeypatch) -> None:
    fake_module = SimpleNamespace(CpModel=_FakeCpModelLower)
    monkeypatch.setattr(_cpsat_compat, "cp_model", fake_module)

    payload = object()
    model = _cpsat_compat.cp_model_from_proto(payload)

    assert isinstance(model, _FakeCpModelLower)
    assert model.proto.copied is payload
