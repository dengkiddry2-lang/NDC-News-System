import pdfplumber
import os
import json
import re

# ── 1. 分類定義（修正版）──────────────────────────────────────────────
# 核心原則：
#   - 不用「美國/中國/日本」等國名當關鍵字（幾乎每篇都有）
#   - 地緣政治獨立一類，不混入金融情勢
#   - 台積/聯電等縮寫補進產業類
#   - 政府政策類補強機構名

DEPARTMENTS = {
    "社論與評論觀點": {
        "icon": "📝",
        "keywords": ["社論", "時評", "社評", "專欄", "論壇", "觀點", "評論", "名家", "經濟教室", "縱橫天下", "自由廣場"]
    },
    "國際機構與智庫報告": {
        "icon": "📘",
        "keywords": ["IMF", "OECD", "World Bank", "WTO", "智庫", "Brookings", "PIIE", "BIS", "ADB", "WEF", "聯合國", "世界銀行", "國際貨幣"]
    },
    "地緣政治與國際衝突": {
        "icon": "🌏",
        "keywords": [
            "戰爭", "衝突", "制裁", "美伊", "俄烏", "荷莫茲", "伊朗", "烏克蘭",
            "關稅", "川普", "貿易戰", "地緣", "槍響", "槍擊", "遇襲", "外交"
        ]
    },
    "國際金融與貨幣政策": {
        "icon": "🌐",
        "keywords": [
            "Fed", "FOMC", "聯準會", "利率決策", "升息", "降息", "鮑爾",
            "ECB", "BOJ", "英格蘭銀行", "央行週", "超級央行",
            "美債", "美元指數", "非農", "CPI", "核心通膨", "PMI", "ISM",
            "人民幣", "日圓", "歐元", "英鎊", "匯率"
        ]
    },
    "台灣總體經濟與數據": {
        "icon": "📊",
        "keywords": [
            "主計", "主計總處", "GDP", "景氣燈號", "景氣", "物價", "通膨",
            "失業率", "薪資", "外銷訂單", "出口統計", "進口統計", "海關",
            "貿易統計", "稅收", "超徵", "出生率", "少子化", "高齡化", "人口統計",
            "消費者信心", "製造業PMI", "非製造業"
        ]
    },
    "台灣產業與投資動向": {
        "icon": "🏭",
        "keywords": [
            "AI", "半導體", "台積電", "台積", "聯發科", "聯電", "鴻海",
            "台達電", "廣達", "緯創", "英業達", "資本支出", "供應鏈",
            "算力", "伺服器", "CoWoS", "先進封裝", "製程", "晶片",
            "離岸風電", "綠能", "電動車", "ASIC", "TPU", "GPU"
        ]
    },
    "台灣政府與政策訊息": {
        "icon": "🏛️",
        "keywords": [
            "國發會", "行政院", "總統府", "經濟部", "財政部", "金管會",
            "國科會", "央行", "衛福部", "內政部", "院會", "政院",
            "法案", "預算", "補助", "政策", "施政", "法規", "條例",
            "立法院", "立委", "修法"
        ]
    },
}

CATEGORY_ORDER = [
    "社論與評論觀點",
    "國際機構與智庫報告",
    "地緣政治與國際衝突",
    "國際金融與貨幣政策",
    "台灣總體經濟與數據",
    "台灣政府與政策訊息",
    "台灣產業與投資動向",
]

MUST_READ_KEYS = [
    "Fed", "FOMC", "鮑爾", "主計", "GDP", "景氣燈號",
    "衝突", "戰爭", "利率決議", "升息", "降息",
    "外銷訂單", "超徵", "荷莫茲"
]

# 非經濟版面關鍵字：這些版面的新聞若標題無任何經濟關鍵字，直接略過
NON_ECON_SECTIONS = [
    "焦點新聞", "社會", "地方", "體育", "娛樂", "影視",
    "生活", "健康", "農業", "司法", "法庭",
    "影劇", "副刊", "旅遊", "美食", "寵物", "星座"
]

