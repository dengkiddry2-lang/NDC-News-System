import pdfplumber
import os

# 專業判讀邏輯：針對 1150427 資料的關鍵字大腦
RULES = {
    "AI": {"cat": "投資 (I)", "note": "關注半導體與 AI 鏈資本支出動能", "color": "#2b6cb0"},
    "資本支出": {"cat": "投資 (I)", "note": "民間投資預測之重要先行指標", "color": "#2b6cb0"},
    "出口": {"cat": "出口 (X)", "note": "外需動能觀測，影響 Q3 經濟增長", "color": "#38a169"},
    "離岸風電": {"cat": "政府投資 (G)", "note": "能源轉型進度與長期電價壓力", "color": "#805ad5"},
    "川普": {"cat": "風險 (Risk)", "note": "地緣政治變數，需注意關稅與能源政策", "color": "#e53e3e"},
    "國發會": {"cat": "本會相關", "note": "本會重要政策推動與對外說明", "color": "#2d3748"}
}

def run_pro_v2():
    pdf_files = [f for f in os.listdir('data') if f.endswith('.pdf')]
    if not pdf_files: return
    latest_pdf = os.path.join('data', pdf_files[-1])
    news_data = []

    with pdfplumber.open(latest_pdf) as pdf:
        for page in pdf.pages[:3]:
            table = page.extract_table()
            if not table: continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]: continue
                title = str(row[1]).replace('\n', '')
                source = str(row[2]).replace('\n', ' ') if len(row) > 2 else ""
                
                # 預設判讀
                analysis = {"cat": "一般財經", "note": "日常經貿動態觀測", "color": "#718096", "is_high": False}
                for key, val in RULES.items():
                    if key in title:
                        analysis = {**val, "is_high": (val['cat'] in ['投資 (I)', '風險 (Risk)'])}
                        break
                news_data.append({"title": title, "source": source, **analysis})

    generate_pro_html(news_data)

def generate_pro_html(data):
    # CSS 設計感設定
    style = """
    <style>
        body { font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif; background: #f0f4f8; color: #2d3748; padding: 40px; }
        .container { max-width: 900px; margin: auto; }
        .header { background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%); color: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); margin-bottom: 30px; }
        .card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 12px; border-left: 6px solid #cbd5e0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: transform 0.2s; }
        .card:hover { transform: translateY(-3px); }
        .tag { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; color: white; margin-bottom: 10px; }
        .note { background: #ebf8ff; padding: 10px; border-radius: 6px; font-size: 14px; color: #2c5282; margin: 10px 0; border: 1px solid #bee3f8; }
        .high-risk { border-left-color: #e53e3e; background: #fff5f5; }
        .footer { text-align: center; color: #a0aec0; font-size: 12px; margin-top: 50px; }
    </style>
    """
    
    cards_html = ""
    for d in data:
        risk_class = "high-risk" if d.get('is_high') else ""
        cards_html += f"""
        <div class="card {risk_class}">
            <div class="tag" style="background:{d['color']}">{d['cat']}</div>
            <h3 style="margin:0 0 10px 0; font-size:18px;">{d['title']}</h3>
            <div class="note"><b>💡 規劃科判讀：</b>{d['note']}</div>
            <div style="font-size:12px; color:#718096;">來源：{d['source']}</div>
        </div>
        """

    html = f"""
    <html><head><meta charset="UTF-8">{style}</head>
    <body contenteditable="true">
        <div class="container">
            <div class="header">
                <div style="font-size:14px; opacity:0.8;">1150427 國家發展委員會</div>
                <h1 style="margin:5px 0 0 0;">經濟規劃科：新聞訊號預警儀表板</h1>
            </div>
            {cards_html}
            <div class="footer">本報表為自動化決策輔助工具，內容僅供內部研究參考</div>
        </div>
    </body></html>
    """
    with open("index.html", "w", encoding="utf-8") as f: f.write(html)

if __name__ == "__main__": run_pro_v2()
