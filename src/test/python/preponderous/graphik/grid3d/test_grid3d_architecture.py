"""grid3d's layers, kept by CI: the model and core (and the ports) never
import an adapter or a composition root, and each port and adapter file
holds one class."""

import ast
import os

import pytest

import preponderous.graphik.grid3d as grid3d

ROOT = os.path.dirname(grid3d.__file__)
PACKAGE = "preponderous.graphik.grid3d"
INNER = ["animate", "board", "errors", "events", "geometry", "pick", "scene", "state", "text",
         "touchkeys", "ui", "wire"]
OUTER = {"adapters", "view", "web", "relay"}


def innerFiles():
    files = [os.path.join(ROOT, name + ".py") for name in INNER]
    ports = os.path.join(ROOT, "ports")
    files += [os.path.join(ports, name) for name in sorted(os.listdir(ports)) if name.endswith(".py")]
    return files


def importedTop(path):
    """The first grid3d-relative part of every module `path` imports."""
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    inPorts = os.path.basename(os.path.dirname(path)) == "ports"
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parts = (node.module or "").split(".")
                # `from .x` in ports/ is ports.x; `from ..x` is grid3d's x
                levelsUp = node.level - (1 if inPorts else 0)
                if levelsUp <= 0:
                    found.add("ports")
                    continue
                found.add(parts[0] if parts[0] else [a.name for a in node.names][0])
            elif node.module and node.module.startswith(PACKAGE + "."):
                found.add(node.module[len(PACKAGE) + 1:].split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PACKAGE + "."):
                    found.add(alias.name[len(PACKAGE) + 1:].split(".")[0])
    return found


@pytest.mark.parametrize("path", innerFiles(), ids=lambda p: os.path.relpath(p, ROOT))
def test_inner_layers_never_import_adapters_or_composition_roots(path):
    assert importedTop(path) & OUTER == set()


def oneClassFiles():
    for folder in ("ports", "adapters"):
        for name in sorted(os.listdir(os.path.join(ROOT, folder))):
            if name.endswith(".py") and name != "__init__.py":
                yield os.path.join(ROOT, folder, name)


@pytest.mark.parametrize("path", list(oneClassFiles()), ids=lambda p: os.path.relpath(p, ROOT))
def test_each_port_and_adapter_file_holds_one_class(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    assert len(classes) == 1, classes


def test_the_walk_sees_a_violation(tmp_path):
    (tmp_path / "ports").mkdir()
    port = tmp_path / "ports" / "bad.py"
    port.write_text("from ..adapters import StrataEngine\nfrom .surface import Surface\n")
    assert importedTop(str(port)) == {"adapters", "ports"}
    core = tmp_path / "state.py"
    core.write_text("from .view import Grid3DView\nfrom preponderous.graphik.grid3d.web import PAGE\n")
    assert importedTop(str(core)) == {"view", "web"}
