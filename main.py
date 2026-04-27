import pdfplumber
import os
import json

# ── 1. 分類與優先級定義 ──────────────────────────────────────────────
DEPARTMENTS = {
    "風險監控": {
        "icon": "⚠️",
        "label": "Risk Monitor",
        "keywords": ["美伊", "伊朗", "戰爭", "川普", "選情", "槍響", "Fed", "利率", "衝突", "地緣", "供應鏈"]
    },
    "總體數據": {
        "icon": "📊",
        "label": "Macro Data",
        "keywords": ["出口", "進口", "物價", "通膨", "匯率", "GDP", "主計", "景氣", "成長", "外銷"]
    },
    "產業動能": {
        "icon": "⚙️",
        "label": "Industry",
        "keywords": ["AI", "資本支出", "台積電", "半導體", "伺服器", "CoWoS", "設備", "製程", "先進封裝"]
    },
    "政策規畫": {
        "icon": "🏢",
        "label": "Policy",
        "keywords": ["國發會", "政策", "計畫", "電力", "預算", "離岸風電", "算力", "淨零", "綠能"]
    }
}

MUST_READ = [
    "Fed", "FOMC", "主計", "主計處", "GDP", "升息", "降息",
    "央行理監事", "利率決議", "通膨數據", "外銷訂單", "貿易統計",
    "戰爭", "地緣", "衝突", "制裁", "供應鏈斷鏈"
]

WATCH = [
    "出口", "進口", "資本支出", "AI", "台積電", "半導體",
    "景氣", "匯率", "油價", "通膨", "物價", "川普",
    "美伊", "離岸風電", "淨零", "算力"
]


def get_priority(title):
    if any(k in title for k in MUST_READ):
        return "must"
    if any(k in title for k in WATCH):
        return "watch"
    return "normal"


def get_lead(title, cat):
    if any(k in title for k in ["資本支出", "AI", "設備", "伺服器"]):
        return "民間投資（I）上行動能，支撐 GDP 成長"
    if any(k in title for k in ["出口", "訂單", "外銷"]):
        return "外需動能指標，影響淨出口（X-M）貢獻度"
    if any(k in title for k in ["通膨", "油價", "物價", "CPI"]):
        return "供給端成本壓力，制約民間消費（C）空間"
    if any(k in title for k in ["川普", "戰爭", "地緣", "衝突", "制裁"]):
        return "系統性風險訊號，需調高不確定性溢價"
    if any(k in title for k in ["Fed", "利率", "央行", "升息", "降息"]):
        return "貨幣政策路徑，影響台美利差與資金流向"
    if any(k in title for k in ["政策", "計畫", "預算", "國發會"]):
        return "政府支出（G）結構調整，牽動公共投資預期"
    if any(k in title for k in ["台積電", "半導體", "CoWoS", "封裝"]):
        return "供應鏈核心動向，影響出口與民間投資預測"
    if any(k in title for k in ["景氣", "GDP", "成長"]):
        return "總體景氣指標，影響整體成長預測校準"
    return "一般經濟資訊，建議持續觀察後續數據"


# ── 2. PDF 解析 ──────────────────────────────────────────────

def build_article_index(pdf):
    results = []

    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        has_source = any(l.startswith("來源:") or l.startswith("來源：") for l in lines[:8])
        has_table = page.extract_table() is not None
        char_count = len("".join(lines))

        if has_source:
            cat = "start"
        elif has_table:
            cat = "toc"
        elif char_count < 30:
            cat = "sep"
        else:
            cat = "cont"

        results.append((cat, lines))

    index = {}
    last_key = None

    for cat, lines in results:
        if cat == "start":
            src_idx = next(
                (j for j, l in enumerate(lines) if l.startswith("來源:") or l.startswith("來源：")),
                None
            )

            if src_idx is None:
                last_key = None
                continue

            title_key = "".join(lines[:src_idx]).replace(" ", "")
            title_key = title_key.encode("utf-8", errors="replace").decode("utf-8")

            body_lines = [
                l for l in lines[src_idx + 1:]
                if not l.strip().isdigit() and l.strip() != "回到目錄"
            ]

            body = "\n".join(body_lines).encode("utf-8", errors="replace").decode("utf-8")

            if title_key:
                index[title_key] = body
                last_key = title_key

        elif cat == "cont" and last_key:
            extra_lines = [
                l for l in lines
                if not l.strip().isdigit() and l.strip() != "回到目錄"
            ]
            extra = "\n".join(extra_lines).encode("utf-8", errors="replace").decode("utf-8")

            if extra:
                index[last_key] = index[last_key] + "\n" + extra

        else:
            last_key = None

    return index


