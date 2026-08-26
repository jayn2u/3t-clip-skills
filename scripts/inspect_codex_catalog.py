import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


FORBIDDEN_PATH_NAMES = {
    ".git",
    ".superpowers",
    "__pycache__",
    "skills",
}


def run_codex(
    bwrap_binary: Path,
    home_target: Path,
    isolated_home: Path,
    isolated_tmp: Path,
    arguments: list[str],
) -> subprocess.CompletedProcess[str]:
    command = [
        str(bwrap_binary),
        "--die-with-parent",
        "--unshare-net",
        "--ro-bind",
        "/",
        "/",
        "--bind",
        str(isolated_home),
        str(home_target),
        "--bind",
        str(isolated_tmp),
        "/tmp",
        "--dev-bind",
        "/dev",
        "/dev",
        "--proc",
        "/proc",
        "/tmp/codex-bin",
        *arguments,
    ]
    return subprocess.run(command, text=True, capture_output=True)


def fail(message: str, detail: str = "") -> int:
    print(message, file=sys.stderr)
    if detail:
        print(detail, file=sys.stderr)
    return 1


def find_yaml_python() -> str | None:
    executables: list[str] = []
    for command in ("python3", "python"):
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            if not directory:
                continue
            candidate = Path(directory) / command
            if candidate.is_file() and os.access(candidate, os.X_OK):
                executables.append(str(candidate))
    executables.append(sys.executable)
    seen: set[str] = set()
    for executable in executables:
        if executable in seen:
            continue
        seen.add(executable)
        result = subprocess.run(
            [executable, "-c", "import yaml"],
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return executable
    return None


def find_quick_validator() -> Path | None:
    for root in (
        Path.home() / ".codex/skills/.system",
        Path.home() / ".agents/skills/.system",
    ):
        candidate = root / "skill-creator/scripts/quick_validate.py"
        if candidate.is_file():
            return candidate
    return None


def validate_installed_skills(skill_paths: list[Path]) -> tuple[bool, str]:
    quick_validator = find_quick_validator()
    interpreter = find_yaml_python()
    if quick_validator is None or interpreter is None:
        return False, "official Codex quick validator is unavailable"
    for skill_path in skill_paths:
        result = subprocess.run(
            [interpreter, str(quick_validator), str(skill_path)],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            return False, result.stdout + result.stderr
    return True, ""


def infer_skill_identifiers_from_packaging_contract(
    plugin_record: dict[str, object], skill_names: set[str]
) -> list[str]:
    plugin_name = str(plugin_record["name"])
    return sorted(f"{plugin_name}:{name}" for name in skill_names)


def main() -> int:
    if len(sys.argv) != 2:
        return fail("Usage: inspect_codex_catalog.py <bundle-root>")
    bundle_root = Path(sys.argv[1]).resolve()
    codex_binary = shutil.which("codex")
    bwrap_binary = shutil.which("bwrap")
    if not codex_binary or not bwrap_binary:
        print("Codex isolated catalog integration unavailable", file=sys.stderr)
        return 2

    marketplace_path = bundle_root / ".agents/plugins/marketplace.json"
    try:
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        entry = marketplace["plugins"][0]
        plugin_name = entry["name"]
    except (OSError, KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        return fail("Unable to read Codex marketplace metadata", str(error))

    home_target = Path.home()
    with tempfile.TemporaryDirectory(prefix="3t-clip-codex-") as temporary_root:
        temporary_path = Path(temporary_root)
        isolated_home = temporary_path / "home"
        isolated_tmp = temporary_path / "tmp"
        isolated_home.mkdir()
        isolated_tmp.mkdir()
        shutil.copy2(codex_binary, isolated_tmp / "codex-bin")

        try:
            added = run_codex(
                Path(bwrap_binary),
                home_target,
                isolated_home,
                isolated_tmp,
                ["plugin", "marketplace", "add", str(bundle_root), "--json"],
            )
        except OSError as error:
            print("Codex isolated catalog integration unavailable", file=sys.stderr)
            return 2
        if added.returncode != 0:
            if "namespace" in added.stderr.lower() or "permission" in added.stderr.lower():
                print("Codex isolated catalog integration unavailable", file=sys.stderr)
                return 2
            return fail("Codex marketplace registration failed", added.stdout + added.stderr)
        try:
            marketplace_name = json.loads(added.stdout)["marketplaceName"]
            plugin_ref = f"{plugin_name}@{marketplace_name}"
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            return fail("Codex marketplace registration did not report its name", str(error))

        installed = run_codex(
            Path(bwrap_binary),
            home_target,
            isolated_home,
            isolated_tmp,
            ["plugin", "add", plugin_ref, "--json"],
        )
        if installed.returncode != 0:
            return fail("Codex plugin installation failed", installed.stdout + installed.stderr)
        try:
            install_record = json.loads(installed.stdout)
            install_path = install_record["installedPath"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            return fail("Codex installation did not report an installed path", str(error))

        listed = run_codex(
            Path(bwrap_binary),
            home_target,
            isolated_home,
            isolated_tmp,
            ["plugin", "list", "--json"],
        )
        if listed.returncode != 0:
            return fail("Codex plugin catalog inspection failed", listed.stdout + listed.stderr)
        try:
            catalog = json.loads(listed.stdout)
            records = [
                item
                for item in catalog["installed"]
                if item.get("pluginId") == plugin_ref
            ]
            record = records[0]
            record["installedPath"] = install_path
            installed_path = Path(install_path)
            relative_path = installed_path.relative_to(home_target)
            installed_root = isolated_home / relative_path
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            return fail("Codex catalog did not register the expected plugin", str(error))

        if not installed_root.is_dir():
            return fail("Codex installed plugin payload is missing", str(installed_root))
        skill_dirs = {
            path.name
            for path in installed_root.iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
        expected_skill_dirs = {
            path.name
            for path in (bundle_root / "skills").iterdir()
            if path.is_dir() and not path.name.startswith(".") and (path / "SKILL.md").is_file()
        }
        forbidden_paths = sorted(
            str(path.relative_to(installed_root))
            for path in installed_root.rglob("*")
            if path.name in FORBIDDEN_PATH_NAMES
        )
        if skill_dirs != expected_skill_dirs:
            return fail(
                "Codex installed skill payload does not match the canonical skills",
                json.dumps({"expected": sorted(expected_skill_dirs), "actual": sorted(skill_dirs)}),
            )
        skill_paths = [installed_root / name for name in sorted(skill_dirs)]
        validated, validation_error = validate_installed_skills(skill_paths)
        if not validated:
            return fail("Installed Codex skills failed official validation", validation_error)
        if forbidden_paths:
            return fail("Codex installed payload contains forbidden paths", json.dumps(forbidden_paths))
        identifiers = infer_skill_identifiers_from_packaging_contract(record, skill_dirs)
        print(
            json.dumps(
                {
                    "pluginId": record["pluginId"],
                    "codexCatalog": {"installed": [record]},
                    "installedSkills": sorted(skill_dirs),
                    "identifierInference": {
                        "identifiers": identifiers,
                        "notReturnedByCodex": True,
                        "source": "packaging-contract-inference",
                    },
                    "forbiddenPaths": forbidden_paths,
                    "installedPath": record["installedPath"],
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
