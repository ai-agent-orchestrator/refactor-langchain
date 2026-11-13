"""ReportLab로 한글 다크모드 학습 PDF를 만든다. diagram PNG 렌더 후 실행한다."""
import json
from pathlib import Path
import textwrap
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor, Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.utils import ImageReader

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "study"
OUTPUT = ROOT / "output" / "pdf" / "LANGCHAIN_REFACTOR_STUDY_DARK.pdf"
W, H = 960, 640
BG = HexColor("#0b1120")
CARD = HexColor("#101b2e")
INK = HexColor("#e5edf8")
MUTED = HexColor("#a5b5cb")
ACCENT = HexColor("#67decc")
BLUE = HexColor("#85bfff")
LINE = HexColor("#293d57")


def para(c, text, x, top, width, size=11.2, leading=18, color=INK, bold=False):
    style = ParagraphStyle("body", fontName="KoreanBold" if bold else "Korean", fontSize=size,
                           leading=leading, textColor=color, wordWrap="CJK", splitLongWords=True)
    p = Paragraph(escape(text).replace("\n", "<br/>"), style)
    _, height = p.wrap(width, H)
    p.drawOn(c, x, top-height)
    return top-height


def codebox(c, code, x, top, width):
    wrapped=[]
    # 폰트 폭으로 긴 코드 줄을 나눠 한국어·영문 모두 잘리지 않게 한다.
    for line in code.splitlines():
        current=""
        for char in line:
            if pdfmetrics.stringWidth(current+char, "Korean", 9.2) > width-28:
                wrapped.append(current)
                current="    "+char
            else:
                current+=char
        wrapped.append(current)
    height=38+len(wrapped)*14
    c.setFillColor(HexColor("#07111e"))
    c.setStrokeColor(LINE)
    c.roundRect(x, top-height, width, height, 8, stroke=1, fill=1)
    c.setFillColor(ACCENT)
    c.setFont("Korean", 9.2)
    c.setFillColor(MUTED);c.setFont("Korean",7.8)
    c.drawString(x+14,top-15,"설명용 발췌·축약 코드 / 실제 함수는 페이지 하단 참조")
    c.setFillColor(ACCENT);c.setFont("Korean",9.2)
    y=top-32
    for line in wrapped:
        c.drawString(x+14,y,line)
        y-=14
    return top-height


def source_label(location):
    path, _, symbol = location.partition(":")
    actual=ROOT/path
    if actual.is_file() and symbol:
        for n,line in enumerate(actual.read_text(encoding="utf-8").splitlines(),1):
            if f"def {symbol}(" in line or f"class {symbol}(" in line:
                return f"{path}:{n} / {symbol}"
    return location


def draw_page(c, page, number, total, data):
    c.setFillColor(BG);c.rect(0,0,W,H,stroke=0,fill=1)
    c.setTitle("수업이 우리 개발에 반영된 방식 - LangChain / LangGraph")
    c.setAuthor("Codex · project study notes")
    c.setFont("KoreanBold",10);c.setFillColor(ACCENT)
    c.drawString(32,607,"LANGCHAIN / LANGGRAPH   ·   DEVELOPMENT ANNOTATIONS")
    c.setFont("Korean",9);c.setFillColor(MUTED)
    c.drawRightString(W-32,607,page["status"])
    y=para(c,page["title"],32,581,W-64,size=24,leading=31,bold=True)
    y=para(c,page["subtitle"],32,y-8,W-64,size=11,leading=17,color=MUTED)
    content_top=min(500,y-20)
    if not page["diagram"]:
        x=44;top=content_top;width=W-88
        for title,body in page["sections"]:
            top=para(c,title,x,top,width,size=12.1,leading=17,color=ACCENT,bold=True)
            before=top
            top=para(c,body,x,top-4,width,size=10.8,leading=16)
            # 참고 페이지의 각 항목은 실제 수업 노트북 링크로 연결한다.
            candidates={"05":"05_embedding.ipynb","06":"06_vectorstore_and_retriever.ipynb","07":"07_rag_chain.ipynb", "10":"10_langgraph_basics.ipynb","11":"11_langgraph_agent.ipynb","12":"12_rag_graph.ipynb","13":"13_memory.ipynb"}
            name=candidates.get(title[:2])
            if name:c.linkURL(data["lecture_base"]+"complete/"+name,(x,top,width+x,before+18),relative=0,thickness=0)
            top-=15
        if top<65:raise ValueError(f"Reference page overflow: {top}")
    else:
        left_x=32;left_w=438;right_x=494;right_w=434;bottom=88
        c.setFillColor(CARD);c.setStrokeColor(LINE)
        c.roundRect(left_x,bottom,left_w,content_top-bottom,12,stroke=1,fill=1)
        c.setFillColor(ACCENT);c.setFont("KoreanBold",10)
        c.drawString(left_x+18,content_top-25,"FLOW  /  흐름을 먼저 읽으세요")
        img=ImageReader(str(DATA/"assets"/(page["diagram"]+".png")))
        iw,ih=img.getSize()
        available_w=left_w-26;available_h=content_top-bottom-70
        scale=min(available_w/iw,available_h/ih)
        dw,dh=iw*scale,ih*scale
        c.drawImage(img,left_x+(left_w-dw)/2,bottom+24+(available_h-dh)/2,dw,dh,mask="auto")
        top=content_top
        for title,body in page["sections"]:
            top=para(c,title,right_x,top,right_w,size=12.3,leading=18,color=ACCENT,bold=True)
            top=para(c,body,right_x,top-5,right_w,size=11,leading=17)-13
        if page["code"]:
            top=codebox(c,page["code"],right_x,top+2,right_w)
        if top<76:raise ValueError(f"Page {number} overflow: {top}; {page['title']}")
    c.setStrokeColor(LINE);c.line(32,68,W-32,68)
    ours=source_label(page["ours"])
    para(c,"우리 코드  "+ours,32,56,W-100,size=8.3,leading=12,color=MUTED)
    if page["lecture"]:
        label="수업 원본  "+page["lecture"]+"  ·  fa65250 (클릭)"
        para(c,label,32,40,W-100,size=8.2,leading=11,color=BLUE)
        c.linkURL(data["lecture_base"]+page["lecture"],(32,27,W-125,42),relative=0,thickness=0)
    c.setFont("Korean",9);c.setFillColor(MUTED)
    c.drawRightString(W-32,38,f"{number:02d} / {total:02d}")
    c.bookmarkPage(f"page-{number}")
    c.addOutlineEntry(page["title"],f"page-{number}",0,False)
    c.showPage()


def main():
    pdfmetrics.registerFont(TTFont("Korean","C:/Windows/Fonts/malgun.ttf"))
    pdfmetrics.registerFont(TTFont("KoreanBold","C:/Windows/Fonts/malgunbd.ttf"))
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    data=json.loads((DATA/"study_content.json").read_text(encoding="utf-8"))
    c=canvas.Canvas(str(OUTPUT),pagesize=(W,H),pageCompression=1)
    c.setSubject("수업 05·06·07·10·11·12·13과 리뷰 API 개발의 연결. 실제 Mermaid 렌더 그림 포함.")
    for n,page in enumerate(data["pages"],1):draw_page(c,page,n,len(data["pages"]),data)
    c.save()
    print(f"PDF: {OUTPUT} ({len(data['pages'])} pages)")


if __name__=="__main__":main()