# 標題有這些詞 → 判定為非經濟，直接略過
NON_ECON_TITLE_KEYS = [
    # 社會犯罪類
    "大麻", "毒品", "詐騙", "竊盜", "槍擊案",
    # 農漁牧類
    "農業", "旱情", "廚餘", "豬", "漁業", "農委會",
    # 醫療社福類
    "失智", "長照", "安樂死", "安寧", "防癌",
    # 娛樂生活類
    "觀光旅遊", "演唱會", "婚喪喜慶",
    # 房產（非投資面）
    "房價指數", "租屋",
]

# 所有分類的經濟關鍵字合集（用於判斷非經濟版面的新聞是否值得保留）
ALL_ECON_KEYS = set()
for dept in DEPARTMENTS.values():
    ALL_ECON_KEYS.update(dept["keywords"])
ALL_ECON_KEYS.update(MUST_READ_KEYS)


# ── 2. 過濾非經濟新聞 ──────────────────────────────────────────────

def should_skip(title, source):
    """判斷這則新聞是否應略過（非經濟情報相關）"""
    # 標題有明確非經濟詞彙
    if any(k in title for k in NON_ECON_TITLE_KEYS):
        return True
    # 非經濟版面 + 標題無任何經濟關鍵字
    if any(sec in source for sec in NON_ECON_SECTIONS):
        if not any(k in title for k in ALL_ECON_KEYS):
            return True
    return False


# ── 3. 文本解析邏輯 ────────────────────────────────────────────────────

def is_noise_line(line):
    noise = ["回到目錄", "來源:", "來源：", "版面", "作者", "日期", "頁次", "新聞議題", "報導媒體"]
    if line.isdigit():
        return True
    return any(k in line for k in noise)

def clean_text_blocks(text_list):
    """
    清洗 PDF 擷取文字並重組段落。
    策略：
    1. 過濾雜訊行
    2. 把 PDF 欄位換行造成的碎行合併回完整句子
    3. 每 2~4 句切一段，輸出 \n\n 分隔的段落
    """
    if not text_list:
        return ""

    # Step 1: 過濾雜訊，合併碎行
    merged = ""
    for line in text_list:
        line = line.strip()
        if not line or is_noise_line(line):
            continue
        # 作者行殘留模式（不應進入正文）
        if re.search(r'報導】$|記者.{0,10}報導', line):
            continue
        # 純數字行（頁碼）
        if line.isdigit():
            continue
        if not merged:
            merged = line
        elif merged[-1] in ("。", "！", "？", "；", "」", "\u201d", "…"):
            # 前一行句子完整，新開一行
            merged += "\n" + line
        else:
            # 前一行句子不完整（PDF 欄位斷行），直接接上
            merged += line

    # Step 2: 清除多餘空白
    merged = re.sub(r' +', ' ', merged)
    merged = merged.strip()

    # Step 3: 按句號切句，每 3 句一段
    sentences = re.split(r'(?<=[。！？；])', merged)
    paragraphs = []
    current = ""
    count = 0
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        current += s
        count += 1
        if count >= 3 and s[-1] in ("。", "！", "？", "；"):
            paragraphs.append(current.strip())
            current = ""
            count = 0
    if current.strip():
        paragraphs.append(current.strip())

    # 清除段落內的 PDF 欄位殘留空格和換行
    import re as _re
    cleaned = []
    for p in paragraphs:
        # 單個換行 → 空格（PDF 欄位斷行）
        p = p.replace("\n", " ")
        # 多餘空格合併
        p = _re.sub(r" {2,}", " ", p)
        # 標點前的空格去除 + 中文字間的 PDF 欄位空格去除
        p = _re.sub(r" ([，。！？；：、「」』」）】])", r"\1", p)
        p = _re.sub(r"([一-鿿＀-￯]) ([一-鿿＀-￯（「『「])", r"\1\2", p)
        p = p.strip()
        if p:
            cleaned.append(p)
    return "\n\n".join(cleaned)

def find_article(article_index, title):
    key = title.replace(" ", "")
    best_content = ""
    best_score = 0
    for art_key, content in article_index.items():
        for n in [14, 12, 10, 8, 6]:
            if key[:n] and key[:n] in art_key:
                if n > best_score:
                    best_score = n
                    best_content = content
                break
    return best_content if best_score >= 6 else ""

def extract_summary(content, limit=220):
    if not content:
        return "尚未擷取到內文摘要"
    parts = [p.strip() for p in content.split("\n\n") if p.strip()]
    if parts:
        return parts[0][:limit] + ("..." if len(parts[0]) > limit else "")
    return content[:limit] + ("..." if len(content) > limit else "")

