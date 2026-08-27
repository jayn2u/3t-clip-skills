# 3T CLIP Skill Distribution Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package three `lab_clip` skills as one installable bundle for `npx skills`, Claude Code, and Codex with automatic and explicit invocation.

**Architecture:** One canonical root-level `skills/` tree contains complete skill payloads. Claude and Codex plugin manifests reference that shared tree, while offline Python validation tests enforce payload, frontmatter, eval-fixture, manifest, and marketplace contracts.

**Tech Stack:** Agent Skills `SKILL.md`, JSON manifests, Python 3 standard library `unittest`, `npx skills`, Claude Code plugin schema, Codex plugin schema.

**Spec:** `docs/superpowers/specs/2026-08-26-skill-distribution-bundle-design.md`

## Global Constraints

- The bundle contains exactly `paper-citation-lookup`, `prior-research-brief`, and `t2i-rank1-diagnosis`.
- `skills/<skill-name>/` is the only canonical distributable payload.
- All three skills remain model-invocable and user-invocable.
- Tests must run without network access and must not mutate user skill directories.
- Do not build or publish a custom npm package.
- Do not include credentials, W&B data, training artifacts, or private paper corpora.
- Do not write comments in code.

---

### Task 1: Import and validate the canonical skill payloads

**Files:**
- Create: `skills/paper-citation-lookup/SKILL.md`
- Create: `skills/paper-citation-lookup/scripts/resolve_paper.py`
- Create: `skills/paper-citation-lookup/references/source_priority.md`
- Create: `skills/paper-citation-lookup/evals/evals.json`
- Create: `skills/paper-citation-lookup/evals/sample_refs.bib`
- Create: `skills/prior-research-brief/SKILL.md`
- Create: `skills/prior-research-brief/evals/evals.json`
- Create: `skills/t2i-rank1-diagnosis/SKILL.md`
- Create: `skills/t2i-rank1-diagnosis/evals/evals.json`
- Create: `skills/t2i-rank1-diagnosis/evals/fixtures/run_config.json`
- Create: `skills/t2i-rank1-diagnosis/evals/fixtures/train_retrieval.log`
- Create: `skills/t2i-rank1-diagnosis/evals/fixtures/wandb_meta.json`
- Create: `skills/t2i-rank1-diagnosis/evals/fixtures/fold_summary.json`
- Create: `tests/test_bundle.py`

**Interfaces:**
- Consumes: tracked source directories under `/mnt/data/lab_clip/.claude/skills/<skill-name>/`.
- Produces: `EXPECTED_SKILLS: set[str]`, `load_frontmatter(path: Path) -> dict[str, str]`, and a complete offline-validatable `skills/` payload.

- [ ] **Step 1: Write failing bundle discovery and frontmatter tests**

```python
EXPECTED_SKILLS = {
    "paper-citation-lookup",
    "prior-research-brief",
    "t2i-rank1-diagnosis",
}

def test_bundle_contains_exactly_expected_skills(self):
    actual = {path.parent.name for path in SKILLS.glob("*/SKILL.md")}
    self.assertEqual(actual, EXPECTED_SKILLS)

def test_skill_names_match_directories_and_are_invocable(self):
    for name in EXPECTED_SKILLS:
        frontmatter = load_frontmatter(SKILLS / name / "SKILL.md")
        self.assertEqual(frontmatter["name"], name)
        self.assertTrue(frontmatter["description"])
        self.assertNotEqual(frontmatter.get("user-invocable"), "false")
        self.assertNotEqual(frontmatter.get("disable-model-invocation"), "true")
```

- [ ] **Step 2: Run the tests and confirm RED**

Run: `uv run python -m unittest tests.test_bundle -v`

Expected: FAIL because `skills/` does not exist.

- [ ] **Step 3: Import all tracked skill payloads without rewriting their behavior**

Copy the three complete tracked source directories into `skills/`. Preserve executable mode on `resolve_paper.py`. Add no generated agent-specific duplicate directories.

- [ ] **Step 4: Run the tests and confirm GREEN**

Run: `uv run python -m unittest tests.test_bundle -v`

Expected: PASS for discovery and frontmatter tests.

- [ ] **Step 5: Write failing eval-resource tests**

```python
def test_eval_file_references_exist(self):
    for name in EXPECTED_SKILLS:
        eval_dir = SKILLS / name / "evals"
        payload = json.loads((eval_dir / "evals.json").read_text())
        for case in payload["evals"]:
            for relative in case.get("files", []):
                self.assertTrue((eval_dir / relative).is_file(), f"{name}: {relative}")
```

- [ ] **Step 6: Run the resource test and confirm RED**

Run: `uv run python -m unittest tests.test_bundle.BundleTests.test_eval_file_references_exist -v`

Expected: FAIL for `sample_refs.bib` and the four `t2i-rank1-diagnosis` fixture paths.

- [ ] **Step 7: Add deterministic, non-secret eval fixtures**

Create `sample_refs.bib` with exactly the CLIP, ResNet, BERT, and ViT entries expected by eval id 2. Create synthetic diagnosis fixtures whose values encode the assertions in the eval descriptions: epoch-48 best and epoch-60 plateau stop, and five folds with fold 3 having 800 held-out identities, 2.10 mean images, and comparable shared-test top-1.

- [ ] **Step 8: Run all bundle tests and confirm GREEN**

Run: `uv run python -m unittest tests.test_bundle -v`

Expected: PASS.

- [ ] **Step 9: Commit the canonical payload**

```bash
git add skills tests/test_bundle.py
git commit -m "feat: add canonical skill bundle" -m "Co-authored-by: Luna <luna@openai.com>"
```

