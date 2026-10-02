import json
import subprocess
import sys

import pytest

from scripts import contracts


def test_schema_export_is_deterministic_and_current(tmp_path):
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    contracts.export_schema(first)
    contracts.export_schema(second)
    assert first.read_bytes() == second.read_bytes() == contracts.SCHEMA.read_bytes()
    assert json.loads(first.read_text())["openapi"] == "3.1.0"


def test_export_import_does_not_initialize_db_or_ml():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import scripts.contracts; import sys; "
            "assert 'app.core.database' not in sys.modules; "
            "assert 'catboost' not in sys.modules; "
            "assert 'sentence_transformers' not in sys.modules",
        ],
        check=True,
    )


def test_check_detects_stale_artifact_without_modifying_it(tmp_path, monkeypatch):
    schema, types = tmp_path / "openapi.json", tmp_path / "schema.ts"
    schema.write_bytes(contracts.SCHEMA.read_bytes())
    original_schema = schema.read_bytes()
    types.write_text("outdated")
    monkeypatch.setattr(contracts, "SCHEMA", schema)
    monkeypatch.setattr(contracts, "TYPES", types)
    monkeypatch.setattr(contracts, "ROOT", tmp_path)
    # Only stub the external generator; exercise the real comparison and --check flow.
    monkeypatch.setattr(
        contracts, "generate_types", lambda source, output: output.write_text("new")
    )
    monkeypatch.setattr(sys, "argv", ["contracts", "--check"])
    with pytest.raises(SystemExit, match="Outdated contracts"):
        contracts.main()
    assert types.read_text() == "outdated"
    assert schema.read_bytes() == original_schema