def build_article_index(pdf):
    index = {}
    last_key = None
    raw_content_map = {}
    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines:
            continue
        has_source = any(l.startswith("來源:") or l.startswith("來源：") for l in lines[:8])
        if has_source:
            src_idx = next(
                i for i, l in enumerate(lines)
                if l.startswith("來源:") or l.startswith("來源：")
            )
            title_key = "".join(lines[:src_idx]).replace(" ", "")
            # 跳過來源行及其可能的跨行殘留（作者行尾段）
            body_start = src_idx + 1
            while body_start < len(lines):
                line = lines[body_start]
                # 作者行尾段特徵：以「報導】」「報導】。」「記者報導】」結尾
                # 或以「／台北報導】」「／綜合報導】」等形式出現
                if re.search(r'[報導綜合外電]+】\s*$|^\w+\/\w+報導】', line):
                    body_start += 1
                elif re.match(r'^[　\s]*【.{0,20}報導】', line):
                    body_start += 1
                else:
                    break
            raw_content_map[title_key] = lines[body_start:]
            last_key = title_key
        elif (
            last_key
            and len("".join(lines)) > 50
            and not page.extract_table()
            and not any("回到目錄" in l for l in lines[:5])
        ):
            if last_key in raw_content_map:
                raw_content_map[last_key].extend(lines)
        else:
            last_key = None
    for key, text_list in raw_content_map.items():
        index[key] = clean_text_blocks(text_list)
    return index




# ── 4. 執行解析 ──────────────────────────────────────────────────────

def run_dashboard():
    data_folder = "data"
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
    pdf_files = [f for f in os.listdir(data_folder) if f.lower().endswith(".pdf")]

    all_items = []
    skipped = 0
    if pdf_files:
        pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join(data_folder, x)))
        latest_pdf = os.path.join(data_folder, pdf_files[-1])
        print(f"處理檔案: {latest_pdf}")

        with pdfplumber.open(latest_pdf) as pdf:
            article_index = build_article_index(pdf)
            # 掃描所有有表格的頁面，動態判斷是否為目錄
            for page in pdf.pages:
                table = page.extract_table()
                if not table:
                    continue
                # 判斷是否為目錄表格：
                # 策略：掃描所有列，只要有一列符合「第2欄是標題、第3欄含報名」就是目錄
                def is_toc_table(t):
                    news_sources = ['時報', '日報', '聯合', '自由', '中時', '工商', '蘋果', '鏡', '報']
                    for r in t:
                        if not r or len(r) < 2: continue
                        col2 = str(r[1] or '').strip()
                        col3 = str(r[2] or '').strip() if len(r) > 2 else ''
                        if len(col2) > 5 and any(s in col3 for s in news_sources):
                            return True
                    return False
                if not is_toc_table(table):
                    continue
                for row in table[1:]:
                    if not row or len(row) < 2 or not row[1]:
                        continue
                    title = str(row[1]).replace("\n", "").strip()
                    source = str(row[2]).replace("\n", " ").strip() if len(row) > 2 and row[2] else "EPC彙整"
                    if len(title) < 5 or any(k in title for k in ["新聞議題", "報導媒體", "目錄", "頁次"]):
                        continue

                    # 過濾非經濟新聞
                    if should_skip(title, source):
                        skipped += 1
                        continue

                    classify_text = title + " " + source
                    found_cat = None
                    for cat in CATEGORY_ORDER:
                        if any(k in classify_text for k in DEPARTMENTS[cat]["keywords"]):
                            found_cat = cat
                            break
                    # 略過無法分類的（其他雜項不顯示）
                    if not found_cat:
                        skipped += 1
                        continue

                    content = find_article(article_index, title)
                    all_items.append({
                        "title": title,
                        "source": source,
                        "cat": found_cat,
                        "priority": 1 if any(k in title for k in MUST_READ_KEYS) else 0,
                        "summary": extract_summary(content),
                        "full_text": content
                    })

    print(f"保留 {len(all_items)} 則，略過 {skipped} 則非經濟新聞")
    generate_html(all_items)
    print("✅ 已產生 index.html")


# ── 5. HTML 生成 ──────────────────────────────────────────────

