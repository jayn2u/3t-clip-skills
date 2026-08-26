# 3T CLIP 스킬 배포 번들

이 저장소는 `lab_clip` 연구 저장소에서 재사용하는 세 가지 스킬을 하나의 번들로 배포합니다.

- `paper-citation-lookup`: 논문 식별자와 참고문헌을 검증하고 신뢰할 수 있는 원문을 찾습니다.
- `prior-research-brief`: 주제별 선행연구를 짧게 조사하고 접근법과 공백을 정리합니다.
- `t2i-rank1-diagnosis`: `lab_clip`의 CLIP 기반 text-to-image 검색에서 t2i R@1 저하 원인을 진단합니다.

## 사전 조건

표준 설치에는 Node.js와 `npx`가 필요합니다. Claude 설치에는 Claude Code CLI가, Codex 설치에는 Codex CLI와 플러그인 기능이 필요합니다. GitHub 저장소에서 설치·업데이트하려면 네트워크가 필요합니다.

`paper-citation-lookup`은 문헌 정보를 확인할 때 arXiv, Semantic Scholar 등 지시에 적힌 외부 학술 서비스에 접속할 수 있습니다. 설치된 스킬은 지시문에 따라 명령이나 스크립트를 실행할 수 있으므로, 사용 전에 이 저장소의 태그와 스크립트를 검토하고 신뢰할 수 있는 릴리스만 설치하십시오.

## 설치

### `npx skills`로 전체 설치

세 스킬을 현재 프로젝트에 한 번에 설치합니다.

```bash
npx skills@latest add jayn2u/3t-clip-skills --all
```

현재 CLI의 `--global`(`-g`) 옵션을 사용하면 사용자 범위에 설치할 수 있습니다. 특정 에이전트만 선택하려면 `--agent <agent>`(`-a`)를 추가하고, 자동 확인을 생략하려면 `--yes`(`-y`)를 사용하십시오. 프로젝트 설치는 현재 저장소에, 전역 설치는 사용자 스킬 디렉터리에 기록되므로 두 범위를 혼동하지 마십시오.

### Claude Code 플러그인

Claude Code의 명령행에서 GitHub 마켓플레이스를 등록하고 플러그인을 설치합니다. `--scope project` 또는 `--scope local`은 선언 범위를 바꾸며, 기본값은 사용자 범위입니다.

```bash
claude plugin marketplace add https://github.com/jayn2u/3t-clip-skills.git
claude plugin install 3t-clip@3t-clip --scope project
```

대화형 Claude Code에서는 같은 작업을 다음과 같이 수행할 수 있습니다.

```text
/plugin marketplace add https://github.com/jayn2u/3t-clip-skills.git
/plugin install 3t-clip@3t-clip
/reload-plugins
```

설치 후 세 스킬은 다음의 명시적 명령으로 호출할 수 있습니다.

```text
/3t-clip:paper-citation-lookup
/3t-clip:prior-research-brief
/3t-clip:t2i-rank1-diagnosis
```

### Codex 플러그인

Codex 플러그인 마켓플레이스에 저장소를 추가하고 번들을 설치합니다. `owner/repo` 표기 또는 HTTPS Git URL을 사용할 수 있습니다.

```bash
codex plugin marketplace add jayn2u/3t-clip-skills
codex plugin add 3t-clip@3t-clip
```

Codex를 다시 시작한 뒤 세 스킬은 다음의 명시적 호출로 사용할 수 있습니다.

```text
$paper-citation-lookup
$prior-research-brief
$t2i-rank1-diagnosis
```

## 자동 선택과 직접 호출

세 스킬 모두 자동 선택과 사용자 직접 호출을 허용합니다. 요청 내용이 논문 주장이나 참고문헌 확인이면 `paper-citation-lookup`, 주제 중심의 선행연구 탐색이면 `prior-research-brief`, `lab_clip`의 검색 실행 결과와 t2i R@1 진단이면 `t2i-rank1-diagnosis`가 자동으로 선택됩니다. 결과를 특정 스킬로 고정해야 할 때는 위의 네임스페이스 명령 또는 `$` 호출을 사용하십시오.

