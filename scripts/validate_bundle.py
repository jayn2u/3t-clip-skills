import json
import re
import sys
from pathlib import Path


EXPECTED_SKILLS = {
    "paper-citation-lookup",
    "prior-research-brief",
    "t2i-rank1-diagnosis",
}
ALLOWED_FRONTMATTER = {"name", "description", "license", "allowed-tools", "metadata"}
FORBIDDEN_PACKAGE_NAMES = {
    ".git",
    ".superpowers",
    "__pycache__",
    "tests",
    "docs",
    ".agents",
    ".claude",
    ".codex",
    "artifacts",
    "results",
    "wandb",
}
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SUPPORT_REFERENCE_RE = re.compile(r"`((?:scripts|references|evals)/[^`\s]+)`")


def within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def parse_frontmatter(path: Path) -> tuple[dict[str, str] | None, list[str]]:
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return None, [f"{path}: cannot read SKILL.md: {error}"]
    if not lines or lines[0].strip() != "---":
        return None, [f"{path}: frontmatter must start with ---"]
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields, errors
        key, separator, value = line.partition(":")
        if not separator or not key.strip():
            errors.append(f"{path}: malformed frontmatter line: {line}")
            continue
        fields[key.strip()] = value.strip()
    errors.append(f"{path}: frontmatter is not terminated")
    return None, errors


def load_json(path: Path, label: str, errors: list[str]):
    if not path.is_file() or path.is_symlink():
        errors.append(f"{label}: required JSON file is missing")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{label}: invalid JSON: {error}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: JSON root must be an object")
        return None
    return value


def validate_frontmatter(skill_root: Path, errors: list[str]) -> str | None:
    path = skill_root / "SKILL.md"
    fields, parse_errors = parse_frontmatter(path)
    errors.extend(parse_errors)
    if fields is None:
        return None
    unexpected = set(fields) - ALLOWED_FRONTMATTER
    if unexpected:
        errors.append(f"{path}: unsupported frontmatter keys: {sorted(unexpected)}")
    name = fields.get("name", "")
    description = fields.get("description", "")
    if not name:
        errors.append(f"{path}: frontmatter name is required")
    elif not SKILL_NAME_RE.fullmatch(name):
        errors.append(f"{path}: frontmatter name is not hyphen-case: {name}")
    if not description:
        errors.append(f"{path}: frontmatter description is required")
    if "<" in description or ">" in description:
        errors.append(f"{path}: frontmatter description cannot contain angle brackets")
    return name


def validate_support_references(skill_root: Path, errors: list[str]) -> None:
    content = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    for relative in SUPPORT_REFERENCE_RE.findall(content):
        candidate = (skill_root / relative).resolve()
        if not within(candidate, skill_root.resolve()) or not candidate.is_file():
            errors.append(f"{skill_root}: support reference is missing: {relative}")


def validate_evals(skill_root: Path, errors: list[str]) -> None:
    evals_path = skill_root / "evals/evals.json"
    payload = load_json(evals_path, str(evals_path), errors)
    if payload is None:
        return
    if payload.get("skill_name") != skill_root.name:
        errors.append(f"{evals_path}: skill_name must be {skill_root.name}")
    cases = payload.get("evals")
    if not isinstance(cases, list):
        errors.append(f"{evals_path}: evals must be an array")
        return
    evals_root = evals_path.parent.resolve()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"{evals_path}: eval {index} must be an object")
            continue
        files = case.get("files", [])
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            errors.append(f"{evals_path}: eval {index} files must be an array of strings")
            continue
        for relative in files:
            candidate = (evals_root / relative).resolve()
            if not within(candidate, evals_root) or not candidate.is_file():
                errors.append(f"{evals_path}: missing eval resource: {relative}")