# 這個檔案定義 build_js 函數的內容，用來替換 main_v2.py 裡的版本

NEW_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --black: #000; --dark1: #1d1d1f; --dark2: #161617; --white: #fff; --offwhite: #fbfbfd; --silver: #f5f5f7;
  --border: rgba(255,255,255,0.1); --border-light: rgba(0,0,0,0.1);
  --txt-w: #f5f5f7; --txt-w2: #a1a1a6; --txt-w3: #6e6e73;
  --txt-b: #1d1d1f; --txt-b2: #6e6e73; --txt-b3: #86868b;
  --blue: #0071e3; --must: #ff3b30; --watch: #ff9500;
}
html { scroll-behavior: smooth; }
body { background: var(--black); color: var(--txt-w); font-family: -apple-system,'SF Pro Display','Helvetica Neue','Noto Sans TC',sans-serif; -webkit-font-smoothing: antialiased; overflow-x: hidden; }

/* ── GLOBAL NAV ── */
#gnav {
  height: 44px; background: rgba(0,0,0,0.88);
  backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 22px; position: sticky; top: 0; z-index: 900;
}
.gnav-logo { display: flex; align-items: center; gap: 8px; }
.gnav-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--blue); }
.gnav-name { font-size: 17px; font-weight: 500; color: var(--txt-w); letter-spacing: -0.01em; }
.gnav-date { font-size: 12px; color: var(--txt-w3); }

/* ── HOME: HERO (dark full-width) ── */
#home-view {}
.hero-block {
  background: var(--dark1); border-bottom: 1px solid var(--border);
  min-height: 460px; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 80px 24px 60px; text-align: center; position: relative; overflow: hidden;
}
.hero-eyebrow { font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--txt-w3); margin-bottom: 16px; }
.hero-headline { font-size: 64px; font-weight: 700; letter-spacing: -0.05em; line-height: 1.02; color: var(--txt-w); margin-bottom: 10px; }
.hero-sub { font-size: 19px; color: var(--txt-w2); font-weight: 400; margin-bottom: 40px; }
.hero-kpis { display: flex; justify-content: center; gap: 64px; padding-top: 40px; border-top: 1px solid var(--border); }
.kpi-val { font-size: 48px; font-weight: 700; letter-spacing: -0.04em; line-height: 1; }
.kpi-val.red { color: var(--must); }
.kpi-val.blue { color: var(--blue); }
.kpi-label { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--txt-w3); margin-top: 6px; }

/* ── HOME: SEGMENT BAR ── */
#seg-bar {
  background: var(--black); padding: 0 22px;
  display: flex; gap: 0; overflow-x: auto; scrollbar-width: none;
  border-bottom: 1px solid var(--border);
  position: sticky; top: 44px; z-index: 800;
}
#seg-bar::-webkit-scrollbar { display: none; }
.seg {
  padding: 12px 18px; font-size: 13px; font-weight: 500;
  color: var(--txt-w3); cursor: pointer; white-space: nowrap;
  border-bottom: 2px solid transparent; transition: all 0.2s;
  letter-spacing: -0.01em; flex-shrink: 0;
}
.seg:hover { color: var(--txt-w); }
.seg.active { color: var(--txt-w); border-bottom-color: var(--txt-w); }

/* ── HOME: BRICK GRID ── */
#brick-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2px;
  background: var(--border);
}
.brick {
  background: var(--dark1); min-height: 420px;
  padding: 48px 44px; display: flex; flex-direction: column;
  justify-content: flex-end; cursor: pointer; position: relative;
  overflow: hidden; transition: filter 0.3s;
}
.brick:hover { filter: brightness(1.06); }
.brick.dark { background: var(--dark2); }
.brick.light { background: var(--silver); color: var(--txt-b); }
.brick.full { grid-column: 1 / -1; min-height: 500px; justify-content: center; align-items: center; text-align: center; }
.brick.full.dark-hero {
  background: var(--dark2);
  background-image: radial-gradient(ellipse at 70% 40%, rgba(0,113,227,0.12) 0%, transparent 60%);
}

.brick-must-bar { position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--must); }
.brick-watch-bar { position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--watch); }

.brick-eyebrow {
  font-size: 11px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--blue);
  margin-bottom: 16px;
}
.brick.light .brick-eyebrow { color: var(--blue); }

