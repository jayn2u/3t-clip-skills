import json
import subprocess
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
