import json
import contextlib
import importlib.util
import io
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
CODEX_ADAPTER = SKILLS
VALIDATOR = ROOT / "scripts/validate_bundle.py"
QUICK_VALIDATE = Path("/home/jwchoi/.codex/skills/.system/skill-creator/scripts/quick_validate.py")
PLUGIN_VALIDATE = Path("/home/jwchoi/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py")
EXPECTED_SKILLS = {
    "paper-citation-lookup",
    "prior-research-brief",
    "t2i-rank1-diagnosis",
}


def load_resolver():
    spec = importlib.util.spec_from_file_location(
        "resolve_paper", SKILLS / "paper-citation-lookup/scripts/resolve_paper.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"missing frontmatter: {path}")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    raise ValueError(f"unterminated frontmatter: {path}")


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def test_plugin_manifests_name_the_same_bundle(self):
        claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        codex = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(claude["name"], "3t-clip")
        self.assertEqual(codex["name"], "3t-clip")

    def test_marketplaces_resolve_local_bundle(self):
        claude = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        codex = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual(claude["plugins"][0]["source"], "./")
        self.assertEqual(codex["plugins"][0]["source"]["path"], "./skills")

    def test_codex_marketplace_source_resolves_root_payload(self):
        marketplace = json.loads(
            (ROOT / ".agents/plugins/marketplace.json").read_text()
        )
        entry = marketplace["plugins"][0]
        source_root = (ROOT / entry["source"]["path"]).resolve()
        self.assertEqual(entry["name"], "3t-clip")
        self.assertEqual(entry["source"]["source"], "local")
        self.assertEqual(source_root, CODEX_ADAPTER)
        self.assertTrue((source_root / ".codex-plugin/plugin.json").is_file())
        for name in EXPECTED_SKILLS:
            self.assertTrue((source_root / name / "SKILL.md").is_file(), name)
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Developer Tools")

    def test_codex_adapter_uses_only_canonical_skill_payload(self):
        self.assertTrue((CODEX_ADAPTER / ".codex-plugin/plugin.json").is_file())
        self.assertFalse((ROOT / "codex-plugin").exists())
        forbidden = {".git", ".superpowers", "__pycache__", "tests", "docs"}
        for path in CODEX_ADAPTER.rglob("*"):
            self.assertNotIn(path.name, forbidden, path)

    def test_codex_catalog_uses_namespaced_skill_identifiers(self):
        marketplace = json.loads(
            (ROOT / ".agents/plugins/marketplace.json").read_text()
        )
        manifest = json.loads((CODEX_ADAPTER / ".codex-plugin/plugin.json").read_text())
        readme = (ROOT / "README.md").read_text()
        self.assertEqual(marketplace["plugins"][0]["name"], "3t-clip")
        self.assertEqual(manifest["name"], "3t-clip")
        for name in EXPECTED_SKILLS:
            self.assertIn(f"$3t-clip:{name}", readme)

    def test_official_codex_validator_accepts_clean_adapter(self):
        result = subprocess.run(
            ["/usr/bin/python3", str(PLUGIN_VALIDATE), str(CODEX_ADAPTER)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bundle_contains_exactly_expected_skills(self):
        actual = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
        self.assertEqual(actual, EXPECTED_SKILLS)

    def test_skill_names_match_directories_and_are_invocable(self):
        for name in EXPECTED_SKILLS:
            path = SKILLS / name / "SKILL.md"
            self.assertTrue(path.is_file(), name)
            frontmatter = load_frontmatter(path)
            self.assertEqual(frontmatter["name"], name)
            self.assertTrue(frontmatter["description"])
            self.assertNotEqual(frontmatter.get("user-invocable"), "false")
            self.assertNotEqual(
                frontmatter.get("disable-model-invocation"), "true"
            )

    def test_resolver_script_preserves_non_executable_source_mode(self):
        mode = (SKILLS / "paper-citation-lookup/scripts/resolve_paper.py").stat().st_mode
        self.assertEqual(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH), 0)

    def test_official_quick_validate_accepts_every_skill(self):
        self.assertTrue(QUICK_VALIDATE.is_file())
        for name in EXPECTED_SKILLS:
            result = subprocess.run(
                ["/usr/bin/python3", str(QUICK_VALIDATE), str(SKILLS / name)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_eval_file_references_exist(self):
        for name in EXPECTED_SKILLS:
            eval_dir = SKILLS / name / "evals"
            payload = json.loads((eval_dir / "evals.json").read_text())
            for case in payload["evals"]:
                for relative in case.get("files", []):
                    self.assertTrue(
                        (eval_dir / relative).is_file(), f"{name}: {relative}"
                    )

    def test_eval_file_references_are_tracked(self):
        for name in EXPECTED_SKILLS:
            eval_dir = SKILLS / name / "evals"
            payload = json.loads((eval_dir / "evals.json").read_text())
            for case in payload["evals"]:
                for relative in case.get("files", []):
                    path = eval_dir / relative
                    tracked_path = path.relative_to(ROOT)
                    result = subprocess.run(
                        ["git", "ls-files", "--error-unmatch", str(tracked_path)],
                        cwd=ROOT,
                        text=True,
                        capture_output=True,
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        f"{name}: {relative} is not tracked",
                    )

    def test_readme_documents_every_install_and_invocation(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("npx skills@latest add jayn2u/3t-clip-skills --all", readme)
        for name in EXPECTED_SKILLS:
            self.assertIn(f"/3t-clip:{name}", readme)
            self.assertIn(f"$3t-clip:{name}", readme)
        self.assertIn("lab_clip", readme)

    def test_t2i_skill_declares_read_only_compatibility_preflight(self):
        content = (SKILLS / "t2i-rank1-diagnosis/SKILL.md").read_text()
        lowered = content.lower()
        for term in (
            "read-only",
            "compatible lab_clip checkout",
            "agents.md",
            "context.md",
            "docs/",
            "configs/",
            "src/",
            "artifacts/",
            "wandb_meta.json",
            "must not modify",
            "refuse",
        ):
            self.assertIn(term, lowered, term)

    def test_validator_accepts_the_bundle(self):
        result = subprocess.run(
            ["uv", "run", "python", str(VALIDATOR), str(ROOT)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validator_rejects_malformed_manifest_without_target_mutation(self):
        source = self.temp_dir / "source"
        shutil.copytree(ROOT, source, symlinks=True)
        (source / ".claude-plugin/plugin.json").write_text("{\n")
        target = self._make_sync_target()
        result = self._run_sync_from(source, target)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "unrelated.txt").read_text(), "preserve\n")
        self.assertFalse((target / ".claude/skills/paper-citation-lookup/SKILL.md").exists())

    def test_validator_rejects_malformed_frontmatter_without_target_mutation(self):
        source = self.temp_dir / "source"
        shutil.copytree(ROOT, source, symlinks=True)
        skill_path = source / "skills/paper-citation-lookup/SKILL.md"
        skill_path.write_text(skill_path.read_text().replace("name: paper-citation-lookup", "name: <id>"))
        target = self._make_sync_target()
        result = self._run_sync_from(source, target)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "unrelated.txt").read_text(), "preserve\n")
        self.assertFalse((target / ".claude/skills/paper-citation-lookup/SKILL.md").exists())

    def test_validator_rejects_missing_support_resource_without_target_mutation(self):
        source = self.temp_dir / "source"
        shutil.copytree(ROOT, source, symlinks=True)
        (source / "skills/paper-citation-lookup/references/source_priority.md").unlink()
        target = self._make_sync_target()
        result = self._run_sync_from(source, target)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "unrelated.txt").read_text(), "preserve\n")
        self.assertFalse((target / ".claude/skills/paper-citation-lookup/SKILL.md").exists())

    def test_validator_rejects_missing_eval_resource_without_target_mutation(self):
        source = self.temp_dir / "source"
        shutil.copytree(ROOT, source, symlinks=True)
        evals_path = source / "skills/t2i-rank1-diagnosis/evals/evals.json"
        payload = json.loads(evals_path.read_text())
        payload["evals"][0]["files"].append("fixtures/missing.json")
        evals_path.write_text(json.dumps(payload))
        target = self._make_sync_target()
        result = self._run_sync_from(source, target)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "unrelated.txt").read_text(), "preserve\n")
        self.assertFalse((target / ".claude/skills/paper-citation-lookup/SKILL.md").exists())

    def test_validator_rejects_forbidden_package_path_without_target_mutation(self):
        source = self.temp_dir / "source"
        shutil.copytree(ROOT, source, symlinks=True)
        (source / "skills/__pycache__").mkdir()
        target = self._make_sync_target()
        result = self._run_sync_from(source, target)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "unrelated.txt").read_text(), "preserve\n")
        self.assertFalse((target / ".claude/skills/paper-citation-lookup/SKILL.md").exists())

    def test_resolver_parses_quoted_bibtex_and_resolves_doi(self):
        resolver = load_resolver()
        bib = self.temp_dir / "quoted.bib"
        bib.write_text(
            '@article{quoted2024,\n'
            '  title = "A Quoted Title",\n'
            '  doi = "10.1234/example.doi",\n'
            '  url = "https://publisher.example/paper"\n'
            '}\n'
        )
        entries = resolver.parse_bibtex(bib)
        self.assertEqual(entries[0]["title"], "A Quoted Title")
        self.assertEqual(entries[0]["doi"], "10.1234/example.doi")
        with mock.patch.object(resolver, "http_get_json", return_value={"data": []}), mock.patch.object(
            resolver, "http_status", return_value=200
        ):
            result = resolver.resolve_one(entries[0])
        self.assertEqual(result["recommended_source"], "https://doi.org/10.1234/example.doi")
        self.assertIn(
            {"type": "doi", "url": "https://doi.org/10.1234/example.doi", "status": 200},
            result["candidates"],
        )

    def test_resolver_accepts_doi_input(self):
        resolver = load_resolver()
        with mock.patch.object(resolver, "http_status", return_value=200):
            result = resolver.resolve_one({"doi": "10.5555/direct.doi", "key": "direct"})
        self.assertEqual(result["recommended_source"], "https://doi.org/10.5555/direct.doi")

    def test_resolver_cli_accepts_doi_input(self):
        resolver = load_resolver()
        output = io.StringIO()
        with mock.patch.object(resolver, "http_status", return_value=200), mock.patch.object(
            sys, "argv", ["resolve_paper.py", "--doi", "10.5555/cli.doi"]
        ), contextlib.redirect_stdout(output):
            resolver.main()
        result = json.loads(output.getvalue())
        self.assertEqual(result["doi"], "10.5555/cli.doi")
        self.assertEqual(result["recommended_source"], "https://doi.org/10.5555/cli.doi")

    def _make_sync_target(self):
        target = self.temp_dir / "target"
        (target / ".git").mkdir(parents=True)
        (target / ".claude/skills").mkdir(parents=True)
        (target / "AGENTS.md").write_text("target\n")
        (target / "unrelated.txt").write_text("preserve\n")
        return target

    def _run_sync_from(self, source, target):
        script = source / "scripts/sync-to-lab-clip.sh"
        return subprocess.run([script, target], cwd=source, text=True, capture_output=True)

    def test_sync_script_rejects_incompatible_target(self):
        result = subprocess.run(
            [ROOT / "scripts/sync-to-lab-clip.sh", self.temp_dir],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lab_clip", result.stderr)

    def test_sync_script_rejects_symlinked_ancestor(self):
        real_parent = self.temp_dir / "real-parent"
        target = real_parent / "lab_clip"
        (target / ".git").mkdir(parents=True)
        (target / "AGENTS.md").write_text("test target\n")
        for name in EXPECTED_SKILLS:
            destination = target / ".claude" / "skills" / name
            destination.mkdir(parents=True)
            (destination / "stale.txt").write_text("remove me\n")
        sentinel = target / "unrelated.txt"
        sentinel.write_text("preserve me\n")
        linked_parent = self.temp_dir / "linked-parent"
        linked_parent.symlink_to(real_parent, target_is_directory=True)

        result = subprocess.run(
            [ROOT / "scripts/sync-to-lab-clip.sh", linked_parent / "lab_clip"],
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("심볼릭", result.stderr)
        self.assertEqual(sentinel.read_text(), "preserve me\n")

    def test_sync_script_rejects_missing_skills_parent_without_mutation(self):
        target = self.temp_dir / "lab_clip"
        (target / ".git").mkdir(parents=True)
        (target / "AGENTS.md").write_text("test target\n")

        result = subprocess.run(
            [ROOT / "scripts/sync-to-lab-clip.sh", target],
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(".claude", result.stderr)
        self.assertFalse((target / ".claude").exists())

    def test_sync_script_updates_only_expected_skill_destinations(self):
        target = self.temp_dir / "lab_clip"
        (target / ".git").mkdir(parents=True)
        (target / "AGENTS.md").write_text("test target\n")
        unrelated = target / "unrelated" / "sentinel.txt"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text("preserve me\n")
        for name in EXPECTED_SKILLS:
            destination = target / ".claude" / "skills" / name
            destination.mkdir(parents=True)
            (destination / "stale.txt").write_text("remove me\n")

        result = subprocess.run(
            [ROOT / "scripts/sync-to-lab-clip.sh", target],
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(unrelated.read_text(), "preserve me\n")
        for name in EXPECTED_SKILLS:
            source = SKILLS / name
            destination = target / ".claude" / "skills" / name
            source_files = {
                path.relative_to(source)
                for path in source.rglob("*")
                if path.is_file()
            }
            destination_files = {
                path.relative_to(destination)
                for path in destination.rglob("*")
                if path.is_file()
            }
            self.assertEqual(destination_files, source_files, name)
            for relative in source_files:
                self.assertEqual(
                    (destination / relative).read_bytes(),
                    (source / relative).read_bytes(),
                    f"{name}: {relative}",
                )
            self.assertFalse((destination / "stale.txt").exists())
            self.assertIn(name, result.stdout)