.brick-title {
  font-size: 28px; font-weight: 700; letter-spacing: -0.03em;
  line-height: 1.15; color: var(--txt-w); margin-bottom: 10px;
}
.brick.light .brick-title { color: var(--txt-b); }
.brick.full .brick-title { font-size: 40px; max-width: 700px; }

.brick-summary {
  font-size: 15px; color: var(--txt-w2); line-height: 1.65;
  margin-bottom: 20px;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.brick.light .brick-summary { color: var(--txt-b2); }
.brick.full .brick-summary { font-size: 17px; max-width: 560px; -webkit-line-clamp: 2; }

.brick-cta {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 17px; font-weight: 400; color: var(--blue);
  letter-spacing: -0.01em; transition: gap 0.2s;
}
.brick:hover .brick-cta { gap: 8px; }
.brick.light .brick-cta { color: var(--blue); }

.brick-meta {
  font-size: 11px; color: var(--txt-w3); margin-top: 14px;
  display: flex; align-items: center; gap: 8px;
}
.brick.light .brick-meta { color: var(--txt-b3); }
.badge-must { background: var(--must); color: #fff; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 20px; letter-spacing: 0.05em; }
.badge-watch { background: var(--watch); color: #000; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 20px; letter-spacing: 0.05em; }

/* ── ARTICLE VIEW (全頁) ── */
#article-view {
  display: none; position: fixed; inset: 0; background: var(--white);
  z-index: 1000; overflow-y: auto; -webkit-overflow-scrolling: touch;
}

/* Article nav */
.article-nav {
  height: 44px; background: rgba(255,255,255,0.88);
  backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--border-light);
  display: flex; align-items: center; padding: 0 22px;
  position: sticky; top: 0; z-index: 100; gap: 12px;
}
.article-back {
  display: flex; align-items: center; gap: 4px;
  font-size: 17px; color: var(--blue); cursor: pointer;
  background: none; border: none; font-family: inherit; padding: 0;
  transition: opacity 0.2s;
}
.article-back:hover { opacity: 0.7; }
.article-nav-cat { font-size: 13px; color: var(--txt-b3); margin-left: auto; }

/* Article hero (白底大標) */
.article-hero {
  background: var(--white); padding: 80px 24px 56px; text-align: center;
  border-bottom: 1px solid var(--border-light);
}
.article-eyebrow {
  font-size: 12px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--blue); margin-bottom: 16px;
}
.article-headline {
  font-size: 48px; font-weight: 700; letter-spacing: -0.04em;
  line-height: 1.1; color: var(--txt-b); margin-bottom: 20px;
  max-width: 800px; margin-left: auto; margin-right: auto;
}
.article-source-row {
  font-size: 13px; color: var(--txt-b3);
  display: flex; align-items: center; justify-content: center; gap: 12px;
}

/* Article body */
.article-body {
  max-width: 680px; margin: 0 auto; padding: 56px 24px 100px;
}
.article-body p {
  font-size: 19px; line-height: 1.9; color: #1d1d1f;
  margin-bottom: 1.6em; font-weight: 400;
  letter-spacing: -0.01em;
}
.article-body p:last-child { margin-bottom: 0; }

/* empty */
.empty-brick { grid-column: 1/-1; padding: 80px; text-align: center; font-size: 17px; color: var(--txt-w3); background: var(--dark1); }

/* print */
@media print {
  #gnav, #seg-bar { display: none; }
  #article-view { position: static; overflow: visible; }
  .article-nav { display: none; }
}