def find_article(index, toc_title):
    search_key = toc_title.replace(" ", "")[:10]

    for art_key, body in index.items():
        if search_key in art_key:
            return body

    # fallback：短一點再找
    search_key = toc_title.replace(" ", "")[:6]
    for art_key, body in index.items():
        if search_key in art_key:
            return body

    return ""


def extract_summary(body, limit=320):
    if not body:
        return ""

    for line in body.split("\n"):
        line = line.strip()
        if len(line) >= 20 and ("，" in line or "。" in line or "、" in line):
            return line[:limit]

    first = body.split("\n")[0].strip()
    return first[:limit]


# ── 3. 主程式 ──────────────────────────────────────────────

def run_dashboard():
    if not os.path.exists("data"):
        os.makedirs("data")

    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]

    if not pdf_files:
        print("data 資料夾內找不到 PDF")
        return

    pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join("data", x)))
    latest_pdf = os.path.join("data", pdf_files[-1])

    print(f"正在分析: {latest_pdf}")

    organized_data = {cat: {} for cat in DEPARTMENTS.keys()}
    organized_data["其他資訊"] = {}

    with pdfplumber.open(latest_pdf) as pdf:
        print("建立文章索引中...")
        article_index = build_article_index(pdf)
        print(f"找到 {len(article_index)} 篇內文頁")

        for page in pdf.pages[:10]:
            table = page.extract_table()

            if not table:
                continue

            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]:
                    continue

                title = str(row[1]).replace("\n", "").strip()
                source = str(row[2]).replace("\n", " ").strip() if len(row) > 2 and row[2] else "未知"

                if len(title) < 5 or "新聞議題" in title:
                    continue

                found_cat = "其他資訊"

                for cat, info in DEPARTMENTS.items():
                    if any(k in title for k in info["keywords"]):
                        found_cat = cat
                        break

                full_text = find_article(article_index, title)
                summary = extract_summary(full_text)
                priority = get_priority(title)
                lead = get_lead(title, found_cat)
                theme_key = title[:8]

                if theme_key not in organized_data[found_cat]:
                    organized_data[found_cat][theme_key] = {
                        "main_title": title,
                        "related_titles": [],
                        "sources": [source],
                        "full_text": full_text,
                        "summary": summary,
                        "priority": priority,
                        "lead": lead,
                    }
                else:
                    p_rank = {"must": 0, "watch": 1, "normal": 2}
                    existing = organized_data[found_cat][theme_key]

                    if p_rank[priority] < p_rank[existing["priority"]]:
                        existing["priority"] = priority

                    if title != existing["main_title"]:
                        existing["related_titles"].append({
                            "title": title,
                            "source": source
                        })

                    if source not in existing["sources"]:
                        existing["sources"].append(source)

    generate_html(organized_data)
    print("✅ 已產生 index.html")


# ── 4. CSS ──────────────────────────────────────────────

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #f5f5f7;
  --white: rgba(255,255,255,0.92);
  --card: rgba(255,255,255,0.84);
  --border: rgba(0,0,0,0.08);
  --text-p: #1d1d1f;
  --text-s: #515154;
  --text-m: #86868b;
  --accent: #0071e3;
  --blue: #0071e3;
  --orange: #ff9500;
  --green: #34c759;
  --purple: #af52de;
  --must-left: #ff3b30;
  --watch-left: #ff9500;
  --must-bg: #fff5f5;
  --watch-bg: #fffaf0;
  --must-tag-bg: #ffe5e5;
  --must-tag-text: #b42318;
  --watch-tag-bg: #fff1d6;
  --watch-tag-text: #9a5b00;
  --radius: 24px;
  --radius-sm: 14px;
  --shadow: 0 24px 70px rgba(0,0,0,0.10);
}

body {
  background: #f5f5f7;
  color: var(--text-p);
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
  min-height: 100vh;
  font-size: 17px;
  line-height: 1.72;
}

