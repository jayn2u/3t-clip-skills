# 3T CLIP Skill Distribution Bundle Design

## Goal

Publish the three reusable `lab_clip` skills from `3t-clip-skills` as one bundle that supports standard `npx skills`, Claude Code plugins, and Codex plugins while preserving direct user invocation.

The bundle contains:

- `paper-citation-lookup`
- `prior-research-brief`
- `t2i-rank1-diagnosis`

Actual npm publication is outside this change. The `npx` path uses the existing `skills` CLI with the GitHub repository as its source.

## Canonical Source

`3t-clip-skills/skills/<skill-name>/` is the canonical distributable source. Each directory contains its `SKILL.md` and every runtime support file it needs. The three delivery mechanisms consume these same directories; generated or hand-maintained copies for individual agents are prohibited.

The initial import copies the tracked versions from `lab_clip/.claude/skills/`. Future changes are authored in `3t-clip-skills` first. A documented synchronization command updates the project-local copies in `lab_clip` when required.

## Repository Layout

```text
3t-clip-skills/
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── .codex-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── skills/
│   ├── paper-citation-lookup/
│   ├── prior-research-brief/
│   └── t2i-rank1-diagnosis/
├── tests/
├── LICENSE
└── README.md
```

Manifest filenames and final placement may be adjusted only where the current official Claude Code or Codex plugin schema requires a different marketplace location. The shared `skills/` directories remain invariant.

## Installation Interfaces

### Standard npx skills

The repository follows the multi-skill repository layout recognized by the `skills` CLI. The documented all-skill installation is:

```bash
npx skills@latest add jayn2u/3t-clip-skills --all
```

The README also documents agent selection and project/global scope flags supported by the current CLI. The repository does not implement or publish a redundant custom npm installer.

### Claude Code plugin

The repository is a Claude marketplace containing one `3t-clip` plugin. Installing that plugin installs all three skills. Claude exposes plugin skills under namespaced commands:

```text
/3t-clip:paper-citation-lookup
/3t-clip:prior-research-brief
/3t-clip:t2i-rank1-diagnosis
```

Each skill remains model-invocable and user-invocable. None sets `disable-model-invocation: true` or `user-invocable: false`.

### Codex plugin

The repository exposes one `3t-clip` Codex plugin containing the same three skill directories. One plugin installation makes the complete bundle available. Each skill remains eligible for automatic selection and explicit `$skill-name` invocation according to Codex skill behavior.

## Skill Portability Contracts

### paper-citation-lookup

The complete skill directory ships, including `scripts/resolve_paper.py`, `references/source_priority.md`, and eval assets. The resolver remains dependency-free beyond Python's standard library and requires outbound access to its documented scholarly sources.

### prior-research-brief

This skill declares its semantic dependency on the bundled `paper-citation-lookup` skill. References to optional external research skills remain optional and must not prevent the core workflow from running.

### t2i-rank1-diagnosis

This skill is distributable but intentionally repository-aware. Its instructions state that execution requires a compatible `lab_clip` checkout containing the referenced domain documents, configuration, source modules, artifacts, and W&B metadata. Installation may succeed in any project; invocation outside a compatible checkout must fail clearly without mutating the project.

## Evaluation Assets

All three `evals/evals.json` files ship. Every referenced local fixture must exist in the distributed skill directory. The missing `sample_refs.bib` and `t2i-rank1-diagnosis/evals/fixtures/*` inputs are added as deterministic, non-secret fixtures. Tests verify that every path declared by an eval exists.

## Validation and Errors

Automated validation covers:

- all three expected skills are present;
- each `SKILL.md` has valid `name` and `description` frontmatter;
- the directory name and frontmatter name match;
- support files referenced by skill instructions and eval definitions exist;
- Claude and Codex manifests parse and identify one bundle containing all three skills;
- marketplace metadata points to the local plugin correctly;
- packaging excludes worktrees, caches, credentials, and repository-local artifacts;
- installation smoke tests use temporary directories and never overwrite existing user skill directories.

Install and validation failures return non-zero status with the failing skill, path, or manifest field. Tests do not require network access.

## Documentation

The Korean README leads with the three supported installation paths and shows direct invocation examples for every skill. It also documents:

- the difference between automatic selection and direct invocation;
- project versus user-wide installation where supported;
- the `lab_clip` runtime prerequisite for `t2i-rank1-diagnosis`;
- update and uninstall commands;
- source synchronization policy;
- security implications of installing executable skill scripts.

## Versioning and Release Boundary

The repository uses SemVer tags. Plugin manifests and marketplace entries use the same release version. Documentation recommends tagged releases for reproducibility and `@latest` only when users intentionally want the newest release.

This task produces a release-ready repository, local package/plugin validation, a commit, a pushed branch, and a ready-for-review Korean pull request. Creating a GitHub release, publishing npm content, or submitting to an official third-party marketplace requires separate authorization.

## Non-Goals

- Building a custom npm package or installer.
- Making `t2i-rank1-diagnosis` independent of `lab_clip`.
- Bundling optional external research skills referenced by `prior-research-brief`.
- Uploading credentials, W&B data, training artifacts, or private paper corpora.
