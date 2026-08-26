#!/usr/bin/env bash
set -euo pipefail

SKILLS=(
  "paper-citation-lookup"
  "prior-research-brief"
  "t2i-rank1-diagnosis"
)

fail() {
  printf '오류: %s\n' "$*" >&2
  exit 1
}

if (( $# != 1 )); then
  fail "lab_clip 대상 경로 하나만 지정해야 합니다: $0 <lab-clip-path>"
fi

TARGET_INPUT=$1
[[ -n "$TARGET_INPUT" ]] || fail "빈 경로는 lab_clip 대상이 될 수 없습니다"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
SOURCE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)

validate_source() {
  [[ -d "$SOURCE_ROOT/skills" ]] || fail "유효한 lab_clip 스킬 번들이 없습니다: $SOURCE_ROOT/skills"
  [[ -f "$SOURCE_ROOT/.claude-plugin/plugin.json" ]] || fail "Claude 번들 매니페스트가 없습니다"
  [[ -f "$SOURCE_ROOT/.codex-plugin/plugin.json" ]] || fail "Codex 번들 매니페스트가 없습니다"

  local skill source_dir entry entry_name
  for skill in "${SKILLS[@]}"; do
    source_dir="$SOURCE_ROOT/skills/$skill"
    [[ -d "$source_dir" && ! -L "$source_dir" ]] || fail "번들 스킬 디렉터리가 없습니다: $source_dir"
    [[ -f "$source_dir/SKILL.md" && ! -L "$source_dir/SKILL.md" ]] || fail "번들 스킬 문서가 없습니다: $source_dir/SKILL.md"
  done

  shopt -s nullglob
  for entry in "$SOURCE_ROOT/skills"/*; do
    [[ -d "$entry" ]] || continue
    entry_name=${entry##*/}
    case "$entry_name" in
      paper-citation-lookup|prior-research-brief|t2i-rank1-diagnosis) ;;
      *) fail "번들에 허용되지 않은 스킬이 있습니다: $entry_name" ;;
    esac
  done
}

validate_source
command -v rsync >/dev/null 2>&1 || fail "rsync가 필요합니다"

case "$TARGET_INPUT" in
  /|.|..)
    fail "root-like 경로는 lab_clip 대상이 될 수 없습니다"
    ;;
esac

[[ ! -L "$TARGET_INPUT" ]] || fail "심볼릭 링크 경로는 lab_clip 대상이 될 수 없습니다"
[[ -d "$TARGET_INPUT" ]] || fail "lab_clip 대상 디렉터리가 없습니다: $TARGET_INPUT"
TARGET_ROOT=$(CDPATH= cd -- "$TARGET_INPUT" && pwd -P) || fail "lab_clip 대상 경로를 해석할 수 없습니다: $TARGET_INPUT"
[[ "$TARGET_ROOT" != / ]] || fail "root-like 경로는 lab_clip 대상이 될 수 없습니다"
[[ "$TARGET_ROOT" != "$SOURCE_ROOT" ]] || fail "번들 자체는 lab_clip 동기화 대상이 될 수 없습니다"
[[ -e "$TARGET_ROOT/.git" && ! -L "$TARGET_ROOT/.git" ]] || fail "lab_clip 대상에 .git이 필요합니다: $TARGET_ROOT"
[[ -f "$TARGET_ROOT/AGENTS.md" && ! -L "$TARGET_ROOT/AGENTS.md" ]] || fail "lab_clip 대상에 AGENTS.md가 필요합니다: $TARGET_ROOT"

CLAUDE_ROOT="$TARGET_ROOT/.claude"
SKILLS_ROOT="$CLAUDE_ROOT/skills"
[[ ! -e "$CLAUDE_ROOT" || -d "$CLAUDE_ROOT" ]] || fail "lab_clip의 .claude 경로가 디렉터리가 아닙니다"
[[ ! -L "$CLAUDE_ROOT" ]] || fail "lab_clip의 .claude 심볼릭 링크는 허용되지 않습니다"
[[ ! -L "$SKILLS_ROOT" ]] || fail "lab_clip의 .claude/skills 심볼릭 링크는 허용되지 않습니다"
mkdir -p -- "$SKILLS_ROOT"
[[ ! -L "$SKILLS_ROOT" && -d "$SKILLS_ROOT" ]] || fail "lab_clip의 .claude/skills 경로가 안전하지 않습니다"

EXPECTED_SKILLS_ROOT=$(CDPATH= cd -- "$SKILLS_ROOT" && pwd -P)
[[ "$EXPECTED_SKILLS_ROOT" == "$TARGET_ROOT/.claude/skills" ]] || fail "lab_clip 스킬 대상 경로가 예상과 다릅니다"

DESTINATIONS=()
for skill in "${SKILLS[@]}"; do
  destination="$EXPECTED_SKILLS_ROOT/$skill"
  [[ ! -L "$destination" ]] || fail "lab_clip 스킬 대상이 심볼릭 링크입니다: $destination"
  [[ ! -e "$destination" || -d "$destination" ]] || fail "lab_clip 스킬 대상이 디렉터리가 아닙니다: $destination"
  DESTINATIONS+=("$destination")
done

for index in "${!SKILLS[@]}"; do
  skill="${SKILLS[$index]}"
  source_dir="$SOURCE_ROOT/skills/$skill"
  destination="${DESTINATIONS[$index]}"
  mkdir -p -- "$destination"
  [[ -d "$destination" && ! -L "$destination" ]] || fail "lab_clip 스킬 대상 디렉터리를 만들 수 없습니다: $destination"
  resolved_destination=$(CDPATH= cd -- "$destination" && pwd -P)
  [[ "$resolved_destination" == "$EXPECTED_SKILLS_ROOT/$skill" ]] || fail "lab_clip 스킬 대상 경로가 예상과 다릅니다: $destination"
  rsync --delete --archive -- "$source_dir/" "$resolved_destination/"
  printf 'updated skill: %s\n' "$skill"
done
