import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
EXPECTED_SKILLS = {
    "paper-citation-lookup",
    "prior-research-brief",
    "t2i-rank1-diagnosis",
}


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
        self.assertEqual(codex["plugins"][0]["source"]["path"], "./")

    def test_codex_marketplace_source_resolves_root_payload(self):
        marketplace = json.loads(
            (ROOT / ".agents/plugins/marketplace.json").read_text()
        )
        entry = marketplace["plugins"][0]
        source_root = (ROOT / entry["source"]["path"]).resolve()
        self.assertEqual(entry["name"], "3t-clip")
        self.assertEqual(entry["source"]["source"], "local")
        self.assertEqual(source_root, ROOT)
        self.assertTrue((source_root / ".codex-plugin/plugin.json").is_file())
        for name in EXPECTED_SKILLS:
            self.assertTrue((source_root / "skills" / name / "SKILL.md").is_file(), name)
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Developer Tools")

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
            self.assertIn(f"${name}", readme)
        self.assertIn("lab_clip", readme)

    def test_sync_script_rejects_incompatible_target(self):
        result = subprocess.run(
            [ROOT / "scripts/sync-to-lab-clip.sh", self.temp_dir],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lab_clip", result.stderr)

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