.header {
  background: rgba(255,255,255,0.72);
  backdrop-filter: blur(22px);
  border-bottom: 1px solid var(--border);
  padding: 0 56px;
  height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-brand { display: flex; flex-direction: column; gap: 2px; }
.header-title { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }
.header-sub { font-size: 12px; color: var(--text-m); letter-spacing: 0.06em; }
.header-actions { display: flex; align-items: center; gap: 10px; }
.header-date { font-size: 14px; color: var(--text-s); margin-right: 8px; }

.btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 40px;
  padding: 0 18px;
  border-radius: 999px;
  font-size: 14px;
  font-family: inherit;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid var(--border);
  transition: transform 0.16s ease, background 0.16s ease, box-shadow 0.16s ease;
  white-space: nowrap;
}
.btn:hover { transform: translateY(-1px); }
.btn-primary {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
  box-shadow: 0 8px 20px rgba(0,113,227,0.18);
}
.btn-primary:hover { background: #0066cc; }
.btn-primary.success { background: #34c759; border-color: #34c759; }
.btn-ghost { background: rgba(255,255,255,0.55); color: var(--text-p); }

.main { padding: 44px 48px 90px; max-width: 1180px; margin: 0 auto; }

/* Hero */
.hero {
  position: relative;
  overflow: hidden;
  min-height: 360px;
  border-radius: 34px;
  padding: 52px 56px;
  margin-bottom: 34px;
  background:
    radial-gradient(circle at 20% 20%, rgba(0,113,227,0.35), transparent 30%),
    radial-gradient(circle at 78% 18%, rgba(175,82,222,0.26), transparent 26%),
    radial-gradient(circle at 70% 82%, rgba(52,199,89,0.20), transparent 28%),
    linear-gradient(135deg, #050816 0%, #111827 52%, #1d1d1f 100%);
  color: white;
  box-shadow: 0 30px 90px rgba(0,0,0,0.22);
}

.hero::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: linear-gradient(to bottom, rgba(0,0,0,0.9), transparent 86%);
  pointer-events: none;
}

.orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(2px);
  opacity: 0.72;
  animation: floatOrb 9s ease-in-out infinite;
}
.orb.blue { width: 210px; height: 210px; background: rgba(0,113,227,0.38); top: -60px; right: 210px; }
.orb.orange { width: 150px; height: 150px; background: rgba(255,149,0,0.28); bottom: 28px; right: 70px; animation-delay: -2s; }
.orb.green { width: 120px; height: 120px; background: rgba(52,199,89,0.25); bottom: 72px; left: 40px; animation-delay: -4s; }

@keyframes floatOrb {
  0%, 100% { transform: translate3d(0,0,0) scale(1); }
  50% { transform: translate3d(18px,-18px,0) scale(1.06); }
}

.ring {
  position: absolute;
  right: 68px;
  top: 62px;
  width: 170px;
  height: 170px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.20);
  animation: rotateRing 18s linear infinite;
}
.ring::before {
  content: "";
  position: absolute;
  inset: 22px;
  border-radius: 50%;
  border: 1px dashed rgba(255,255,255,0.24);
}
.ring::after {
  content: "";
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #fff;
  top: 14px;
  left: 78px;
}
@keyframes rotateRing { to { transform: rotate(360deg); } }

.hero-content { position: relative; z-index: 2; max-width: 760px; }
.hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 13px;
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 999px;
  color: rgba(255,255,255,0.82);
  font-size: 13px;
  margin-bottom: 22px;
  background: rgba(255,255,255,0.08);
  backdrop-filter: blur(14px);
}
.hero-title {
  font-size: clamp(44px, 6vw, 76px);
  font-weight: 850;
  line-height: 1.02;
  letter-spacing: -0.06em;
  margin-bottom: 18px;
}
.hero-desc {
  font-size: 22px;
  line-height: 1.6;
  color: rgba(255,255,255,0.78);
  max-width: 760px;
  letter-spacing: -0.02em;
}
.hero-stats {
  position: relative;
  z-index: 2;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 36px;
  max-width: 620px;
}
.stat-card {
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.16);
  backdrop-filter: blur(18px);
  border-radius: 20px;
  padding: 18px 20px;
}
.stat-num { font-size: 36px; font-weight: 800; letter-spacing: -0.04em; }
.stat-label { font-size: 13px; color: rgba(255,255,255,0.66); }

