# 3T CLIP Skill Distribution Bundle

This repository distributes three reusable skills for the `lab_clip` research repository as a single bundle.

- `paper-citation-lookup`: Verifies paper identifiers and references, then finds reliable primary sources.
- `prior-research-brief`: Performs a concise survey of prior research on a topic and summarizes approaches and gaps.
- `t2i-rank1-diagnosis`: Diagnoses causes of degraded t2i R@1 in `lab_clip`'s CLIP-based text-to-image retrieval.

## Prerequisites

Standard installation requires Node.js and `npx`. Claude installation requires the Claude Code CLI, while Codex installation requires the Codex CLI and plugin support. Network access is required to install or update from the GitHub repository.

When checking bibliographic information, `paper-citation-lookup` may access external academic services named in its instructions, such as arXiv and Semantic Scholar. Installed skills may execute commands or scripts according to their instructions, so review this repository's tags and scripts before use and install only releases you trust.

## Installation

### Install everything with `npx skills`

Install all three skills in the current project at once.

```bash
npx skills@latest add jayn2u/3t-clip-skills --all
```

Use the current CLI's `--global` (`-g`) option for a user-scoped installation. Add `--agent <agent>` (`-a`) to select a specific agent, or `--yes` (`-y`) to skip confirmation. Project installations are written to the current repository, while global installations are written to the user's skill directory; do not confuse the two scopes.

### Claude Code plugin

Register the GitHub marketplace and install the plugin from the Claude Code command line. `--scope project` or `--scope local` changes the declaration scope; the default is the user scope.

```bash
claude plugin marketplace add https://github.com/jayn2u/3t-clip-skills.git
claude plugin install 3t-clip@3t-clip --scope project
```

In interactive Claude Code, perform the same steps as follows:

```text
/plugin marketplace add https://github.com/jayn2u/3t-clip-skills.git
/plugin install 3t-clip@3t-clip
/reload-plugins
```

After installation, invoke the three skills with these explicit commands:

```text
/3t-clip:paper-citation-lookup
/3t-clip:prior-research-brief
/3t-clip:t2i-rank1-diagnosis
```

### Codex plugin

Add the repository to the Codex plugin marketplace and install the bundle. You can use either `owner/repo` notation or an HTTPS Git URL.

```bash
codex plugin marketplace add jayn2u/3t-clip-skills
codex plugin add 3t-clip@3t-clip
```

After restarting Codex, invoke the three skills explicitly as follows:

```text
$3t-clip:paper-citation-lookup
$3t-clip:prior-research-brief
$3t-clip:t2i-rank1-diagnosis
```

The Codex marketplace uses a thin release adapter that points directly to the canonical `skills/` directory. It includes only `skills/.codex-plugin/plugin.json` as additional metadata and does not duplicate skill files, allowing all three skills to be installed without placing repository metadata in the installation cache.

Codex's unauthenticated plugin catalog provides the installed plugin identifier and cache path, but it does not return skill invocation identifiers. The `$3t-clip:<skill>` notation above is the bundle invocation contract inferred from the plugin identifier and the installed skill directories that pass official validation.

## Automatic Selection and Direct Invocation

All three skills support automatic selection and direct user invocation. Requests about checking paper claims or references automatically select `paper-citation-lookup`; topic-focused prior-research exploration selects `prior-research-brief`; and `lab_clip` retrieval results or t2i R@1 diagnosis selects `t2i-rank1-diagnosis`. When you need to force a specific skill, use the namespaced command or `$` invocation shown above.

`t2i-rank1-diagnosis` can run only in a compatible `lab_clip` checkout. That checkout must contain the `AGENTS.md`, domain documents, configuration YAML files, `src` modules, training outputs, and W&B metadata referenced by the instructions. The skill may be installed in other projects, but when invoked from an incompatible location it must clearly explain why and leave the project unchanged.

## Updating and Removing

Use `@latest` only when you intentionally want the newest version. Pin a SemVer tag for reproducible runs. The Claude and Codex manifest versions in this bundle use the same `MAJOR.MINOR.PATCH` version: incompatible instruction changes increment major, new features increment minor, and bug fixes or documentation changes increment patch.

```bash
npx skills@latest update -p paper-citation-lookup prior-research-brief t2i-rank1-diagnosis -y
npx skills@latest remove paper-citation-lookup prior-research-brief t2i-rank1-diagnosis -y

claude plugin marketplace update 3t-clip
claude plugin update 3t-clip@3t-clip --scope project
claude plugin uninstall 3t-clip@3t-clip --scope project
claude plugin marketplace remove 3t-clip

codex plugin marketplace upgrade
codex plugin remove 3t-clip@3t-clip
codex plugin marketplace remove 3t-clip
```

Claude updates may require a restart. For Codex, refresh the remote snapshot with `upgrade`, then run `plugin add` again. Use commands matching the installation scope, and do not assume that removing a global installation also removes a project installation.

## Synchronizing with the `lab_clip` Project

The `skills/` directory in this repository is the sole source of truth. The following command synchronizes only the three directories in the validated bundle to the specified `lab_clip` checkout.

```bash
./scripts/sync-to-lab-clip.sh /mnt/data/lab_clip
```

The target must be an actual `lab_clip` repository containing both `<target>/.git` and `<target>/AGENTS.md`. The parent directory `<target>/.claude/skills/` must already exist; the script does not create or delete this parent. After validating the bundle manifests and all three `SKILL.md` files, the script applies `rsync --delete` only to these three paths:

```text
<target>/.claude/skills/paper-citation-lookup/
<target>/.claude/skills/prior-research-brief/
<target>/.claude/skills/t2i-rank1-diagnosis/
```

Stale files inside each target may be removed, and the three target directories may be created if they do not exist. The parent and all other files and directories in the target repository are left untouched. The script rejects empty paths, root paths, the bundle itself, directories without the required markers, and targets with symbolic-link path components. Tests use temporary targets only and never synchronize with the real `/mnt/data/lab_clip`.

Before synchronization, a reusable offline validator checks the JSON manifests, skill frontmatter, support files, and eval resource paths. To validate the bundle only, run:

```bash
uv run python scripts/validate_bundle.py .
```

## Network and Security Boundaries

Installations through `npx`, the Claude marketplace, and the Codex marketplace retrieve repositories and plugin metadata over the network. Follow your organization's policies for GitHub and external academic-service access, and review the SemVer tag or commit before installing when appropriate. Code executed according to skill instructions can read files and run commands with the user's permissions, so do not install bundles from untrusted sources. This repository contains no API keys, W&B credentials, training outputs, or private paper corpora.

## License

The bundle's original documentation and scripts are distributed under the [MIT License](LICENSE). Copyright and terms of use for external services and papers referenced by each skill apply separately; this license does not grant permission to redistribute third-party materials.
