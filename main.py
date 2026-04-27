import pdfplumber
import os
import html

DEPARTMENTS = {
    "🔥 風險預警": ["美伊", "伊朗", "戰爭", "川普", "選情", "槍響", "Fed", "央行"],
    "🌏 總體經濟": ["出口", "進口", "物價", "通膨", "匯率", "GDP", "景氣", "主計"],
    "💻 產業投資": ["AI", "資本支出", "台積電", "半導體", "伺服器", "CoWoS", "設備"],
    "🏛️ 政策/本會": ["國發會", "政策", "離岸風電", "淨零", "電力", "算力"]
}

def get_summary(title, category):
    summaries = {
        "🔥 風險預警": "連動避險情緒，需觀察油價及下半年通膨路徑。",
        "🌏 總體經濟": "觀測外需動能，為年度經濟成長率之關鍵指標。",
        "💻 產業投資": "民間投資先行指標，決定 Q3 投資達成率。",
        "🏛️ 政策/本會": "涉及政策推動，注意中長期發展之引導效益。"
    }
    return summaries.get(category, "經貿動態觀測。")

def run_dashboard_pipeline():
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files: return
    latest_pdf = os.path.join("data", sorted(pdf_files)[-1])

    organized_data = {cat: [] for cat in DEPARTMENTS.keys()}
    organized_data["📝 其他"] = []

    with pdfplumber.open(latest_pdf) as pdf:
        for page in pdf.pages[:5]:
            table = page.extract_table()
            if not table: continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]: continue
                title = str(row[1]).replace("\n", "").strip()
                source = str(row[2]).replace("\n", " ").strip() if len(row) > 2 else ""
                if len(title) < 5 or "新聞議題" in title: continue

                found_cat = "📝 其他"
                for cat, keywords in DEPARTMENTS.items():
                    if any(k in title for k in keywords):
                        found_cat = cat
                        break
                organized_data[found_cat].append({"title": title, "source": source, "summary": get_summary(title, found_cat)})

    generate_dashboard_html(organized_data)

def generate_dashboard_html(data):
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'PingFang TC', sans-serif; background: #020617; color: #f8fafc; margin: 0; padding: 20px; overflow-x: hidden; }}
        .dashboard {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; height: 90vh; }}
        .header {{ grid-column: span 4; display: flex; justify-content: space-between; align-items: center; padding: 10px 20px; background: #1e293b; border-radius: 10px; margin-bottom: 10px; border: 1px solid #334155; }}
        .column {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; display: flex; flex-direction: column; overflow: hidden; }}
        .col-header {{ background: #1e3a8a; padding: 10px; font-weight: bold; text-align: center; font-size: 16px; border-bottom: 2px solid #38bdf8; }}
        .news-list {{ overflow-y: auto; flex-grow: 1; padding: 10px; }}
        .news-card {{ background: #1e293b; padding: 10px; margin-bottom: 10px; border-radius: 6px; font-size: 13px; cursor: pointer; border-left: 4px solid #334155; }}
        .news-card:hover {{ border-left-color: #38bdf8; background: #334155; }}
        .news-card b {{ display: block; margin-bottom: 5px; color: #38bdf8; }}
        .summary {{ font-size: 12px; color: #94a3b8; margin-top: 5px; display: none; background: #020617; padding: 5px; border-radius: 4px; }}
        .source {{ float: right; font-size: 10px; color: #64748b; }}
        ::-webkit-scrollbar {{ width: 5px; }}
        ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 10px; }}
    </style>
    <script>
        function toggle(e) {{
            const s = e.querySelector('.summary');
            s.style.display = s.style.display === 'block' ? 'none' : 'block';
        }}
    </script>
</head>
<body>
    <div class="header">
        <h2 style="margin:0;">📊 經濟規劃科戰情室 <small style="font-size:12px; color:#94a3b8;">(1150427 訊號監控)</small></h2>
        <div style="font-size:14px; color:#38bdf8;">狀態：即時更新中</div>
    </div>
    <div class="dashboard">
"""
    for cat, list_data in data.items():
        if cat == "📝 其他": continue
        html_content += f"""
        <div class="column">
            <div class="col-header">{cat} ({len(list_data)})</div>
            <div class="news-list">
        """
        for item in list_data:
            html_content += f"""
                <div class="news-card" onclick="toggle(this)">
                    <span class="source">{item['source']}</span>
                    <b>{item['title']}</b>
                    <div class="summary">💡 判讀：{item['summary']}</div>
                </div>
            """
        html_content += "</div></div>"

    html_content += """</div></body></html>"""
    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__": run_dashboard_pipeline()