def validate_skill_payload(root: Path, errors: list[str]) -> None:
    skills_root = root / "skills"
    if not skills_root.is_dir() or skills_root.is_symlink():
        errors.append(f"{skills_root}: canonical skills directory is missing")
        return
    hidden = {
        entry.name
        for entry in skills_root.iterdir()
        if entry.is_dir() and entry.name.startswith(".")
    }
    if hidden - {".codex-plugin"}:
        errors.append(f"{skills_root}: unexpected hidden directories: {sorted(hidden - {'.codex-plugin'})}")
    actual = {
        entry.name
        for entry in skills_root.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    }
    if actual != EXPECTED_SKILLS:
        errors.append(f"{skills_root}: expected exactly {sorted(EXPECTED_SKILLS)}, got {sorted(actual)}")
    for name in sorted(EXPECTED_SKILLS):
        skill_root = skills_root / name
        if not skill_root.is_dir() or skill_root.is_symlink():
            errors.append(f"{skill_root}: skill directory is missing or symlinked")
            continue
        frontmatter_name = validate_frontmatter(skill_root, errors)
        if frontmatter_name != name:
            errors.append(f"{skill_root}/SKILL.md: frontmatter name must match directory {name}")
        validate_support_references(skill_root, errors)
        validate_evals(skill_root, errors)


def validate_plugin_manifest(
    path: Path, expected_name: str, expected_skills: str | None, errors: list[str]
) -> None:
    payload = load_json(path, str(path), errors)
    if payload is None:
        return
    if payload.get("name") != expected_name:
        errors.append(f"{path}: name must be {expected_name}")
    if expected_skills is not None and payload.get("skills") != expected_skills:
        errors.append(f"{path}: skills must be {expected_skills}")


def validate_marketplaces(root: Path, errors: list[str]) -> None:
    claude_path = root / ".claude-plugin/marketplace.json"
    claude = load_json(claude_path, str(claude_path), errors)
    if claude is not None:
        plugins = claude.get("plugins")
        if not isinstance(plugins, list) or len(plugins) != 1:
            errors.append(f"{claude_path}: exactly one plugin is required")
        elif plugins[0].get("source") != "./":
            errors.append(f"{claude_path}: plugin source must be ./")
    codex_path = root / ".agents/plugins/marketplace.json"
    codex = load_json(codex_path, str(codex_path), errors)
    if codex is not None:
        plugins = codex.get("plugins")
        if not isinstance(plugins, list) or len(plugins) != 1:
            errors.append(f"{codex_path}: exactly one plugin is required")
        else:
            entry = plugins[0]
            source = entry.get("source")
            if entry.get("name") != "3t-clip":
                errors.append(f"{codex_path}: plugin name must be 3t-clip")
            if not isinstance(source, dict) or source.get("source") != "local":
                errors.append(f"{codex_path}: plugin source must be a local source")
            elif source.get("path") != "./skills":
                errors.append(f"{codex_path}: plugin source path must be ./skills")


def validate_versions(root: Path, errors: list[str]) -> None:
    paths = [
        root / ".claude-plugin/plugin.json",
        root / ".codex-plugin/plugin.json",
        root / "skills/.codex-plugin/plugin.json",
        root / ".claude-plugin/marketplace.json",
    ]
    versions: list[tuple[Path, str]] = []
    for path in paths:
        payload = load_json(path, str(path), errors)
        if payload is None:
            continue
        version = payload.get("version")
        if isinstance(version, str) and version:
            versions.append((path, version))
    unique_versions = {version for _, version in versions}
    if len(unique_versions) > 1:
        errors.append(
            "manifest versions must match: "
            + ", ".join(f"{path}={version}" for path, version in versions)
        )


def validate_adapter(root: Path, errors: list[str]) -> None:
    adapter = root / "skills"
    if not adapter.is_dir() or adapter.is_symlink():
        errors.append(f"{adapter}: Codex release adapter is missing")
        return
    validate_plugin_manifest(
        adapter / ".codex-plugin/plugin.json", "3t-clip", "./skills/", errors
    )
    for path in adapter.rglob("*"):
        if path.name in FORBIDDEN_PACKAGE_NAMES:
            errors.append(f"{adapter}: forbidden package path: {path.relative_to(adapter)}")
    if (root / "codex-plugin").exists():
        errors.append(f"{root}: duplicate Codex adapter directory is not allowed")


def validate_bundle(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    validate_plugin_manifest(root / ".claude-plugin/plugin.json", "3t-clip", "./skills/", errors)
    validate_plugin_manifest(root / ".codex-plugin/plugin.json", "3t-clip", "./skills/", errors)
    validate_marketplaces(root, errors)
    validate_versions(root, errors)
    validate_skill_payload(root, errors)
    validate_adapter(root, errors)
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_bundle.py <bundle-root>", file=sys.stderr)
        return 2
    root = Path(sys.argv[1])
    errors = validate_bundle(root)
    if errors:
        print("Bundle validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Bundle validation passed: {root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
