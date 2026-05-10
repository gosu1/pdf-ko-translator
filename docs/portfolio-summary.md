# 포트폴리오 요약

## 프로젝트명

Layout-Preserving PDF Korean Translator

## 한 줄 설명

pdf2zh, Gemini, PyMuPDF 기반 QA를 결합해 영어 기술 PDF를 한국어 PDF로 변환하는 문서 번역 자동화 파이프라인입니다.

## 문제 정의

기술 PDF는 복잡한 레이아웃, 그림, 수식, 표, 텍스트 박스가 섞여 있어 단순 번역만으로는 결과물이 쉽게 깨집니다. 특히 원문/번역문 겹침, 한글 폰트 깨짐, 미번역 캡션, 이미지 안 텍스트 누락 문제가 자주 발생합니다.

## 해결 방법

Python으로 `pdf2zh` 기반 번역 래퍼를 만들고, 번역 후 PyMuPDF로 PDF를 분석해 QA 리포트를 생성했습니다. 리포트는 미번역 영어 잔여물, 이미지 중심 페이지, OCR 필요 여부, 후처리 권장 사항을 기록합니다.

## 성과

- 번역 결과의 품질 문제를 조기에 발견할 수 있도록 QA 가시성 확보
- PDF 번역 결과를 공유하기 전에 검수 가능한 구조 마련
- Discord Bot 또는 agent workflow와 연결 가능한 재사용형 CLI 파이프라인 구성

## 키워드

Python, PDF Processing, Gemini API, LLM Automation, PyMuPDF, Document AI, MLOps, QA Automation