.top5 {
  background: rgba(255,255,255,0.78);
  backdrop-filter: blur(22px);
  border: 1px solid var(--border);
  border-radius: 28px;
  padding: 28px 30px;
  margin-bottom: 26px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.06);
}
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 16px;
}
.section-title {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.04em;
}
.section-note {
  font-size: 14px;
  color: var(--text-m);
}
.top5-list { display: grid; gap: 10px; }
.top5-item {
  display: grid;
  grid-template-columns: 34px 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 13px 0;
  border-top: 1px solid var(--border);
}
.top5-rank {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--text-p);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 800;
}
.top5-title {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.45;
  letter-spacing: -0.02em;
}
.top5-cat {
  font-size: 13px;
  color: var(--text-m);
  white-space: nowrap;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
}

.legend {
  display: flex;
  align-items: center;
  gap: 18px;
  font-size: 14px;
  color: var(--text-m);
}
.leg { display: flex; align-items: center; gap: 7px; }
.leg-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.leg-dot.must { background: var(--must-left); }
.leg-dot.watch { background: var(--watch-left); }
.leg-dot.normal { background: #c7c7cc; }

.tabs {
  display: flex;
  gap: 8px;
  padding: 7px;
  background: rgba(255,255,255,0.66);
  border: 1px solid var(--border);
  border-radius: 999px;
  width: fit-content;
  backdrop-filter: blur(18px);
  overflow-x: auto;
}
.tab-btn {
  padding: 10px 20px;
  border: none;
  background: transparent;
  font-size: 15px;
  font-family: inherit;
  font-weight: 650;
  color: var(--text-s);
  cursor: pointer;
  border-radius: 999px;
  transition: all 0.16s ease;
  white-space: nowrap;
}
.tab-btn:hover { background: rgba(0,0,0,0.04); color: var(--text-p); }
.tab-btn.active { color: #fff; background: var(--text-p); }

.news-list { display: flex; flex-direction: column; gap: 18px; }

.news-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 6px solid transparent;
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: 0 8px 28px rgba(0,0,0,0.045);
  backdrop-filter: blur(18px);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  opacity: 0;
  transform: translateY(18px);
  animation: cardIn 0.55s cubic-bezier(0.19,1,0.22,1) forwards;
}
@keyframes cardIn { to { opacity: 1; transform: translateY(0); } }

.news-card:hover { transform: translateY(-2px); box-shadow: var(--shadow); }
.news-card.priority-must { border-left-color: var(--must-left); background: linear-gradient(90deg, var(--must-bg), rgba(255,255,255,0.9)); }
.news-card.priority-watch { border-left-color: var(--watch-left); background: linear-gradient(90deg, var(--watch-bg), rgba(255,255,255,0.9)); }

.card-top {
  padding: 26px 30px;
  display: flex;
  align-items: flex-start;
  gap: 20px;
  cursor: pointer;
  user-select: none;
}
.prio-col { flex-shrink: 0; padding-top: 4px; }
.prio-badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  padding: 5px 11px;
  border-radius: 999px;
  white-space: nowrap;
}
.prio-badge.must { background: var(--must-tag-bg); color: var(--must-tag-text); }
.prio-badge.watch { background: var(--watch-tag-bg); color: var(--watch-tag-text); }
.prio-badge.normal { background: #f2f2f7; color: var(--text-m); }

.card-info { flex: 1; min-width: 0; }
.card-title {
  font-size: 24px;
  font-weight: 800;
  line-height: 1.35;
  letter-spacing: -0.035em;
  color: var(--text-p);
  margin-bottom: 10px;
}
.card-top:hover .card-title { color: var(--accent); }
.card-lead { font-size: 17px; color: var(--text-s); margin-bottom: 14px; line-height: 1.65; }
.card-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.src-tag {
  font-size: 13px;
  color: var(--text-s);
  background: rgba(0,0,0,0.045);
  padding: 5px 10px;
  border-radius: 999px;
}
.related-badge { font-size: 13px; color: var(--text-m); }

.toggle-icon {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(0,0,0,0.045);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-s);
  font-size: 24px;
  transition: transform 0.22s ease, background 0.16s ease, color 0.16s ease;
  margin-top: 2px;
}
.news-card.open .toggle-icon { transform: rotate(90deg); background: var(--accent); color: #fff; }

.card-expand { display: none; border-top: 1px solid var(--border); background: rgba(255,255,255,0.55); }
.news-card.open .card-expand { display: block; }

.inner-tabs {
  display: flex;
  gap: 8px;
  background: rgba(245,245,247,0.88);
  border-bottom: 1px solid var(--border);
  padding: 12px 26px 0;
}
.inner-tab {
  padding: 11px 18px;
  border: none;
  background: transparent;
  font-size: 15px;
  font-family: inherit;
  font-weight: 700;
  color: var(--text-m);
  cursor: pointer;
  border-bottom: 3px solid transparent;
}
.inner-tab.active { color: var(--accent); border-bottom-color: var(--accent); }

.inner-panel { display: none; padding: 30px; }
.inner-panel.active { display: block; }

.summary-block {
  font-size: 21px;
  color: var(--text-p);
  line-height: 1.85;
  font-family: "Noto Serif TC", serif;
  border-left: 5px solid var(--accent);
  padding: 4px 0 4px 22px;
  outline: none;
  white-space: pre-wrap;
}

.fulltext-body {
  font-size: 18px;
  color: var(--text-s);
  line-height: 2.05;
  font-family: "Noto Serif TC", serif;
  white-space: pre-wrap;
  outline: none;
}

.fulltext-paste {
  width: 100%;
  min-height: 170px;
  padding: 18px 20px;
  border: 1px dashed rgba(0,0,0,0.18);
  border-radius: 16px;
  font-family: "Noto Serif TC", serif;
  font-size: 18px;
  color: var(--text-s);
  background: #fff;
  resize: vertical;
  outline: none;
  line-height: 1.95;
}

.fulltext-hint {
  font-size: 15px;
  color: var(--text-m);
  margin-bottom: 12px;
}

.related-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border);
  font-size: 17px;
  color: var(--text-s);
}

