"""Export FastAPI OpenAPI and generate frontend types without starting the app."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts" / "openapi.json"
TYPES = ROOT / "frontend" / "src" / "contracts" / "schema.ts"


def export_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def generate_types(schema: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["bun", "run", "openapi-typescript", str(schema), "-o", str(output)],
        cwd=ROOT / "frontend",
        check=True,
    )
    subprocess.run(
        ["bun", "run", "prettier", str(output), "--write", "--config", ".prettierrc"],
        cwd=ROOT / "frontend",
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check artifacts without changing them"
    )
    args = parser.parse_args()
    if not args.check:
        export_schema(SCHEMA)
        generate_types(SCHEMA, TYPES)
        return

    with tempfile.TemporaryDirectory(prefix="rlthack-contracts-") as directory:
        temporary = Path(directory)
        schema, types = temporary / "openapi.json", temporary / "schema.ts"
        export_schema(schema)
        generate_types(schema, types)
        stale = [
            str(target.relative_to(ROOT))
            for generated, target in ((schema, SCHEMA), (types, TYPES))
            if not target.exists() or generated.read_bytes() != target.read_bytes()
        ]
        if stale:
            raise SystemExit("Outdated contracts: " + ", ".join(stale) + ". Run task gen.")
    print("API contracts are up to date.")


if __name__ == "__main__":
    main()
