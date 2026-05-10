#!/usr/bin/env python3
"""한국어 PDF 번역을 위한 SaaS형 오케스트레이터입니다.

파이프라인 흐름:
1. 안정적인 pdf2zh 래퍼를 실행해 mono/dual 기본 번역 PDF를 생성합니다.
2. 원본/결과 PDF를 분석해 이미지가 많은 페이지와 미번역 영어 잔여물을 찾습니다.
3. OCR 또는 오버레이 후처리가 필요한지 판단할 수 있도록 QA 리포트를 생성합니다.

핵심 아이디어는 `pdf2zh`의 장점을 그대로 활용하되, 품질 문제를 조용히 넘기지 않고
검수 가능한 진단 결과로 드러내는 것입니다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PDF를 한국어로 번역하고 QA 진단 리포트를 생성합니다.")
    p.add_argument("pdf", help="입력 PDF 경로")
    p.add_argument("-o", "--output-dir", default="./outputs", help="생성된 PDF를 저장할 디렉터리")
    p.add_argument("--log-dir", default=None, help="QA md/json 로그 디렉터리. 기본값은 <output-dir>/qa-logs")
    p.add_argument("-s", "--service", default="gemini:gemini-2.5-flash", help="pdf2zh 번역 서비스")
    p.add_argument("-p", "--pages", default=None, help="테스트 실행에 사용할 선택 페이지 범위")
    p.add_argument("-t", "--threads", default=None, help="pdf2zh에 전달할 스레드 수")
    p.add_argument("--mode", default=None, help="pdf2zh 실행 모드")
    p.add_argument("--skip-base", action="store_true", help="pdf2zh 번역을 건너뛰고 기존 출력물만 QA")
    p.add_argument("--ignore-cache", action="store_true", help="기본 번역을 새로 강제 실행. 비용/시간 증가 가능")
    p.add_argument("--skip-subset-fonts", action="store_true", help="pdf2zh에 --skip-subset-fonts 옵션 전달")
    p.add_argument("--extra", nargs=argparse.REMAINDER, help="pdf2zh 래퍼에 그대로 전달할 추가 인자")
    return p.parse_args()


def run(cmd: list[str], env: dict[str, str]) -> None:
    print("실행 명령:", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, env=env)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def find_outputs(pdf: Path, out_dir: Path) -> dict[str, str | None]:
    stem = pdf.stem
    candidates = sorted(out_dir.glob(f"{stem}*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    dual = next((p for p in candidates if "dual" in p.name.lower()), None)
    mono = next((p for p in candidates if "mono" in p.name.lower()), None)
    return {"dual": str(dual) if dual else None, "mono": str(mono) if mono else None}


def parse_page_selection(raw: str | None, page_count: int) -> set[int] | None:
    """pdf2zh 스타일 페이지 범위 문자열을 1부터 시작하는 페이지 번호 집합으로 변환합니다."""
    if not raw:
        return None
    selected: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a) if a else 1
            end = int(b) if b else page_count
            selected.update(range(max(1, start), min(page_count, end) + 1))
        else:
            n = int(part)
            if 1 <= n <= page_count:
                selected.add(n)
    return selected or None


def extract_pdf_stats(path: Path, selected_pages: set[int] | None = None) -> dict[str, Any]:
    try:
        import fitz  # PyMuPDF
    except Exception as e:  # pragma: no cover - 실행 환경 진단용 예외 처리
        return {"error": f"PyMuPDF를 사용할 수 없습니다: {e}"}

    doc = fitz.open(path)
    pages = []
    total = {"chars": 0, "ko": 0, "en": 0, "image_blocks": 0, "untranslated_snippets": 0}
    snippet_re = re.compile(r"[A-Za-z][A-Za-z0-9()\-/–—'\".,:; βγλϕ𝜙𝑡𝑣𝛾𝜆𝛽]{2,}")

    for idx, page in enumerate(doc):
        page_no = idx + 1
        if selected_pages is not None and page_no not in selected_pages:
            continue
        text = page.get_text() or ""
        blocks = page.get_text("dict").get("blocks", [])
        image_blocks = sum(1 for b in blocks if b.get("type") == 1)
        snippets = []
        for m in snippet_re.finditer(text):
            s = " ".join(m.group(0).split())
            # 사람이 읽는 영어 문장/라벨일 가능성이 있는 것만 남기고, 순수 기호/숫자는 제외합니다.
            if len(re.findall(r"[A-Za-z]", s)) >= 3 and s not in snippets:
                snippets.append(s[:120])
            if len(snippets) >= 8:
                break
        ko = len(re.findall(r"[가-힣]", text))
        en = len(re.findall(r"[A-Za-z]", text))
        row = {
            "page": page_no,
            "chars": len(text),
            "ko_chars": ko,
            "en_chars": en,
            "image_blocks": image_blocks,
            "untranslated_snippets": snippets,
        }
        pages.append(row)
        total["chars"] += len(text)
        total["ko"] += ko
        total["en"] += en
        total["image_blocks"] += image_blocks
        total["untranslated_snippets"] += len(snippets)

    return {"file": str(path), "page_count": doc.page_count, "selected_pages": sorted(selected_pages) if selected_pages else None, "total": total, "pages": pages}


def write_report(pdf: Path, report_dir: Path, outputs: dict[str, str | None], pages_arg: str | None = None) -> Path:
    try:
        import fitz
        page_count = fitz.open(pdf).page_count
    except Exception:
        page_count = 0
    selected_pages = parse_page_selection(pages_arg, page_count) if page_count else None
    report: dict[str, Any] = {
        "input": str(pdf),
        "page_selection": sorted(selected_pages) if selected_pages else None,
        "outputs": outputs,
        "diagnostics": {
            "source": extract_pdf_stats(pdf, selected_pages),
            "mono": extract_pdf_stats(Path(outputs["mono"]), selected_pages) if outputs.get("mono") else None,
            "dual": extract_pdf_stats(Path(outputs["dual"]), selected_pages) if outputs.get("dual") else None,
            "ocr_available": bool(shutil.which("tesseract")),
        },
        "recommendation": [],
    }

    mono = report["diagnostics"].get("mono") or {}
    source = report["diagnostics"].get("source") or {}
    if source.get("total", {}).get("image_blocks", 0):
        report["recommendation"].append("원본에 이미지 블록이 있습니다. 이미지 안 라벨은 OCR/오버레이 후처리가 필요할 수 있습니다.")
    if mono.get("total", {}).get("en", 0) > 0:
        report["recommendation"].append("번역된 mono PDF에 영어가 남아 있습니다. 페이지별 snippet을 확인하고 부분 후처리를 고려하세요.")
    if not report["diagnostics"].get("ocr_available"):
        report["recommendation"].append("Tesseract OCR이 설치되어 있지 않아 OCR 오버레이 단계는 현재 사용할 수 없습니다.")

    stem = pdf.stem
    report_dir.mkdir(parents=True, exist_ok=True)
    suffix = ""
    if selected_pages:
        suffix = "-p" + "_".join(map(str, sorted(selected_pages)))
    json_path = report_dir / f"{stem}{suffix}-qa-report.json"
    md_path = report_dir / f"{stem}{suffix}-qa-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# QA 리포트: {pdf.name}"]
    if selected_pages:
        lines += ["", f"선택 페이지: {', '.join(map(str, sorted(selected_pages)))}"]
    lines += ["", "## 생성 파일"]
    for k, v in outputs.items():
        lines.append(f"- {k}: {v or '없음'}")
    lines += ["", "## 권장 조치"]
    lines += [f"- {x}" for x in report["recommendation"]] or ["- 큰 문제는 감지되지 않았습니다."]
    lines += ["", "## 미번역 영어가 많이 남은 페이지"]
    pages = (mono.get("pages") or []) if isinstance(mono, dict) else []
    pages = sorted(pages, key=lambda p: (p.get("en_chars", 0), len(p.get("untranslated_snippets", []))), reverse=True)[:12]
    for p in pages:
        lines.append(f"- p{p['page']}: en={p['en_chars']} ko={p['ko_chars']} images={p['image_blocks']}")
        for s in p.get("untranslated_snippets", [])[:5]:
            lines.append(f"  - `{s}`")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def ensure_pdf_python() -> None:
    """현재 Python에 PyMuPDF가 없으면 pdf2zh가 설치된 Python으로 재실행합니다."""
    try:
        import fitz  # noqa: F401
        return
    except Exception:
        pass
    if os.environ.get("PDF2KO_PIPELINE_REEXEC"):
        return
    pdf2zh = shutil.which("pdf2zh")
    if not pdf2zh:
        return
    bin_dir = Path(pdf2zh).resolve().parent
    for name in ("python3", "python"):
        candidate = bin_dir / name
        if not candidate.exists() or str(candidate) == sys.executable:
            continue
        probe = subprocess.run([str(candidate), "-c", "import fitz"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if probe.returncode == 0:
            env = os.environ.copy()
            env["PDF2KO_PIPELINE_REEXEC"] = "1"
            os.execve(str(candidate), [str(candidate), *sys.argv], env)


def main() -> int:
    ensure_pdf_python()
    args = parse_args()
    pdf = Path(args.pdf).expanduser().resolve()
    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not pdf.exists() or pdf.suffix.lower() != ".pdf":
        print(f"입력 파일이 없거나 PDF가 아닙니다: {pdf}", file=sys.stderr)
        return 2

    wrapper = Path(__file__).resolve().with_name("pdf2ko.py")
    env = os.environ.copy()
    env.setdefault("GEMINI_MODEL", "gemini-2.5-flash")

    if not args.skip_base:
        cmd = [sys.executable, str(wrapper), str(pdf), "-o", str(out_dir), "-s", args.service]
        if args.pages:
            cmd += ["-p", args.pages]
        if args.threads:
            cmd += ["-t", args.threads]
        if args.mode:
            cmd += ["--mode", args.mode]
        if args.ignore_cache:
            cmd += ["--ignore-cache"]
        if args.skip_subset_fonts:
            cmd += ["--skip-subset-fonts"]
        if args.extra:
            cmd += ["--extra", *args.extra]
        run(cmd, env)

    outputs = find_outputs(pdf, out_dir)
    report_dir = Path(args.log_dir).expanduser().resolve() if args.log_dir else out_dir / "qa-logs"
    report_path = write_report(pdf, report_dir, outputs, args.pages)
    print("\n파이프라인 출력:")
    for label, path in outputs.items():
        print(f"{label}: {path}")
    print(f"qa_report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