`t2i-rank1-diagnosis`는 호환되는 `lab_clip` 체크아웃에서만 실행할 수 있습니다. 해당 체크아웃에는 지시문이 참조하는 `AGENTS.md`, domain 문서, 설정 YAML, `src` 모듈, 학습 산출물, W&B 메타데이터가 있어야 합니다. 다른 프로젝트에 설치하는 것은 가능하지만 호환되지 않는 위치에서 호출하면 이유를 분명히 알리고 프로젝트를 변경하지 않아야 합니다.

## 업데이트와 제거

`@latest`는 최신 버전을 의도적으로 선택할 때만 사용하고, 재현 가능한 실행에는 SemVer 태그를 고정하십시오. 이 번들의 Claude와 Codex 매니페스트 버전은 같은 `MAJOR.MINOR.PATCH` 버전을 사용하며, 호환되지 않는 지시문 변경은 major, 새 기능은 minor, 버그 수정과 문서 수정은 patch로 올립니다.

```bash
npx skills@latest update
npx skills@latest remove paper-citation-lookup
npx skills@latest remove prior-research-brief
npx skills@latest remove t2i-rank1-diagnosis

claude plugin marketplace update 3t-clip
claude plugin update 3t-clip@3t-clip
claude plugin uninstall 3t-clip@3t-clip
claude plugin marketplace remove 3t-clip

codex plugin marketplace upgrade
codex plugin remove 3t-clip@3t-clip
codex plugin marketplace remove 3t-clip
```

Claude의 업데이트는 재시작이 필요할 수 있습니다. Codex 마켓플레이스는 `upgrade`로 원격 스냅샷을 새로 고친 뒤 다시 `plugin add`할 수 있습니다. 설치 범위에 맞는 명령을 사용하고, 전역 설치를 제거한다고 프로젝트 설치가 함께 제거된다고 가정하지 마십시오.

## `lab_clip` 프로젝트 동기화

이 저장소의 `skills/`가 유일한 정본입니다. 다음 명령은 검증된 번들의 세 디렉터리만 지정한 `lab_clip` 체크아웃에 동기화합니다.

```bash
./scripts/sync-to-lab-clip.sh /mnt/data/lab_clip
```

대상은 반드시 실제 `lab_clip` 저장소여야 하며 `<target>/.git`과 `<target>/AGENTS.md`가 모두 있어야 합니다. 또한 `<target>/.claude/skills/` 부모 디렉터리가 미리 존재해야 하며, 스크립트는 이 부모를 만들거나 삭제하지 않습니다. 스크립트는 먼저 번들의 매니페스트와 세 `SKILL.md`를 검증한 다음, 정확히 다음 세 경로에만 `rsync --delete`를 적용합니다.

```text
<target>/.claude/skills/paper-citation-lookup/
<target>/.claude/skills/prior-research-brief/
<target>/.claude/skills/t2i-rank1-diagnosis/
```

각 대상 안의 오래된 파일은 제거될 수 있고 세 대상 디렉터리는 없을 경우 만들어질 수 있지만, 부모와 대상 저장소의 다른 파일·디렉터리는 건드리지 않습니다. 빈 경로, 루트형 경로, 번들 자체, 마커가 없는 디렉터리, 경로 구성 요소가 심볼릭 링크인 대상은 거부합니다. 테스트는 임시 대상만 사용하며 실제 `/mnt/data/lab_clip`에는 동기화하지 않습니다.

## 네트워크와 보안 경계

`npx`, Claude 마켓플레이스, Codex 마켓플레이스 설치는 저장소와 플러그인 메타데이터를 네트워크에서 가져옵니다. 조직 정책에 따라 GitHub 접근과 외부 학술 서비스 접근을 허용하고, 필요하면 SemVer 태그 또는 커밋을 검토한 뒤 설치하십시오. 스킬 지시문에 따라 실행되는 코드는 사용자의 권한으로 파일을 읽거나 명령을 실행할 수 있으므로, 출처가 불분명한 번들을 설치하지 마십시오. 이 저장소에는 API 키, W&B 자격 증명, 학습 산출물, 비공개 논문 코퍼스를 포함하지 않습니다.

## 라이선스

번들의 원본 문서와 스크립트는 [MIT License](LICENSE)로 배포합니다. 각 스킬이 참조하는 외부 서비스와 논문의 저작권·이용 약관은 별도로 적용되며, 이 라이선스가 제3자 자료의 재배포 권한을 대신하지 않습니다.