### Task 2: Add Claude and Codex plugin distribution metadata

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `.codex-plugin/plugin.json`
- Create: `.agents/plugins/marketplace.json`
- Modify: `tests/test_bundle.py`

**Interfaces:**
- Consumes: root-level `skills/` from Task 1.
- Produces: one Claude marketplace plugin named `3t-clip` and one Codex marketplace plugin named `3t-clip`, both resolving to the repository root without copying skills.

- [ ] **Step 1: Write failing manifest tests**

```python
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
```

- [ ] **Step 2: Run manifest tests and confirm RED**

Run: `uv run python -m unittest tests.test_bundle.BundleTests.test_plugin_manifests_name_the_same_bundle tests.test_bundle.BundleTests.test_marketplaces_resolve_local_bundle -v`

Expected: ERROR because manifests are absent.

- [ ] **Step 3: Create the Claude plugin and marketplace manifests**

Use current official Claude schemas. Set one plugin name, description, author, repository, and SemVer version. Point the marketplace source to the repository root so the root `skills/` directory is loaded.

- [ ] **Step 4: Scaffold and adapt the Codex plugin metadata**

Use the `plugin-creator` scaffold and validators rather than inventing the Codex schema. The plugin manifest stays at `.codex-plugin/plugin.json`. The repo marketplace stays at `.agents/plugins/marketplace.json`, identifies `3t-clip`, and contains `policy.installation: "AVAILABLE"`, `policy.authentication: "ON_INSTALL"`, and category `Developer Tools` or the closest accepted validator value.

- [ ] **Step 5: Run manifest and official plugin validators**

Run:

```bash
uv run python -m unittest tests.test_bundle -v
python3 /home/jwchoi/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

Expected: PASS with no placeholders or unsupported fields.

- [ ] **Step 6: Commit plugin metadata**

```bash
git add .claude-plugin .codex-plugin .agents/plugins/marketplace.json tests/test_bundle.py
git commit -m "feat: add Claude and Codex plugin manifests" -m "Co-authored-by: Luna <luna@openai.com>"
```

### Task 3: Document installation, invocation, synchronization, and safety

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `scripts/sync-to-lab-clip.sh`
- Modify: `tests/test_bundle.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the repository and manifest paths from Tasks 1 and 2.
- Produces: a Korean operator guide and `scripts/sync-to-lab-clip.sh <lab-clip-path>` that updates only the three named project-local skill directories after validation.

- [ ] **Step 1: Write failing documentation and sync-contract tests**

```python
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
```

- [ ] **Step 2: Run documentation tests and confirm RED**

Run: `uv run python -m unittest tests.test_bundle.BundleTests.test_readme_documents_every_install_and_invocation tests.test_bundle.BundleTests.test_sync_script_rejects_incompatible_target -v`

Expected: ERROR because README and sync script are absent.

- [ ] **Step 3: Write the Korean README and license**

Document one-command all-skill npx installation, Claude marketplace add/install/reload, Codex marketplace add/install, all six explicit invocation examples, automatic selection, update/uninstall, SemVer policy, prerequisites, network/security implications, and the `t2i-rank1-diagnosis` compatibility boundary. Add the repository's chosen license without copying unlicensed third-party text.

- [ ] **Step 4: Implement the guarded sync script**

The script accepts exactly one explicit target path, requires `<target>/.git` and `<target>/AGENTS.md`, refuses empty or root-like paths, validates the source bundle first, and uses `rsync --delete` only on the three fully resolved `<target>/.claude/skills/<skill-name>/` directories. It prints every updated skill.

- [ ] **Step 5: Add a successful temporary-target sync test**

Create a temp target with `.git`, `AGENTS.md`, and stale files inside only the three named skill destinations. Assert all three payloads are copied, stale files inside those destinations are removed, and an unrelated sentinel remains.

- [ ] **Step 6: Run all offline tests and shell syntax validation**

Run:

```bash
uv run python -m unittest tests.test_bundle -v
bash -n scripts/sync-to-lab-clip.sh
git diff --check
```

Expected: PASS.

- [ ] **Step 7: Commit documentation and synchronization tooling**

```bash
git add README.md LICENSE scripts/sync-to-lab-clip.sh tests/test_bundle.py .gitignore
git commit -m "docs: add bundle installation guide" -m "Co-authored-by: Luna <luna@openai.com>"
```

### Task 4: Run release-readiness verification

**Files:**
- Modify only files whose validation exposes a defect.

**Interfaces:**
- Consumes: completed bundle from Tasks 1-3.
- Produces: recorded evidence that repository structure, plugin manifests, skill payloads, and installation discovery are release-ready.

- [ ] **Step 1: Run the complete offline suite**

Run:

```bash
uv run python -m unittest discover -s tests -v
bash -n scripts/sync-to-lab-clip.sh
python3 /home/jwchoi/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
git diff --check
```

Expected: all tests and validators pass.

- [ ] **Step 2: Validate `npx skills` discovery in a temporary directory**

Run the current `skills` CLI against the local repository using a temporary target and non-interactive all-skill flags. If the CLI cannot install directly from a local path, run its documented repository validation/list command and record that limitation. Do not write to `~/.agents`, `~/.claude`, or `~/.codex`.

Expected: the CLI discovers exactly three skills and selects all three.

- [ ] **Step 3: Inspect repository hygiene**

Run:

```bash
git status --short
git ls-files
git log --oneline --decorate -5
```

Expected: no credentials, caches, worktree internals, or unrelated files; all intended changes are committed.

- [ ] **Step 4: Commit any verification-driven corrections**

```bash
git add <only-corrected-files>
git commit -m "fix: satisfy skill bundle validation" -m "Co-authored-by: Luna <luna@openai.com>"
```

Skip this commit when verification required no corrections.
