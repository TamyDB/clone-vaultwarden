"""Mantém a regra de dependência entre camadas descrita em docs/ARQUITETURA.md."""

import ast
from pathlib import Path

import cofre

ROOT = Path(cofre.__file__).parent

ALLOWED_LAYERS = {
    "domain": {"domain"},
    "crypto": {"crypto"},
    "storage": {"storage", "crypto", "domain"},
    "services": {"services", "storage", "domain"},
}
FORBIDDEN_MODULES = {
    "PySide6", "socket", "ssl", "http", "urllib", "ftplib", "smtplib", "asyncio", "logging",
}


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def core_files():
    for layer in ALLOWED_LAYERS:
        for path in (ROOT / layer).glob("*.py"):
            yield layer, path


def test_core_layers_exist():
    assert {layer for layer, _path in core_files()} == set(ALLOWED_LAYERS)


def test_layers_only_depend_on_allowed_layers():
    for layer, path in core_files():
        for module in imported_modules(path):
            parts = module.split(".")
            if parts[0] == "cofre":
                assert parts[1] in ALLOWED_LAYERS[layer], f"{path.name} importa {module}"


def test_core_does_not_import_ui_network_or_logging():
    for _layer, path in core_files():
        roots = {module.split(".")[0] for module in imported_modules(path)}
        assert not roots & FORBIDDEN_MODULES, f"{path.name} importa {roots & FORBIDDEN_MODULES}"
