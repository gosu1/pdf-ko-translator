#!/usr/bin/env python3
"""PDFMathTranslate의 pdf2zh CLI를 사용해 영어/과학 PDF를 한국어로 번역하는 래퍼입니다.

이 파일은 실제 PDF 레이아웃 보존 번역은 upstream `pdf2zh` 명령에 위임하고,
포트폴리오 프로젝트에서 재사용하기 쉽도록 입력 검증, 옵션 전달, 결과 파일 목록 출력을 담당합니다.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="pdf2zh를 사용해 PDF를 한국어로 번역합니다.")
    parser.add_argument("pdf", help="입력 PDF 경로")
    parser.add_argument("-o", "--output-dir", default=None, help="번역된 PDF를 저장할 디렉터리")
    parser.add_argument("-s", "--service", default=None, help="pdf2zh 번역 서비스 예: google, bing, gemini:gemini-2.5-flash")
    parser.add_argument("-p", "--pages", default=None, help="번역할 페이지 범위 예: 1-3,5")
    parser.add_argument("-t", "--threads", default=None, help="pdf2zh에 전달할 스레드 수")
    parser.add_argument("--mode", default=None, help="pdf2zh 모드. 설치된 버전이 지원하는 경우 precise 등 사용 가능")
    parser.add_argument("--prompt", default=None, help="LLM 서비스에 사용할 커스텀 프롬프트 파일")
    parser.add_argument("--ignore-cache", action="store_true", help="캐시를 무시하고 강제로 다시 번역")
    parser.add_argument("--skip-subset-fonts", action="store_true", help="호환성을 위해 폰트 서브셋 생성을 비활성화")
    parser.add_argument("--extra", nargs=argparse.REMAINDER, help="--extra 뒤에 적은 추가 인자를 pdf2zh에 그대로 전달")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf = Path(args.pdf).expanduser().resolve()
    if not pdf.exists() or pdf.suffix.lower() != ".pdf":
        print(f"입력 파일이 없거나 PDF가 아닙니다: {pdf}", file=sys.stderr)
        return 2

    exe = shutil.which("pdf2zh")
    if not exe:
        print(
            "pdf2zh 명령을 찾을 수 없습니다. 먼저 PDFMathTranslate를 설치하세요. 예:\n"
            "  pip install pdf2zh\n"
            "또는:\n"
            "  pip install uv && uv tool install --python 3.12 pdf2zh",
            file=sys.stderr,
        )
        return 127

    out_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else pdf.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # pdf2zh에 기본 언어 방향(en -> ko)과 출력 경로를 지정합니다.
    cmd = [exe, str(pdf), "-li", "en", "-lo", "ko", "-o", str(out_dir)]
    if args.service:
        cmd += ["-s", args.service]
    if args.pages:
        cmd += ["-p", args.pages]
    if args.threads:
        cmd += ["-t", args.threads]
    if args.mode:
        cmd += ["--mode", args.mode]
    if args.prompt:
        cmd += ["--prompt", str(Path(args.prompt).expanduser().resolve())]
    if args.ignore_cache:
        cmd.append("--ignore-cache")
    if args.skip_subset_fonts:
        cmd.append("--skip-subset-fonts")
    if args.extra:
        cmd += args.extra

    print("실행 명령:", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(out_dir))
    if proc.returncode != 0:
        return proc.returncode

    stem = pdf.stem
    candidates = sorted(out_dir.glob(f"{stem}*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    print("\n생성된 PDF:")
    for path in candidates[:10]:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
