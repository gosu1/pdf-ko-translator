# Layout-Preserving PDF Korean Translator

영어 기술 PDF를 한국어 PDF로 변환하면서 원본 레이아웃을 최대한 보존하는 번역 파이프라인입니다.

이 프로젝트는 **PDFMathTranslate/pdf2zh**를 기본 번역 엔진으로 사용하고, **Gemini API**를 번역 백엔드로 연결합니다. 여기에 **PyMuPDF 기반 QA 단계**를 추가해 미번역 영어, 이미지 중심 페이지, OCR 필요 여부 같은 품질 리스크를 리포트로 남깁니다.

## 만든 이유

강의자료나 논문 PDF는 텍스트 박스, 수식, 그림, 표가 섞여 있어서 단순 번역만으로는 품질이 쉽게 깨집니다.

자주 발생하는 문제는 다음과 같습니다.

- 원문 텍스트와 번역 텍스트가 겹침
- 한글 폰트가 깨지거나 표시되지 않음
- 캡션/라벨/그림 안 텍스트가 번역되지 않음
- 복잡한 레이아웃이 무너짐
- 결과물이 생성됐지만 품질 문제를 바로 알기 어려움

그래서 단순한 일회성 번역 명령을 **번역 → 결과 분석 → QA 리포트 생성** 구조로 확장했습니다.

## 주요 기능

- 영어 PDF → 한국어 PDF 변환
- Gemini 기반 `pdf2zh` 번역 연동
- mono PDF / dual bilingual PDF 출력 지원
- 원본 레이아웃 보존 중심의 PDF 번역 워크플로우
- 한글 폰트/호환성 옵션 지원
- Markdown/JSON QA 리포트 생성
- 미번역 영어 잔여물 탐지
- OCR이 필요할 수 있는 이미지 중심 페이지 탐지
- Discord Bot 또는 agent workflow에 붙이기 쉬운 CLI 구조

## 기술 스택

- Python
- PDFMathTranslate / `pdf2zh`
- Gemini API
- PyMuPDF (`fitz`)
- PDF text/layout analysis
- Markdown/JSON QA reporting
- Optional Discord/OpenClaw workflow integration

## 아키텍처

```mermaid
flowchart LR
    A[입력 영어 PDF] --> B[pdf2zh 번역 래퍼]
    B --> C[Gemini 번역 백엔드]
    C --> D[Mono / Dual PDF 생성]
    D --> E[PyMuPDF QA 분석기]
    E --> F[Markdown + JSON QA 리포트]
    F --> G[검수 / 전달]
```

## 빠른 시작

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

기본 Gemini 서비스를 사용하려면 Gemini API Key가 필요합니다.

```bash
cp .env.example .env
# .env 파일을 열어 GEMINI_API_KEY 값을 설정하세요.
```

### 2. PDF 번역 실행

```bash
python src/pdf_ko_translator/pipeline.py examples/sample-input.pdf \
  -o outputs \
  -s gemini:gemini-2.5-flash
```

### 3. 일부 페이지만 테스트

```bash
python src/pdf_ko_translator/pipeline.py examples/sample-input.pdf \
  -o outputs/test \
  -s gemini:gemini-2.5-flash \
  -p 1-3
```

## 출력 예시

```txt
outputs/
├── sample-input-mono.pdf
├── sample-input-dual.pdf
└── qa-logs/
    ├── sample-input-qa-report.md
    └── sample-input-qa-report.json
```

## QA 리포트가 확인하는 것

QA 단계는 원본/번역 PDF를 분석해 다음 정보를 기록합니다.

- 페이지별 한글/영어 문자 수
- 미번역으로 의심되는 영어 snippet
- 이미지 블록 수
- OCR 도구 사용 가능 여부
- 후처리 권장 사항


## 보안 주의사항

다음 파일/정보는 Git에 올리지 마세요.

- `.env`
- API Key
- Discord Bot Token
- 개인 PDF
- 저작권이 있거나 개인정보가 포함된 생성 PDF

공개 저장소에는 `.env.example`과 공개 가능한 샘플 PDF만 포함하는 것을 권장합니다.

## License

MIT
