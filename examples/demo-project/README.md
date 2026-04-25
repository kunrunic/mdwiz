# demo-project

mdwiz 의 동작을 직접 체험하기 위한 **가상 데모 프로젝트**. 실제로는 아무것도 배포·설치하지 않고, `echo` / `sleep` / `read` 만 쓴다 — 안전.

## 사용

```bash
cd /path/to/mdwiz/examples/demo-project
mdwiz
```

mdwiz 가 자동으로 이 디렉터리의 `WIZARD.md` 를 읽어서 가능한 작업 (`check`, `deploy`, `status`, `cleanup`) 을 안내한다. 사용자가 *"deploy 해줘"* 같이 자연어로 요청하면 claude 가 plan 표 → confirm → 실행 → 비번 popup 이 필요한 단계는 자동 처리.

## 구성

```
demo-project/
├── README.md          ← 이 파일
├── WIZARD.md          ← mdwiz 가 자동 로드하는 워크플로우 가이드
└── scripts/
    ├── check.sh       ← 의존성 점검 (비번 X)
    ├── deploy.sh      ← 가상 배포 (비번 popup 트리거)
    ├── status.sh      ← 가상 상태 조회
    └── cleanup.sh     ← 임시 파일 정리
```

전체 walkthrough 는 `../walkthrough.md` 참고.
