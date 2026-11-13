"""12개 규정 절을 A4 인쇄 기준 12페이지로 나누는 로컬 HTML 편집본."""
from html import escape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "policies" / "store_policy.md"
    text = source.read_text(encoding="utf-8")
    intro, *sections = re.split(r"(?m)^## ", text)
    pages = []
    for i, section in enumerate(sections, 1):
        title, _, body = section.partition("\n")
        paragraphs = "".join(f"<p>{escape(p.strip())}</p>" for p in body.split("\n\n") if p.strip())
        pages.append(f'<section class="page"><small>연습매장 합성 운영 규정 / training-policy-v1</small><h1>{escape(title)}</h1>{paragraphs}<footer>{i:02d} / 12 · 실제 약관이나 법률 자문이 아닌 RAG 학습용 자료</footer></section>')
    assert len(pages) == 12
    html = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>매장 운영 규정집 - 12페이지 학습 편집본</title>
<style>@page{size:A4;margin:0}*{box-sizing:border-box}body{margin:0;background:#25324b;color:#e5edf8;font-family:'Malgun Gothic',sans-serif}.page{position:relative;width:210mm;min-height:297mm;padding:22mm;margin:8mm auto;background:#0b1120;break-after:page}.page:last-child{break-after:auto}small{color:#67decc}h1{font-size:23px;line-height:1.5;margin:10mm 0}p{font-size:14px;line-height:2.05;margin:0 0 7mm}footer{position:absolute;bottom:15mm;font-size:10px;color:#a5b5cb}@media print{body{background:#0b1120;print-color-adjust:exact;-webkit-print-color-adjust:exact}.page{margin:0;height:297mm;overflow:hidden}}</style>'''+"".join(pages)+"</html>"
    output = ROOT / "policies" / "store_policy_12pages.html"
    output.write_text(html, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