.related-row:last-child { border-bottom: none; }
.related-bullet { color: var(--accent); flex-shrink: 0; margin-top: 2px; font-size: 14px; }
.related-src { font-size: 13px; color: var(--text-m); flex-shrink: 0; margin-left: auto; }

.empty-state { text-align: center; padding: 80px 20px; color: var(--text-m); font-size: 17px; }

@media print {
  .header { position: static; backdrop-filter: none; }
  .hero, .top5 { box-shadow: none; }
  .orb, .ring, .btn, .tabs, .inner-tabs, .fulltext-paste, .fulltext-hint { display: none !important; }
  .news-card { break-inside: avoid; box-shadow: none; }
  .card-expand { display: block !important; }
  .inner-panel { display: block !important; padding: 18px 30px; }
}

@media (max-width: 760px) {
  .header { padding: 0 18px; height: auto; min-height: 72px; gap: 12px; flex-wrap: wrap; }
  .header-sub, .header-date { display: none; }
  .main { padding: 28px 18px 64px; }
  .hero { padding: 38px 28px; min-height: 420px; }
  .hero-stats { grid-template-columns: 1fr; }
  .hero-title { font-size: 42px; }
  .hero-desc { font-size: 18px; }
  .toolbar { align-items: flex-start; flex-direction: column; }
  .tabs { width: 100%; }
  .card-top { padding: 22px 20px; }
  .card-title { font-size: 21px; }
  .summary-block { font-size: 18px; }
}
"""


# ── 5. JS ──────────────────────────────────────────────

def build_js(data_json, sep_double, sep_single):
    lines = [
        "const DATA = " + data_json + ";",
        "const CATS = Object.keys(DATA);",
        "let currentTab = 'all';",
        "const pasteStore = {};",
        "const PRIO_LABEL = {must:'必看',watch:'關注',normal:'一般'};",
        "",
        "function flattenItems(){",
        "  const arr=[];",
        "  CATS.forEach(cat=>DATA[cat].items.forEach(item=>arr.push({...item,cat:cat,icon:DATA[cat].icon})));",
        "  const rank={must:0,watch:1,normal:2};",
        "  arr.sort((a,b)=>rank[a.priority]-rank[b.priority]);",
        "  return arr;",
        "}",
        "",
        "function renderHero(){",
        "  const items=flattenItems();",
        "  const must=items.filter(i=>i.priority==='must').length;",
        "  const watch=items.filter(i=>i.priority==='watch').length;",
        "  const normal=items.filter(i=>i.priority==='normal').length;",
        "  document.getElementById('stat-must').textContent=must;",
        "  document.getElementById('stat-watch').textContent=watch;",
        "  document.getElementById('stat-normal').textContent=normal;",
        "  const first=items[0];",
        "  if(first){",
        "    document.getElementById('hero-title').textContent='今日重點：'+first.cat;",
        "    document.getElementById('hero-desc').textContent=first.main_title;",
        "  }",
        "}",
        "",
        "function renderTop5(){",
        "  const box=document.getElementById('top5-list');",
        "  if(!box)return;",
        "  box.innerHTML='';",
        "  flattenItems().slice(0,5).forEach((item,idx)=>{",
        "    const row=document.createElement('div');",
        "    row.className='top5-item';",
        "    row.innerHTML='<div class=\"top5-rank\">'+(idx+1)+'</div><div class=\"top5-title\">'+item.main_title+'</div><div class=\"top5-cat\">'+item.icon+' '+item.cat+'</div>';",
        "    box.appendChild(row);",
        "  });",
        "}",
        "",
        "function renderTabs(){",
        "  const el=document.getElementById('tabs');",
        "  el.innerHTML='';",
        "  el.appendChild(mkTab('全部','all',true));",
        "  CATS.forEach(cat=>{",
        "    const d=DATA[cat];",
        "    const mustN=d.items.filter(i=>i.priority==='must').length;",
        "    const label=d.icon+' '+cat+(mustN?' ⚑'+mustN:'');",
        "    el.appendChild(mkTab(label,cat,false));",
        "  });",
        "}",
        "",
        "function mkTab(label,id,active){",
        "  const b=document.createElement('button');",
        "  b.className='tab-btn'+(active?' active':'');",
        "  b.dataset.id=id;",
        "  b.textContent=label;",
        "  b.onclick=()=>switchTab(id);",
        "  return b;",
        "}",
        "",
        "function switchTab(id){",
        "  currentTab=id;",
        "  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',b.dataset.id===id));",
        "  renderList();",
        "}",
        "",
        "function renderList(){",
        "  const list=document.getElementById('news-list');",
        "  list.innerHTML='';",
        "  const targets=currentTab==='all'?CATS:[currentTab];",
        "  let n=0;",
        "  targets.forEach(cat=>DATA[cat].items.forEach(item=>{list.appendChild(makeCard(item,cat));n++;}));",
        "  if(!n){const e=document.createElement('div');e.className='empty-state';e.textContent='目前無相關新聞資料';list.appendChild(e);}",
        "}",
        "",
        "function makeCard(item,cat){",
        "  const card=document.createElement('div');",
        "  card.className='news-card priority-'+item.priority;",
        "  const srcHtml=item.sources.map(s=>'<span class=\"src-tag\">'+s+'</span>').join('');",
        "  const relN=item.related_count||0;",
        "  card.innerHTML=",
        "    '<div class=\"card-top\">'+",
        "      '<div class=\"prio-col\"><span class=\"prio-badge '+item.priority+'\">'+PRIO_LABEL[item.priority]+'</span></div>'+",
        "      '<div class=\"card-info\">'+",
        "        '<div class=\"card-title\">'+item.main_title+'</div>'+",
        "        '<div class=\"card-lead\">→ '+item.lead+'</div>'+",
        "        '<div class=\"card-meta\">'+srcHtml+(relN?'<span class=\"related-badge\">＋'+relN+' 則相關</span>':'')+'</div>'+",
        "      '</div>'+",
        "      '<span class=\"toggle-icon\">›</span>'+",
        "    '</div>'+",
        "    '<div class=\"card-expand\"></div>';",
        "  card.querySelector('.card-top').addEventListener('click',()=>{",
        "    const isOpen=card.classList.contains('open');",
        "    if(!isOpen)buildExpand(card,item);",
        "    card.classList.toggle('open');",
        "  });",
        "  return card;",
        "}",
        "",
        "function buildExpand(card,item){",
        "  const expand=card.querySelector('.card-expand');",
        "  if(expand.dataset.ready)return;",
        "  expand.dataset.ready='1';",
        "  const tabBar=document.createElement('div');",
        "  tabBar.className='inner-tabs';",
        "  expand.appendChild(tabBar);",
        "  const panels=[];",
        "  function addInnerTab(label,active){",
        "    const t=document.createElement('button');",
        "    t.className='inner-tab'+(active?' active':'');",
        "    t.textContent=label;",
        "    const idx=panels.length;",
        "    t.onclick=()=>{",
        "      tabBar.querySelectorAll('.inner-tab').forEach((x,i)=>x.classList.toggle('active',i===idx));",
        "      panels.forEach((p,i)=>p.classList.toggle('active',i===idx));",
        "    };",
        "    tabBar.appendChild(t);",
        "    const p=document.createElement('div');",
        "    p.className='inner-panel'+(active?' active':'');",
        "    expand.appendChild(p);",
        "    panels.push(p);",
        "    return p;",
        "  }",
        "  const p1=addInnerTab('新聞重點',true);",
        "  if(item.summary){",
        "    const div=document.createElement('div');",
        "    div.className='summary-block';",
        "    div.contentEditable='true';",
        "    div.textContent=item.summary;",
        "    p1.appendChild(div);",
        "  }else{",
        "    p1.innerHTML='<div class=\"summary-empty\">⚠️ 自動抓取失敗，請切換至「新聞全文」手動貼入</div>';",
        "  }",
        "  const p2=addInnerTab('新聞全文',false);",
        "  const storeKey=item.main_title;",
        "  if(item.full_text){",
        "    const div=document.createElement('div');",
        "    div.className='fulltext-body';",
        "    div.contentEditable='true';",
        "    div.textContent=item.full_text;",
        "    div.addEventListener('input',e=>{pasteStore[storeKey]=e.target.innerText;});",
        "    p2.appendChild(div);",
        "  }else{",
        "    const saved=pasteStore[storeKey]||'';",
        "    p2.innerHTML='<div class=\"fulltext-hint\">📋 未能自動擷取，請手動貼入：</div>'+'<textarea class=\"fulltext-paste\">'+saved+'</textarea>';",
        "    p2.querySelector('textarea').addEventListener('input',e=>{pasteStore[storeKey]=e.target.value;});",
        "  }",
        "  if(item.related_titles&&item.related_titles.length>0){",
        "    const p3=addInnerTab('相關報導 ('+item.related_titles.length+')',false);",
        "    item.related_titles.forEach(r=>{",
        "      const row=document.createElement('div');",
        "      row.className='related-row';",
        "      const t=typeof r==='object'?r.title:r;",
        "      const s=typeof r==='object'?r.source:'';",
        "      row.innerHTML='<span class=\"related-bullet\">▸</span><span style=\"flex:1\">'+t+'</span>'+(s?'<span class=\"related-src\">'+s+'</span>':'');",
        "      p3.appendChild(row);",
        "    });",
        "  }",
        "}",
        "",
        "document.getElementById('btn-copy').addEventListener('click',()=>{",
        "  const now=new Date();",
        "  const roc=now.getFullYear()-1911;",
        "  const mm=String(now.getMonth()+1).padStart(2,'0');",
        "  const dd=String(now.getDate()).padStart(2,'0');",
        "  const dateStr=roc+'.'+mm+'.'+dd;",
        "  let text='【'+dateStr+' 經濟規劃科 · 每日新聞重點】\\n'+'" + sep_double + "'+'\\n\\n';",
        "  const targets=currentTab==='all'?CATS:[currentTab];",
        "  targets.forEach(cat=>{",
        "    const d=DATA[cat];",
        "    text+=d.icon+' '+cat+'\\n'+'" + sep_single + "'+'\\n';",
        "    d.items.forEach(item=>{",
        "      text+='▌ ['+PRIO_LABEL[item.priority]+'] '+item.main_title+'\\n';",
        "      text+='   來源：'+item.sources.join('、')+'\\n';",
        "      text+='   → '+item.lead+'\\n';",
        "      if(item.summary)text+='   重點：'+item.summary+'\\n';",
        "      if(item.related_titles&&item.related_titles.length>0){",
        "        const rel=item.related_titles.map(r=>typeof r==='object'?r.title:r);",
        "        text+='   相關：'+rel.join('；')+'\\n';",
        "      }",
        "      text+='\\n';",
        "    });",
        "    text+='\\n';",
        "  });",
        "  navigator.clipboard.writeText(text).then(()=>{",
        "    const btn=document.getElementById('btn-copy');",
        "    btn.classList.add('success');",
        "    btn.innerHTML='✓ 已複製';",
        "    setTimeout(()=>{btn.classList.remove('success');btn.innerHTML='📋 複製今日摘要';},2000);",
        "  });",
        "});",
        "",
        "const now=new Date();",
        "const roc=now.getFullYear()-1911;",
        "document.getElementById('date-label').textContent='民國 '+roc+' 年 '+(now.getMonth()+1)+' 月 '+now.getDate()+' 日';",
        "renderHero();",
        "renderTop5();",
        "renderTabs();",
        "renderList();",
    ]

    return "\n".join(lines)


# ── 6. HTML 產生 ──────────────────────────────────────────────

def generate_html(data):
    js_data = {}
    p_rank = {"must": 0, "watch": 1, "normal": 2}

    for cat, items in data.items():
        if cat == "其他資訊":
            continue

        dept = DEPARTMENTS[cat]
        item_list = sorted(items.values(), key=lambda x: p_rank[x["priority"]])

        for item in item_list:
            item["related_count"] = len(item["related_titles"])

        js_data[cat] = {
            "icon": dept["icon"],
            "label": dept["label"],
            "items": item_list
        }

    data_json = json.dumps(js_data, ensure_ascii=False).replace("</", "<\\/")
    sep_double = "═" * 36
    sep_single = "─" * 30
    js_code = build_js(data_json, sep_double, sep_single)

    html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-TW">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>國發會經濟規劃科 · 每日新聞重點</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;600;700&family=Noto+Sans+TC:wght@300;400;500&display=swap" rel="stylesheet">\n'
        '<style>\n' + CSS + '\n</style>\n'
        '</head>\n'
        '<body>\n'
        '<header class="header">\n'
        '  <div class="header-brand">\n'
        '    <span class="header-title">國家發展委員會 · 經濟規劃科</span>\n'
        '    <span class="header-sub">每日新聞重點整理 · INTERNAL USE ONLY</span>\n'
        '  </div>\n'
        '  <div class="header-actions">\n'
        '    <span class="header-date" id="date-label"></span>\n'
        '    <button class="btn btn-ghost" onclick="window.print()">🖨 列印／PDF</button>\n'
        '    <button class="btn btn-primary" id="btn-copy">📋 複製今日摘要</button>\n'
        '  </div>\n'
        '</header>\n'
        '<main class="main">\n'
        '  <section class="hero">\n'
        '    <span class="orb blue"></span>\n'
        '    <span class="orb orange"></span>\n'
        '    <span class="orb green"></span>\n'
        '    <span class="ring"></span>\n'
        '    <div class="hero-content">\n'
        '      <div class="hero-kicker">Economic Intelligence · Daily Signal</div>\n'
        '      <h1 class="hero-title" id="hero-title">今日經濟訊號</h1>\n'
        '      <p class="hero-desc" id="hero-desc">正在彙整今日新聞重點與經濟規劃科應關注事項。</p>\n'
        '      <div class="hero-stats">\n'
        '        <div class="stat-card">\n'
        '          <div class="stat-num" id="stat-must">0</div>\n'
        '          <div class="stat-label">必看新聞</div>\n'
        '        </div>\n'
        '        <div class="stat-card">\n'
        '          <div class="stat-num" id="stat-watch">0</div>\n'
        '          <div class="stat-label">關注新聞</div>\n'
        '        </div>\n'
        '        <div class="stat-card">\n'
        '          <div class="stat-num" id="stat-normal">0</div>\n'
        '          <div class="stat-label">一般資訊</div>\n'
        '        </div>\n'
        '      </div>\n'
        '    </div>\n'
        '  </section>\n'
        '  <section class="top5">\n'
        '    <div class="section-head">\n'
        '      <div class="section-title">今日必看 Top 5</div>\n'
        '      <div class="section-note">依優先級與分類排序</div>\n'
        '    </div>\n'
        '    <div class="top5-list" id="top5-list"></div>\n'
        '  </section>\n'
        '  <div class="toolbar">\n'
        '    <div class="legend">\n'
        '      <span>優先級：</span>\n'
        '      <div class="leg"><span class="leg-dot must"></span>必看</div>\n'
        '      <div class="leg"><span class="leg-dot watch"></span>關注</div>\n'
        '      <div class="leg"><span class="leg-dot normal"></span>一般</div>\n'
        '    </div>\n'
        '    <div class="tabs" id="tabs"></div>\n'
        '  </div>\n'
        '  <div class="news-list" id="news-list"></div>\n'
        '</main>\n'
        '<script>\n' + js_code + '\n</script>\n'
        '</body>\n'
        '</html>\n'
    )

    with open("index.html", "w", encoding="utf-8", errors="replace") as f:
        f.write(html)


if __name__ == "__main__":
    run_dashboard()
