#!/usr/bin/env python3
"""Explicit pytest plugin for the AB16 collection protocol.

The preflight caller imports this source by its pinned path and passes a
protocol session object directly to :class:`AB16PytestCollectionPlugin`.
Nothing in this module registers itself globally or discovers a session from
the environment, ``conftest.py``, a ``-p`` name, or the current directory.

``module_origins`` is diagnostic telemetry.  It is canonical and useful for
replay comparisons, but it is not a HEAD-membership or import-closure proof.
The separate Gate-A repository-surface check owns that boundary.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from collections.abc import Generator
from typing import Mapping, Protocol, Sequence

import pytest


class AB16CollectionSessionLike(Protocol):
    """Structural surface consumed by the plugin without an ambient import."""

    workflow: str

    def publish_stage(
        self,
        *,
        items: Sequence[Mapping[str, str]],
        module_origins: Sequence[Mapping[str, str]],
        workflow: str,
        markexpr: str,
    ) -> None:
        """Publish the collection-finish record."""

    def publish_terminal(
        self,
        *,
        exitstatus: int,
        module_origins: Sequence[Mapping[str, str]],
    ) -> None:
        """Publish the session-finish record."""


def _absolute(
    path: Path | str | os.PathLike[str],
    *,
    base: Path,
) -> Path:
    candidate = Path(os.fspath(path))
    if not candidate.is_absolute():
        candidate = base / candidate
    return Path(os.path.abspath(candidate))


def _display_origin(path: str, *, repository_root: Path, basetemp_root: Path | None) -> str:
    """Render a diagnostic path without treating it as authority."""

    absolute = _absolute(path, base=repository_root)
    if basetemp_root is not None:
        try:
            relative = absolute.relative_to(basetemp_root)
        except ValueError:
            pass
        else:
            return f"basetemp:{relative.as_posix()}"
    try:
        relative = absolute.relative_to(repository_root)
    except ValueError:
        pass
    else:
        return relative.as_posix()
    return f"outside:{absolute}"


def _module_origins(
    *,
    repository_root: Path,
    basetemp_root: Path | None,
) -> list[dict[str, str]]:
    """Snapshot canonical diagnostic module-origin records."""

    records: set[tuple[str, str, str, str]] = set()
    for module_name, module in tuple(sys.modules.items()):
        if (
            type(module_name) is not str
            or not module_name
            or module is None
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in module_name
            )
        ):
            continue
        try:
            namespace = vars(module)
        except TypeError:
            continue
        raw_file = namespace.get("__file__")
        if type(raw_file) is str and raw_file and not (
            raw_file.startswith("<") and raw_file.endswith(">")
        ):
            lexical = _display_origin(
                raw_file,
                repository_root=repository_root,
                basetemp_root=basetemp_root,
            )
            resolved = _display_origin(
                os.path.realpath(_absolute(raw_file, base=repository_root)),
                repository_root=repository_root,
                basetemp_root=basetemp_root,
            )
            records.add((module_name, "file", lexical, resolved))
        raw_package_path = namespace.get("__path__")
        if raw_package_path is None:
            continue
        try:
            package_paths = tuple(raw_package_path)
        except (TypeError, RuntimeError):
            continue
        for raw_path in package_paths:
            if type(raw_path) is not str or not raw_path:
                continue
            lexical = _display_origin(
                raw_path,
                repository_root=repository_root,
                basetemp_root=basetemp_root,
            )
            resolved = _display_origin(
                os.path.realpath(_absolute(raw_path, base=repository_root)),
                repository_root=repository_root,
                basetemp_root=basetemp_root,
            )
            records.add((module_name, "package_path", lexical, resolved))
    return [
        {
            "kind": kind,
            "module": module,
            "path": path,
            "resolved_path": resolved_path,
        }
        for module, kind, path, resolved_path in sorted(records)
    ]


class AB16PytestCollectionPlugin:
    """One explicit AB16 collection producer bound to one protocol session."""

    def __init__(
        self,
        *,
        session: AB16CollectionSessionLike,
        repository_root: Path | str,
        basetemp_root: Path | str | None,
    ) -> None:
        raw_root = Path(os.fspath(repository_root))
        if not raw_root.is_absolute():
            raise ValueError("AB16 pytest repository root must be absolute")
        root = Path(os.path.abspath(raw_root))
        if basetemp_root is not None and not Path(os.fspath(basetemp_root)).is_absolute():
            raise ValueError("AB16 pytest basetemp root must be absolute")
        self._session = session
        self._repository_root = root
        self._basetemp_root = (
            None
            if basetemp_root is None
            else _absolute(basetemp_root, base=root)
        )

    def _relative_test_path(self, path: Path | str) -> str:
        absolute = _absolute(path, base=self._repository_root)
        try:
            relative = absolute.relative_to(self._repository_root).as_posix()
        except ValueError as exc:
            raise pytest.UsageError(
                f"AB16 pytest collected a path outside the explicit repository root: {absolute}"
            ) from exc
        if not relative.startswith("src/tests/"):
            raise pytest.UsageError(
                f"AB16 pytest collected a non-test path: {relative}"
            )
        return relative

    def _collection_items(self, session: pytest.Session) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for item in session.items:
            path = self._relative_test_path(item.path)
            raw_nodeid = item.nodeid
            if type(raw_nodeid) is not str or not raw_nodeid:
                raise pytest.UsageError("AB16 pytest collected a malformed nodeid")
            _raw_path, separator, suffix = raw_nodeid.partition("::")
            if separator and (
                not suffix
                or any(
                    ord(character) < 32 or ord(character) == 127
                    for character in suffix
                )
            ):
                raise pytest.UsageError("AB16 pytest collected an unsafe nodeid suffix")
            nodeid = path + (f"::{suffix}" if separator else "")
            items.append({"nodeid": nodeid, "path": path})
        items.sort(key=lambda item: (item["nodeid"], item["path"]))
        if len({item["nodeid"] for item in items}) != len(items):
            raise pytest.UsageError("AB16 pytest collection contains duplicate nodeids")
        return items

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_collection_finish(
        self,
        session: pytest.Session,
    ) -> Generator[None, None, None]:
        """Publish after every inner collection-finish hook and wrapper."""

        yield
        markexpr = session.config.option.markexpr
        workflow = session.config.getoption("repository_workflow")
        raw_confcutdir = session.config.getoption("confcutdir")
        raw_basetemp = session.config.getoption("basetemp")
        if (
            type(markexpr) is not str
            or workflow != self._session.workflow
            or session.config.rootpath != self._repository_root
            or session.config.inipath != self._repository_root / "pytest.ini"
            or not isinstance(raw_confcutdir, (str, os.PathLike))
            or _absolute(
                raw_confcutdir,
                base=self._repository_root,
            )
            != self._repository_root / "src/tests"
            or self._basetemp_root is None
            or not isinstance(raw_basetemp, (str, os.PathLike))
            or _absolute(raw_basetemp, base=self._repository_root)
            != self._basetemp_root
            or session.config.pluginmanager.hasplugin("xdist")
            or session.config.pluginmanager.hasplugin("cacheprovider")
            or not session.config.pluginmanager.hasplugin("randomly")
        ):
            raise pytest.UsageError(
                "AB16 pytest configuration differs from the explicit serial full lane"
            )
        self._session.publish_stage(
            items=self._collection_items(session),
            module_origins=_module_origins(
                repository_root=self._repository_root,
                basetemp_root=self._basetemp_root,
            ),
            workflow=workflow,
            markexpr=markexpr,
        )

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_sessionfinish(
        self,
        session: pytest.Session,
        exitstatus: int,
    ) -> Generator[None, None, None]:
        """Publish after every inner terminal hook and wrapper."""

        del session
        yield
        self._session.publish_terminal(
            exitstatus=int(exitstatus),
            module_origins=_module_origins(
                repository_root=self._repository_root,
                basetemp_root=self._basetemp_root,
            ),
        )
