import pdfplumber
import os

def run_v1_pipeline():
    # 確保資料夾存在
    if not os.path.exists('data'):
        os.makedirs('data')
        
    # 找 PDF 檔案
    pdf_files = [f for f in os.listdir('data') if f.endswith('.pdf')]
    if not pdf_files:
        print("資料夾內沒看到 PDF，請上傳檔案到 data/ 目錄下")
        return
    
    latest_pdf = os.path.join('data', pdf_files[-1])
    news_list = []

    try:
        with pdfplumber.open(latest_pdf) as pdf:
            # 讀取前 3 頁目錄
            for page in pdf.pages[:3]:
                table = page.extract_table()
                if table:
                    for row in table:
                        if not row or len(row) < 2 or not row[1]: continue
                        
                        title = str(row[1]).replace('\n', '').strip()
                        source = str(row[2]).replace('\n', ' ').strip() if len(row) > 2 else "媒體未知"
                        
                        if "新聞議題" in title or title == "None" or not title: continue
                        
                        # 簡單分類
                        cat = "重點新聞"
                        if "頭版" in title: cat = "🔥 頭版要聞"
                        if "國發會" in title or "本會" in title: cat = "🏛️ 本會相關"
                        
                        news_list.append({"title": title, "source": source, "cat": cat})
    except Exception as e:
        print(f"解析發生錯誤，但我們會嘗試繼續: {e}")

    # 就算解析失敗，也產出一個基礎網頁，不要讓 Actions 報錯
    generate_html(news_list)

def generate_html(news_list):
    content_html = ""
    if not news_list:
        content_html = "<p>尚未抓取到新聞資料，請檢查 PDF 格式或上傳正確檔案。</p>"
    else:
        for n in news_list:
            content_html += f'<div style="border-left:5px solid #2b6cb0; background:white; padding:15px; margin:10px 0; border-radius:5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);"><b>[{n["cat"]}]</b> {n["title"]} <br><small style="color:#666">{n["source"]}</small></div>'

    html_template = f"""
    <html>
    <head><meta charset="UTF-8"><style>body {{ font-family: sans-serif; margin: 40px; background: #f4f7f6; }}</style></head>
    <body contenteditable="true">
        <div style="background: #1a365d; color: white; padding: 20px; border-radius: 8px;"><h1>📊 經濟規劃科：新聞訊號預警 (v1)</h1></div>
        {content_html}
        <div style="font-size: 12px; color: #666; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px;">
            【資料限制說明】本報告為輔助判讀工具，相關資訊需以正式資料複核。
        </div>
    </body></html>
    """
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_template)

if __name__ == "__main__":
    run_v1_pipeline()
