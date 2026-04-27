import pdfplumber
import os
import html

# 1. 定義分類與智慧關鍵字
DEPARTMENTS = {
    "⚠️ 風險監控 (Risk)": ["美伊", "伊朗", "戰爭", "川普", "選情", "槍響", "Fed", "利率", "衝突"],
    "📊 總體數據 (Macro)": ["出口", "進口", "物價", "通膨", "匯率", "GDP", "主計", "景氣", "成長"],
    "⚙️ 產業動能 (I)": ["AI", "資本支出", "台積電", "半導體", "伺服器", "CoWoS", "設備", "製程"],
    "🏢 政策規畫 (G)": ["國發會", "政策", "計畫", "電力", "預算", "離岸風電", "算力", "淨零"]
}

def get_industrial_analysis(title, cat):
    """工業風專業判讀摘要"""
    if any(k in title for k in ["資本支出", "AI", "設備"]):
        return "🛠️ [生產力映射] AI 供應鏈擴產動能強勁。影響指標：民間投資 (I) 權重調升。"
    if any(k in title for k in ["出口", "訂單"]):
        return "📦 [物流映射] 外需動能回穩。影響指標：淨出口 (X-M) 貢獻度增加。"
    if any(k in title for k in ["通膨", "油價", "央行"]):
        return "⚖️ [成本監控] 供給端壓力仍存。影響指標：CPI 通膨路徑需重新校準。"
    if any(k in title for k in ["川普", "戰爭"]):
        return "🚨 [系統性風險] 地緣政治變數。影響指標：調高不確定性溢價權重。"
    
    return "📝 [一般監測] 經濟訊號穩定，建議維持現行預測模型參數。"

def run_industrial_dashboard():
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files: return
    latest_pdf = os.path.join("data", sorted(pdf_files)[-1])

    # 主題歸併字典
    organized_data = {cat: {} for cat in DEPARTMENTS.keys()}
    organized_data["📂 其他資訊"] = {}

    with pdfplumber.open(latest_pdf) as pdf:
        for page in pdf.pages[:5]:
            table = page.extract_table()
            if not table: continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]: continue
                title = str(row[1]).replace("\n", "").strip()
                source = str(row[2]).replace("\n", " ").strip() if len(row) > 2 else "未知"
                if len(title) < 5 or "新聞議題" in title: continue

                # 分類
                found_cat = "📂 其他資訊"
                for cat, keywords in DEPARTMENTS.items():
                    if any(k in title for k in keywords):
                        found_cat = cat
                        break
                
                # 主題歸併 (取標題前 7 個字)
                theme_key = title[:7]
                if theme_key not in organized_data[found_cat]:
                    organized_data[found_cat][theme_key] = {
                        "main_title": title,
                        "sources": [source],
                        "analysis": get_industrial_analysis(title, found_cat)
                    }
                else:
                    if source not in organized_data[found_cat][theme_key]["sources"]:
                        organized_data[found_cat][theme_key]["sources"].append(source)

    generate_industrial_html(organized_data)

def generate_industrial_html(data):
    html_content = f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <style>
        :root {{
            --bg-metal: #1a1a1a;
            --panel-bg: #262626;
            --accent-yellow: #f59e0b;
            --accent-orange: #ea580c;
            --border-gray: #404040;
            --text-light: #e5e5e5;
            --text-dim: #a3a3a3;
        }}
        body {{
            background-color: var(--bg-metal);
            background-image: radial-gradient(#333 1px, transparent 1px);
            background-size: 20px 20px; /* 工業風格網格背景 */
            color: var(--text-light);
            font-family: 'Consolas', 'Microsoft JhengHei', monospace;
            margin: 0; padding: 15px; overflow: hidden;
        }}
        .header {{
            display: flex; justify-content: space-between; align-items: center;
            border: 2px solid var(--border-gray);
            background: #111; padding: 10px 25px; margin-bottom: 15px;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.5);
        }}
        .header h1 {{ margin: 0; font-size: 24px; color: var(--accent-yellow); letter-spacing: 2px; }}
        
        .dashboard {{
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; height: 82vh;
        }}
        .column {{
            background: var(--panel-bg);
            border: 1px solid var(--border-gray);
            display: flex; flex-direction: column;
            position: relative;
        }}
        .column::before {{ /* 工業螺栓裝飾 */
            content: '●'; position: absolute; top: 5px; right: 5px; color: #444; font-size: 10px;
        }}
        .col-header {{
            background: #333; padding: 12px; font-weight: bold; text-align: center;
            border-bottom: 3px solid var(--accent-yellow); color: var(--accent-yellow);
            text-transform: uppercase; letter-spacing: 1px;
        }}
        .news-list {{ overflow-y: auto; flex-grow: 1; padding: 10px; }}
        
        .news-card {{
            background: #1a1a1a; border: 1px solid var(--border-gray);
            padding: 12px; margin-bottom: 12px; border-left: 5px solid #555;
            transition: 0.2s;
        }}
        .news-card:hover {{ border-left-color: var(--accent-orange); background: #222; }}
        
        .news-title {{ font-size: 14px; font-weight: bold; line-height: 1.5; margin-bottom: 8px; color: #fff; }}
        
        .analysis {{
            background: #111; padding: 10px; border: 1px dashed #444;
            font-size: 12px; color: var(--accent-yellow); outline: none; margin-top: 8px;
        }}
        .source-container {{ display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }}
        .source-tag {{
            font-size: 10px; color: var(--text-dim); background: #000;
            padding: 2px 6px; border: 1px solid #333;
        }}
        .status-dot {{ display: inline-block; width: 8px; height: 8px; background: var(--accent-orange); border-radius: 50%; margin-right: 8px; animation: blink 2s infinite; }}
        @keyframes blink {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} 100% {{ opacity: 1; }} }}
        
        ::-webkit-scrollbar {{ width: 6px; }}
        ::-webkit-scrollbar-track {{ background: #111; }}
        ::-webkit-scrollbar-thumb {{ background: #444; }}
    </style>
</head>
<body>
    <div class="header">
        <h1><span class="status-dot"></span>NDCP : NEWS INTELLIGENCE SYSTEM</h1>
        <div style="font-size: 12px; color: var(--text-dim);">SYSTEM_DATE: 1150427 // DEPT: ECONOMIC_PLANNING</div>
    </div>
    <div class="dashboard">
"""
    for cat, items in data.items():
        if cat == "📂 其他資訊": continue
        html_content += f"""
        <div class="column">
            <div class="col-header">{cat} [{len(items)}]</div>
            <div class="news-list">
        """
        for key, info in items.items():
            sources_html = "".join([f'<span class="source-tag">{s}</span>' for s in info['sources']])
            html_content += f"""
                <div class="news-card">
                    <div class="news-title">{info['main_title']}</div>
                    <div class="source-container">{sources_html}</div>
                    <div class="analysis" contenteditable="true">{info['analysis']}</div>
                </div>
            """
        html_content += "</div></div>"

    html_content += """</div>
    <div style="text-align: right; font-size: 10px; color: #444; margin-top: 10px;">INDUSTRIAL MONITORING INTERFACE v4.0 // END_OF_LINE</div>
</body></html>"""
    with open("index.html", "w", encoding="utf-8") as f: f.write(html_content)

if __name__ == "__main__": run_industrial_dashboard()
