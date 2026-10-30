import pytest

from labgrid.util import imports


@pytest.fixture(autouse=True)
def fresh_imports(monkeypatch):
    monkeypatch.setattr(imports, "_loaded", set())


def test_load_imports_only_once(tmp_path):
    counter = tmp_path / "counter"
    counter.write_text("")
    module = tmp_path / "plugin_once.py"
    module.write_text(f"open({str(counter)!r}, 'a').write('x')\n")

    imports.load_imports([str(module)])
    # same file through a different path spelling
    imports.load_imports([str(tmp_path / "." / "plugin_once.py")])

    assert counter.read_text() == "x"


def test_load_imports_module_name(tmp_path, monkeypatch):
    (tmp_path / "plugin_by_name.py").write_text("VALUE = 42\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    imports.load_imports(["plugin_by_name"])

    import plugin_by_name

    assert plugin_by_name.VALUE == 42