/* mobile */
@media (max-width: 680px) {
  .hero-headline { font-size: 40px; }
  .hero-kpis { gap: 32px; }
  .kpi-val { font-size: 36px; }
  #brick-grid { grid-template-columns: 1fr; }
  .brick { min-height: 320px; padding: 36px 28px; }
  .brick.full { min-height: 360px; }
  .brick-title { font-size: 22px; }
  .brick.full .brick-title { font-size: 28px; }
  .article-headline { font-size: 32px; }
  .article-body p { font-size: 17px; }
}
"""



NEW_JS_LINES = ['const DATA={DATA_JSON};', 'const DEPTS={DEPT_JSON};', 'const CAT_ORDER={CAT_ORDER_JSON};', '', 'function esc(s){', "  let r=String(s||'');", "  r=r.split('&').join('&amp;');", "  r=r.split('<').join('&lt;');", "  r=r.split('>').join('&gt;');", '  r=r.split(\'"\').join(\'&quot;\');', '  return r;', '}', '', '// ── INIT ──', 'function init(){', '  const now=new Date();', '  const roc=now.getFullYear()-1911;', "  document.getElementById('gnav-date').textContent='民國 '+roc+'年'+(now.getMonth()+1)+'月'+now.getDate()+'日';", "  document.getElementById('kpi-must').textContent=DATA.filter(i=>i.priority===1).length;", "  document.getElementById('kpi-total').textContent=DATA.length;", "  document.getElementById('kpi-cat').textContent=new Set(DATA.map(i=>i.cat)).size;", '  buildSegs();', "  renderBricks('all');", '}', '', '// ── SEGMENT BAR ──', 'function buildSegs(){', "  const bar=document.getElementById('seg-bar');", "  bar.innerHTML='';", "  const a=document.createElement('div');", "  a.className='seg active';a.textContent='全部';", "  a.onclick=()=>switchSeg('all',a);", '  bar.appendChild(a);', '  CAT_ORDER.forEach(cat=>{', '    const d=DEPTS[cat];', "    const s=document.createElement('div');", "    s.className='seg';", "    s.textContent=(d?d.icon:'')+' '+cat;", '    s.onclick=()=>switchSeg(cat,s);', '    bar.appendChild(s);', '  });', '}', 'function switchSeg(cat,el){', "  document.querySelectorAll('.seg').forEach(s=>s.classList.remove('active'));", "  el.classList.add('active');", '  renderBricks(cat);', '}', '', '// ── BRICK GRID ──', 'function renderBricks(cat){', "  const grid=document.getElementById('brick-grid');", "  grid.innerHTML='';", "  const items=cat==='all'?DATA:DATA.filter(i=>i.cat===cat);", '  if(!items.length){', "    const e=document.createElement('div');e.className='empty-brick';e.textContent='目前無資料';", '    grid.appendChild(e);return;', '  }', '  items.forEach((item,i)=>{', '    grid.appendChild(makeBrick(item,i));', '  });', '}', '', 'function makeBrick(item,idx){', '  const dataIdx=DATA.indexOf(item);', '  const isFirst=idx===0;', '  const isLight=idx%5===3;', "  const brick=document.createElement('div');", "  let cls='brick';", "  if(isFirst) cls+=' full dark-hero';", "  else if(isLight) cls+=' light';", "  else cls+=' dark';", '  brick.className=cls;', "  let inner='';", '  if(item.priority===1) inner+=\'<div class="brick-must-bar"></div>\';', '  else if(item.priority===2) inner+=\'<div class="brick-watch-bar"></div>\';', "  const cat=DEPTS[item.cat]?DEPTS[item.cat].icon+' '+item.cat:item.cat;", '  inner+=\'<div class="brick-eyebrow">\'+esc(cat)+\'</div>\';', '  inner+=\'<div class="brick-title">\'+esc(item.title)+\'</div>\';', '  inner+=\'<div class="brick-summary">\'+esc(item.summary)+\'</div>\';', '  inner+=\'<div class="brick-cta">閱讀全文 ›</div>\';', '  let badge=item.priority===1?\'<span class="badge-must">必看</span>\':', '    item.priority===2?\'<span class="badge-watch">關注</span>\':\'\';', '  inner+=\'<div class="brick-meta">\'+badge+\'<span>\'+esc(item.source)+\'</span></div>\';', '  brick.innerHTML=inner;', '  brick.onclick=()=>openArticle(dataIdx);', '  return brick;', '}', '', '// ── ARTICLE VIEW ──', 'function openArticle(idx){', '  const item=DATA[idx];', "  const view=document.getElementById('article-view');", "  const rawText=item.full_text||'尚未擷取到內文內容';", "  const paras=rawText.split('\\n\\n').map(p=>'<p>'+esc(p.trim())+'</p>').join('');", "  const cat=DEPTS[item.cat]?DEPTS[item.cat].icon+' '+item.cat:item.cat;", "  document.getElementById('art-cat').textContent=cat;", "  document.getElementById('art-nav-cat').textContent=cat;", "  document.getElementById('art-title').textContent=item.title;", "  document.getElementById('art-source').textContent='來源：'+item.source;", "  document.getElementById('art-body').innerHTML=paras;", "  view.style.display='block';", '  view.scrollTo(0,0);', "  document.body.style.overflow='hidden';", '  // push state for back button', "  history.pushState({article:idx},'','');", '}', 'function closeArticle(){', "  document.getElementById('article-view').style.display='none';", "  document.body.style.overflow='';", '}', "window.addEventListener('popstate',e=>{", "  if(document.getElementById('article-view').style.display==='block') closeArticle();", '});', "document.addEventListener('keydown',e=>{if(e.key==='Escape')closeArticle();});", 'init();']


def generate_html(data):
    p_rank = {1: 0, 2: 1, 0: 2}
    data_sorted = sorted(data, key=lambda x: p_rank.get(x["priority"], 2))

    data_json = json.dumps(data_sorted, ensure_ascii=False).replace("</", "</")
    dept_json = json.dumps(
        {k: {"icon": v["icon"]} for k, v in DEPARTMENTS.items()},
        ensure_ascii=False
    ).replace("</", "</")
    cat_order_json = json.dumps(CATEGORY_ORDER, ensure_ascii=False)

    # build JS
    js_code = "\n".join(NEW_JS_LINES)
    js_code = js_code.replace("{DATA_JSON}", data_json)
    js_code = js_code.replace("{DEPT_JSON}", dept_json)
    js_code = js_code.replace("{CAT_ORDER_JSON}", cat_order_json)

    must_count = sum(1 for i in data_sorted if i["priority"] == 1)

    html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-TW">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>EPC Intelligence Hub</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@700;900&family=Noto+Sans+TC:wght@300;400;500;700&display=swap" rel="stylesheet">\n'
        '<style>\n' + NEW_CSS + '\n</style>\n'
        '</head>\n'
        '<body>\n'

        # Global nav
        '<nav id="gnav">\n'
        '  <div class="gnav-logo"><span class="gnav-dot"></span><span class="gnav-name">EPC Intelligence Hub</span></div>\n'
        '  <span class="gnav-date" id="gnav-date"></span>\n'
        '</nav>\n'

        # Home view
        '<div id="home-view">\n'

        # Hero block
        '<section class="hero-block">\n'
        '  <div class="hero-eyebrow">National Development Council &middot; Economic Planning Division</div>\n'
        '  <div class="hero-headline">\u6bcf\u65e5\u65b0\u8a0a<br>\u60c5\u5831\u5f59\u6574</div>\n'
        '  <div class="hero-sub">Internal Use Only &middot; \u6a5f\u5bc6\u6587\u4ef6</div>\n'
        '  <div class="hero-kpis">\n'
        '    <div><div class="kpi-val red" id="kpi-must">-</div><div class="kpi-label">Must Read</div></div>\n'
        '    <div><div class="kpi-val blue" id="kpi-total">-</div><div class="kpi-label">Today\u2019s Total</div></div>\n'
        '    <div><div class="kpi-val" id="kpi-cat">-</div><div class="kpi-label">Categories</div></div>\n'
        '  </div>\n'
        '</section>\n'

        # Segment bar
        '<div id="seg-bar"></div>\n'

        # Brick grid
        '<div id="brick-grid"></div>\n'

        '</div>\n'  # end home-view

        # Article view (hidden by default)
        '<div id="article-view">\n'
        '  <nav class="article-nav">\n'
        '    <button class="article-back" onclick="closeArticle()">&#8249; \u8fd4\u56de</button>\n'
        '    <span class="article-nav-cat" id="art-nav-cat"></span>\n'
        '  </nav>\n'
        '  <div class="article-hero">\n'
        '    <div class="article-eyebrow" id="art-cat"></div>\n'
        '    <h1 class="article-headline" id="art-title"></h1>\n'
        '    <div class="article-source-row"><span id="art-source"></span></div>\n'
        '  </div>\n'
        '  <div class="article-body" id="art-body"></div>\n'
        '</div>\n'

        '<script>\n' + js_code + '\n</script>\n'
        '</body>\n'
        '</html>\n'
    )

    with open("index.html", "w", encoding="utf-8", errors="replace") as f:
        f.write(html)


if __name__ == "__main__":
    run_dashboard()
