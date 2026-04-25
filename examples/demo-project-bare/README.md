# demo-project-bare

mdwiz 의 **WIZARD.md 자동 생성 플로우** 를 체험하기 위한 가상 데모. `WIZARD.md` 가 **일부러 없는 상태** 로 시작한다 — claude 가 README + `scripts/` 를 fs_read 해서 초안을 제안 → 사용자 confirm → `fs_write('WIZARD.md', ...)` 까지의 사이클을 그대로 보여준다.

`../demo-project/` 와 달리 이 디렉터리는 가상의 **정적 블로그 퍼블리시** 도구로, 도메인을 일부러 다르게 잡아 README/스크립트만 가지고 작성되는 WIZARD.md 의 결과물이 직관적으로 비교되도록 했다. 모든 동작은 `echo` / `sleep` / `read` 만 — 외부 시스템에 영향 없음.

## 사용

```bash
cd /path/to/mdwiz/examples/demo-project-bare
mdwiz
```

`WIZARD.md` 가 없으므로 mdwiz 가 첫 메시지에서 **"1번: 만들기 / 2번: 그냥 시작"** 분기를 띄운다.

- **1번 선택** → claude 가 `fs_read('.')` 로 root 훑고 `README.md` + `scripts/*.sh` 읽어서 초안 작성 → preview → confirm → `fs_write('WIZARD.md', ...)` 저장. 다음 mdwiz 부터는 자동 로드.
- **2번 선택** → 가이드 없이 자유 대화로 진행 (원하면 나중에 만들 수도 있음).

## 구성

```
demo-project-bare/
├── README.md          ← 이 파일 (claude 가 WIZARD.md 초안 작성 시 참고)
└── scripts/
    ├── build.sh       ← 가상 사이트 빌드 (비번 X)
    ├── preview.sh     ← 가상 미리보기 서버 (비번 X)
    ├── publish.sh     ← 가상 배포 — `Publish Token:` 프롬프트 (default 패턴 X)
    └── clean.sh       ← /tmp/mdwiz-bare-* 정리
```

## 작업 요약 — 사용자 시각

| # | 작업 | 명령 | 비고 |
|---|---|---|---|
| 1 | 빌드 | `bash scripts/build.sh` | `/tmp/mdwiz-bare-build/` 에 가상 산출물 생성 |
| 2 | 미리보기 | `bash scripts/preview.sh` | 가상 URL 출력 (서버 실제로 안 띄움) |
| 3 | 퍼블리시 | `bash scripts/publish.sh <env>` | `Publish Token:` 입력 필요 — env: dev / prod |
| 4 | 정리 | `bash scripts/clean.sh` | `/tmp/mdwiz-bare-*` 제거 |

## 교육 포인트

1. **생성 플로우** — WIZARD.md 가 없을 때 claude 가 어떻게 초안을 만드는지 (README + 스크립트만으로 충분한지) 직접 본다.
2. **가이드 진화** — `Publish Token:` 은 mdwiz 의 default 패턴 (`Password` / `API Key` / `Token` / ...) 에 부분 매칭되긴 하지만, 처음 publish 실행 시 어떻게 popup 이 뜨는지 / 안 뜨고 inactivity fallback 으로 가는지를 관찰. 안 매칭되면 사용자가 claude 에게 *"방금 그 prompt 를 WIZARD.md frontmatter 의 prompts 에 추가해줘"* 라고 시켜서 가이드를 진화시킨다 — 다음 실행부터 즉시 매칭.

전체 walkthrough 는 `../walkthrough.md` 의 **변형 — WIZARD.md 생성 플로우** 절을 참고.
