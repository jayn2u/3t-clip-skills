import json
import os
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

    @unittest.skipUnless(shutil.which("codex"), "Codex CLI not installed")
    def test_codex_cli_installs_root_marketplace_plugin(self):
        with tempfile.TemporaryDirectory(prefix="task2-codex-home-") as codex_home:
            environment = os.environ.copy()
            environment["CODEX_HOME"] = codex_home
            add = subprocess.run(
                ["codex", "plugin", "marketplace", "add", str(ROOT), "--json"],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertEqual(add.returncode, 0, add.stderr)
            add_payload = json.loads(add.stdout)
            self.assertEqual(Path(add_payload["installedRoot"]), ROOT)
            install = subprocess.run(
                ["codex", "plugin", "add", "3t-clip@3t-clip", "--json"],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            payload = json.loads(install.stdout)
            installed_root = Path(payload["installedPath"])
            self.assertTrue(installed_root.is_relative_to(Path(codex_home)))
            self.assertTrue(installed_root.is_dir())
            for name in EXPECTED_SKILLS:
                self.assertTrue(
                    (installed_root / "skills" / name / "SKILL.md").is_file(), name
                )

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
