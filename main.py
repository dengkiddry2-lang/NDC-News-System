import pdfplumber
import os

def run_v1_pipeline():
    if not os.path.exists('data'): os.makedirs('data')
    pdf_files = [f for f in os.listdir('data') if f.endswith('.pdf')]
    if not pdf_files: return
    
    latest_pdf = os.path.join('data', pdf_files[-1])
    news_list = []
    try:
        with pdfplumber.open(latest_pdf) as pdf:
            for page in pdf.pages[:3]:
                table = page.extract_table()
                if table:
                    for row in table:
                        if not row or len(row) < 2 or not row[1]: continue
                        title = str(row[1]).replace('\n', '').strip()
                        source = str(row[2]).replace('\n', ' ').strip() if len(row) > 2 else ""
                        if "新聞議題" in title or title == "None": continue
                        news_list.append({"title": title, "source": source})
    except: pass

    # 生成結果網頁
    content = "".join([f'<div style="border-left:5px solid #2b6cb0; background:white; padding:15px; margin:10px 0; border-radius:5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"><b>{n["title"]}</b><br><small>{n["source"]}</small></div>' for n in news_list])
    html = f'<html><body style="font-family:sans-serif; background:#f4f7f6; padding:40px;"><h1 style="color:#1a365d;">📊 經濟規劃科新聞預警 (v1)</h1>{content}</body></html>'
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_v1_pipeline()
