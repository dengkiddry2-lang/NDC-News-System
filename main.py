import pdfplumber
import os
import json
import re
from collections import Counter

# ── 1. 分類定義 ──────────────────────────────────────────────
DEPARTMENTS = {
    "社論與評論觀點": {
        "icon": "📝", "short": "社論",
        "keywords": ["社論","社評","時評","縱橫天下"],
        "pdf_sections": ["08", "07"],
        "source_keywords": ["社論","社評","時評","時論廣場","論壇","廣場"],
    },
    "國際經濟情勢": {
        "icon": "🌐", "short": "國際",
        "keywords": [],
        "pdf_sections": ["05", "06"],
    },
    "台灣總體經濟與數據": {
        "icon": "📊", "short": "總經",
        "keywords": [
            "GDP","景氣燈號","景氣","物價","通膨","CPI","失業率","薪資",
            "外銷訂單","出口統計","進口統計","貿易統計","稅收","超徵",
            "出生率","少子化","高齡化","消費者信心","PMI","非製造業",
            "淨零","碳排","再生能源","能源轉型",
        ],
        "pdf_sections": ["04"],
    },
    "台灣產業與投資動向": {
        "icon": "🏭", "short": "產業",
        "keywords": [
            "AI","半導體","台積電","台積","聯發科","聯電","鴻海",
            "台達電","廣達","緯創","英業達","資本支出","供應鏈",
            "算力","伺服器","CoWoS","先進封裝","製程","晶片",
            "離岸風電","綠能","電動車","ASIC","TPU","GPU",
            "新創","新興產業","科技業","數位","資料中心",
            "數位帳戶","純網銀","金融科技","FinTech","網銀",
            "金管會","台股","股市","基金","ETF",
        ],
        "pdf_sections": ["02", "04"],
    },
    "台灣政府與政策訊息": {
        "icon": "🏛️", "short": "政策",
        "keywords": [
            "國發會","行政院","總統府","經濟部","財政部","金管會",
            "國科會","央行","院會","法案","預算","政策","施政",
            "法規","條例","立法院","立委","修法","補助","國防",
            "軍購","軍事預算","特別條例",
        ],
        "pdf_sections": ["03", "04"],
        "exclude_keywords": [
            "安樂死","安寧","失智","醫護","廚餘","豬","旅遊",
            "禁團令","詐騙","甘肅","鞭刑","兒托","監管雲",
        ],
    },
}

CATEGORY_ORDER = [
    "社論與評論觀點",
    "國際經濟情勢",
    "台灣總體經濟與數據",
    "台灣產業與投資動向",
    "台灣政府與政策訊息",
]

NOISE_PREFIXES = ["來源","作者","版面","日期","出處","記者","編輯","回到目錄","本報訊"]
FRONT_PAGE_PATTERNS = ["A01", "AA01"]

def is_frontpage(source):
    return any(p in source for p in FRONT_PAGE_PATTERNS)

HARD_EXCLUDE = [
    "大麻","毒品","農業旱","廚餘養豬","安樂死","安寧照護",
    "失智","長照","石崇良","監管雲","甘肅翻車","鞭刑",
    "兒托法","禁團令","旅行業","赴陸禁","旅遊業者",
]

def should_skip(title, source, pdf_section):
    if any(k in title for k in HARD_EXCLUDE):
        return True
    dept = DEPARTMENTS.get("台灣政府與政策訊息", {})
    if dept.get("exclude_keywords"):
        if any(k in title for k in dept["exclude_keywords"]):
            return True
    return False

def is_noise_line(line):
    if line.isdigit(): return True
    return any(line.startswith(p) for p in NOISE_PREFIXES)

def clean_text_blocks(text_list):
    if not text_list: return ""
    merged = ""
    for line in text_list:
        line = line.strip()
        if not line or is_noise_line(line): continue
        if re.search(r'報導[〕】]$|^[／/].{0,10}報導[〕】]|^[合綜]\w*報導[〕】]|^記者.{0,15}報導', line): continue
        if len(line) <= 10 and re.search(r'[〕】報導]', line): continue
        if line.isdigit(): continue
        if not merged:
            merged = line
        elif (
            merged[-1] in ("。","！","？","；","…") or
            (len(merged) >= 2 and merged[-1] in ("」","\u201d","'","\u2019") and
             merged[-2] in ("。","！","？","；","…"))
        ):
            merged += "\n" + line
        else:
            merged += line

    merged = re.sub(r' +', ' ', merged).strip()
    sentences = re.split(r'(?<=[。！？；])', merged)
    paragraphs, current, count = [], "", 0
    for s in sentences:
        s = s.strip()
        if not s: continue
        current += s
        count += 1
        if count >= 3 and s[-1] in ("。","！","？","；"):
            paragraphs.append(current.strip())
            current, count = "", 0
    if current.strip(): paragraphs.append(current.strip())

    cleaned = []
    for p in paragraphs:
        p = p.replace("\n", " ")
        p = re.sub(r" {2,}", " ", p)
        p = re.sub(r" ([，。！？；：、「」『』）】])", r"\1", p)
        p = re.sub(r"([\u4e00-\u9fff\uff00-\uffef]) ([\u4e00-\u9fff\uff00-\uffef（「\u300e\u300c])", r"\1\2", p)
        p = p.strip()
        if p: cleaned.append(p)
    result = "\n\n".join(cleaned)
    result = re.sub(r'\n\n([」』\u201d\u2019])', r'\1', result)
    return result

def find_article(article_index, title):
    key = title.replace(" ", "")
    best, best_score = "", 0
    for art_key, content in article_index.items():
        for n in [14,12,10,8,6]:
            if key[:n] and key[:n] in art_key:
                if n > best_score:
                    best_score, best = n, content
                break
    return best if best_score >= 6 else ""

def extract_summary(content, limit=220):
    if not content: return "尚未擷取到內文摘要"
    parts = [p.strip() for p in content.split("\n\n") if p.strip()]
    if parts:
        return parts[0][:limit] + ("..." if len(parts[0]) > limit else "")
    return content[:limit]

def build_article_index(pdf):
    index, last_key, raw_map = {}, None, {}
    for page in pdf.pages:
        text = page.extract_text() or ""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if not lines: continue
        has_source = any(l.startswith("來源:") or l.startswith("來源：") for l in lines[:8])
        char_count = len("".join(lines))
        if has_source:
            src_idx = next(i for i,l in enumerate(lines) if l.startswith("來源:") or l.startswith("來源："))
            title_key = "".join(lines[:src_idx]).replace(" ","")
            body_start = src_idx + 1
            while body_start < len(lines):
                l = lines[body_start]
                is_author_tail = (
                    len(l) <= 15 and (
                        re.search(r'[報導〕】]\s*$', l) or
                        re.search(r'^[／/].{0,10}報導[〕】]', l) or
                        re.search(r'^[合綜]\w*報導[〕】]', l)
                    )
                )
                if is_author_tail:
                    body_start += 1
                else:
                    break
            raw_map[title_key] = lines[body_start:]
            last_key = title_key
        elif page.extract_table():
            last_key = None
        elif char_count < 30:
            last_key = None
        elif last_key and char_count > 50:
            if last_key in raw_map:
                raw_map[last_key].extend(lines)
    for key, text_list in raw_map.items():
        index[key] = clean_text_blocks(text_list)
    return index

# ── 3. 主程式 ──────────────────────────────────────────────
def run_dashboard():
    if not os.path.exists("data"): os.makedirs("data")
    pdf_files = [f for f in os.listdir("data") if f.lower().endswith(".pdf")]
    if not pdf_files: print("data 資料夾內找不到 PDF"); return
    pdf_files.sort(key=lambda x: os.path.getmtime(os.path.join("data", x)))
    latest_pdf = os.path.join("data", pdf_files[-1])
    print(f"處理檔案: {latest_pdf}")

    all_items, skipped = [], 0
    with pdfplumber.open(latest_pdf) as pdf:
        article_index = build_article_index(pdf)
        current_section = ""
        import re as _re2

        def is_toc_table(t):
            news_sources = ['時報','日報','聯合','自由','中時','工商','蘋果','鏡','報']
            for r in t:
                if not r or len(r) < 2: continue
                col2 = str(r[1] or '').strip()
                col3 = str(r[2] or '').strip() if len(r) > 2 else ''
                if len(col2) > 5 and any(s in col3 for s in news_sources): return True
            return False

        for page in pdf.pages:
            table = page.extract_table()
            if not table: continue
            if not is_toc_table(table): continue

            for row in table:
                if not row: continue
                c1 = str(row[0] or '').strip()
                c2 = str(row[1] or '').strip() if len(row) > 1 else ''
                c3 = str(row[2] or '').strip() if len(row) > 2 else ''

                if _re2.match(r'^\d{2}-', c1) and not c2:
                    current_section = c1
                    continue

                if not c2 or len(c2) < 5: continue
                if any(k in c2 for k in ["新聞議題","報導媒體","目錄","頁次"]): continue
                title = c2.replace("\n","").strip()
                source = c3.replace("\n"," ").strip() if c3 else "EPC彙整"
                if len(title) < 5: continue

                if should_skip(title, source, current_section): skipped += 1; continue

                found_cat = None
                sec_num = current_section[:2] if current_section else ""

                for cat in CATEGORY_ORDER:
                    dept = DEPARTMENTS[cat]
                    in_section = sec_num in dept.get("pdf_sections", [])

                    if in_section and not dept["keywords"] and "source_keywords" not in dept:
                        found_cat = cat; break
                    if in_section and dept.get("source_keywords"):
                        if (any(k in source for k in dept["source_keywords"]) or
                            any(k in title for k in dept.get("keywords", []))):
                            found_cat = cat; break

                    if in_section and dept["keywords"]:
                        if any(k in title + " " + source for k in dept["keywords"]):
                            found_cat = cat; break

                if not found_cat and sec_num == "01":
                    classify_text = title + " " + source
                    intl_src = ["國際","兩岸","全球","外電"]
                    intl_title = ["德國","法國","日本","韓國","美國","英國","歐洲",
                                  "中國","大陸","北京","上海","俄羅斯","以色列",
                                  "核能","核電","車諾比"]
                    if (any(k in source for k in intl_src) or
                            any(k in title for k in intl_title)):
                        found_cat = "國際經濟情勢"
                    else:
                        for cat in CATEGORY_ORDER:
                            if DEPARTMENTS[cat]["keywords"] and any(
                                k in classify_text for k in DEPARTMENTS[cat]["keywords"]
                            ):
                                found_cat = cat; break
                        if not found_cat:
                            found_cat = "國際經濟情勢"

                if not found_cat: skipped += 1; continue

                content = find_article(article_index, title)
                is_must = is_frontpage(source) and found_cat is not None
                all_items.append({
                    "title": title, "source": source, "cat": found_cat,
                    "priority": 1 if is_must else 0,
                    "summary": extract_summary(content), "full_text": content
                })

    print(f"保留 {len(all_items)} 則，略過 {skipped} 則")
    generate_html(all_items)
    print("✅ 已產生 index.html")

# ── 4. HTML 生成 ──────────────────────────────────────────────
def generate_html(data):
    p_rank = {1: 0, 0: 1}
    data_sorted = sorted(data, key=lambda x: p_rank.get(x["priority"], 1))
    data_json = json.dumps(data_sorted, ensure_ascii=False).replace("</", "\u003c/")
    dept_info = {k: {"icon": v["icon"], "short": v["short"]} for k,v in DEPARTMENTS.items()}
    dept_json = json.dumps(dept_info, ensure_ascii=False).replace("</", "\u003c/")
    cat_order_json = json.dumps(CATEGORY_ORDER, ensure_ascii=False)

    cat_counts = Counter(i["cat"] for i in data_sorted)
    must_total = sum(1 for i in data_sorted if i["priority"] == 1)

    highlights = []
    if must_total > 0:
        highlights.append({"label": "今日必看", "value": f"{must_total} 則", "cat": ""})
    for cat in CATEGORY_ORDER:
        cnt = cat_counts.get(cat, 0)
        if cnt > 0:
            m = sum(1 for i in data_sorted if i["cat"]==cat and i["priority"]==1)
            highlights.append({
                "label": DEPARTMENTS[cat]["short"],
                "value": f"{cnt} 則" + (f"・{m} 必看" if m else ""),
                "cat": cat
            })
    highlights_json = json.dumps(highlights, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EPC 經濟情報 — 國家發展委員會</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;500;600;700;900&family=Noto+Sans+TC:wght@300;400;500;700&family=Source+Han+Serif+TC:wght@400;700&display=swap" rel="stylesheet">
<style>
{CSS}
</style>
</head>
<body>

<!-- TOP UTILITY BAR -->
<div id="utility-bar">
  <div class="util-inner">
    <span class="util-org">國家發展委員會 經濟分析科</span>
    <span class="util-date" id="util-date"></span>
  </div>
</div>

<!-- MASTHEAD -->
<header id="masthead">
  <div class="masthead-inner">
    <div class="masthead-left">
      <div class="masthead-logo">
        <span class="logo-jp">EPC</span>
        <div class="logo-divider"></div>
        <div class="logo-sub">
          <span class="logo-cn">經濟情報</span>
          <span class="logo-en">Economic Press Clipping</span>
        </div>
      </div>
    </div>
    <div class="masthead-stats">
      <div class="stat-pill must-pill" id="must-pill-btn">
        <span class="stat-label">頭版要聞</span>
        <span class="stat-num red" id="kpi-must">{must_total}</span>
      </div>
      <div class="stat-sep"></div>
      <div class="stat-pill">
        <span class="stat-label">今日總則</span>
        <span class="stat-num" id="kpi-total">{len(data_sorted)}</span>
      </div>
    </div>
  </div>
</header>

<!-- CATEGORY NAV BAR -->
<nav id="cat-nav-bar">
  <div class="cat-nav-inner">
    <button class="cat-btn active" data-cat="all">全部</button>
    <!-- filled by JS -->
  </div>
</nav>

<!-- HOME VIEW -->
<div id="home-view">

  <!-- BREAKING TICKER -->
  <div class="ticker-wrap" id="ticker-wrap">
    <span class="ticker-label">頭版</span>
    <div class="ticker-track" id="ticker-track"></div>
  </div>

  <!-- MAIN GRID -->
  <main class="main-container" id="main-container">

    <!-- LEFT: TOP STORY + SECONDARY -->
    <section class="col-main">
      <div id="top-story-area"></div>
      <div class="section-divider"></div>
      <div id="secondary-area"></div>
    </section>

    <!-- RIGHT SIDEBAR -->
    <aside class="col-sidebar">
      <!-- MUST READ BOX -->
      <div class="sidebar-box" id="must-box">
        <div class="sidebar-box-header">
          <span class="sbox-label red-label">今日必看</span>
          <span class="sbox-sub">頭版 · 重點領域</span>
        </div>
        <div id="must-list"></div>
      </div>
      <!-- CATEGORY SUMMARY -->
      <div class="sidebar-box" id="cat-summary-box">
        <div class="sidebar-box-header">
          <span class="sbox-label">分類總覽</span>
        </div>
        <div id="cat-summary-list"></div>
      </div>
    </aside>

  </main>

  <!-- BOTTOM SECTION: ALL NEWS BY CATEGORY -->
  <div class="all-news-section">
    <div class="all-news-inner" id="all-news-inner"></div>
  </div>

</div><!-- end home-view -->

<!-- CATEGORY VIEW -->
<div id="cat-view" style="display:none;">
  <div class="page-nav">
    <button class="page-back-btn" onclick="goHome()">← 返回首頁</button>
    <span class="page-nav-title" id="cat-view-title"></span>
  </div>
  <div class="cat-view-inner">
    <div id="cat-news-list"></div>
  </div>
</div>

<!-- ARTICLE VIEW -->
<div id="article-view" style="display:none;">
  <div class="page-nav">
    <button class="page-back-btn" id="art-back-btn" onclick="closeArticle()">← 返回</button>
    <span class="page-nav-title" id="art-nav-cat"></span>
  </div>
  <article class="article-container">
    <header class="article-header">
      <div class="art-cat-tag" id="art-cat-tag"></div>
      <h1 class="art-headline" id="art-title"></h1>
      <div class="art-meta">
        <span class="art-source" id="art-source"></span>
      </div>
      <div class="art-summary-box" id="art-summary-box">
        <div class="art-summary-label">▌ 摘要重點</div>
        <p class="art-summary-text" id="art-summary"></p>
      </div>
    </header>
    <div class="art-body" id="art-body"></div>
  </article>
</div>

<script>
const DATA = {data_json};
const DEPTS = {dept_json};
const CAT_ORDER = {cat_order_json};
const HIGHLIGHTS = {highlights_json};

// ── 日期 ──
(function() {{
  const now = new Date();
  const roc = now.getFullYear() - 1911;
  const dateStr = '\u6c11\u570b' + roc + '\u5e74' + (now.getMonth()+1) + '\u6708' + now.getDate() + '\u65e5 \u661f\u671f' + ['\u65e5','\u4e00','\u4e8c','\u4e09','\u56db','\u4e94','\u516d'][now.getDay()];
  const el = document.getElementById('util-date');
  if(el) el.textContent = dateStr;
}})();

function esc(s) {{
  let r = String(s||'');
  return r.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

// ── CATEGORY NAV ──
function buildCatNav() {{
  const bar = document.querySelector('.cat-nav-inner');
  CAT_ORDER.forEach(cat => {{
    const btn = document.createElement('button');
    btn.className = 'cat-btn';
    btn.dataset.cat = cat;
    btn.textContent = DEPTS[cat] ? DEPTS[cat].short : cat;
    btn.onclick = () => openCatView(cat);
    bar.appendChild(btn);
  }});
  document.getElementById('must-pill-btn').onclick = () => openCatView('must');
}}

function setActiveNavBtn(cat) {{
  document.querySelectorAll('.cat-btn').forEach(b => b.classList.toggle('active', b.dataset.cat === cat));
}}

// ── TICKER ──
function buildTicker() {{
  const mustItems = DATA.filter(i => i.priority === 1);
  const track = document.getElementById('ticker-track');
  if(!mustItems.length) {{ document.getElementById('ticker-wrap').style.display='none'; return; }}
  const html = mustItems.map(item => {{
    const idx = DATA.indexOf(item);
    return '<span class="ticker-item" onclick="openArticle('+idx+')">' + esc(item.title) + '</span>';
  }}).join('<span class="ticker-sep">／</span>');
  track.innerHTML = html + '<span class="ticker-sep">&nbsp;&nbsp;&nbsp;&nbsp;</span>' + html;
}}

// ── TOP STORY ──
function buildTopStory() {{
  const area = document.getElementById('top-story-area');
  area.innerHTML = '';
  const allItems = DATA;
  if(!allItems.length) return;

  // 取最優先（priority=1）的第一則，或第一則
  const top = allItems.find(i => i.priority===1) || allItems[0];
  const topIdx = DATA.indexOf(top);
  const dept = DEPTS[top.cat] || {{}};

  area.innerHTML = `
    <div class="top-story" onclick="openArticle(${{topIdx}})">
      ${{top.priority===1 ? '<div class="ts-must-bar"></div>' : ''}}
      <div class="ts-cat-row">
        <span class="ts-cat-tag">${{esc(top.cat)}}</span>
        ${{top.priority===1 ? '<span class="ts-must-badge">頭版要聞</span>' : ''}}
      </div>
      <h2 class="ts-headline">${{esc(top.title)}}</h2>
      <p class="ts-summary">${{esc(top.summary)}}</p>
      <div class="ts-footer">
        <span class="ts-source">${{esc(top.source)}}</span>
        <span class="ts-cta">閱讀全文 →</span>
      </div>
    </div>
  `;
}}

// ── SECONDARY NEWS (below top story) ──
function buildSecondary() {{
  const area = document.getElementById('secondary-area');
  area.innerHTML = '';
  const allItems = DATA;
  if(allItems.length < 2) return;

  // 跳過第一則（已作 top story），取後面幾則
  const items = allItems.slice(1, 7);
  const rows = items.map((item, i) => {{
    const idx = DATA.indexOf(item);
    const dept = DEPTS[item.cat] || {{}};
    return `
      <div class="sec-row${{item.priority===1 ? ' sec-must' : ''}}" onclick="openArticle(${{idx}})">
        <div class="sec-row-inner">
          ${{item.priority===1 ? '<div class="sec-must-dot"></div>' : '<div class="sec-num">'+(i+1)+'</div>'}}
          <div class="sec-content">
            <div class="sec-cat">${{esc(item.cat)}}</div>
            <div class="sec-title">${{esc(item.title)}}</div>
            <div class="sec-source">${{esc(item.source)}}</div>
          </div>
        </div>
      </div>
    `;
  }}).join('');

  area.innerHTML = `
    <div class="sec-header">更多要聞</div>
    <div class="sec-list">${{rows}}</div>
  `;
}}

// ── SIDEBAR MUST LIST ──
function buildMustList() {{
  const list = document.getElementById('must-list');
  list.innerHTML = '';
  const mustItems = DATA.filter(i => i.priority===1);
  if(!mustItems.length) {{
    document.getElementById('must-box').style.display = 'none';
    return;
  }}
  mustItems.slice(0, 8).forEach(item => {{
    const idx = DATA.indexOf(item);
    const el = document.createElement('div');
    el.className = 'must-row';
    el.innerHTML = `
      <div class="must-row-cat">${{esc(item.cat)}}</div>
      <div class="must-row-title">${{esc(item.title)}}</div>
      <div class="must-row-src">${{esc(item.source)}}</div>
    `;
    el.onclick = () => openArticle(idx);
    list.appendChild(el);
  }});
}}

// ── SIDEBAR CATEGORY SUMMARY ──
function buildCatSummary() {{
  const list = document.getElementById('cat-summary-list');
  list.innerHTML = '';
  CAT_ORDER.forEach(cat => {{
    const cnt = DATA.filter(i => i.cat===cat).length;
    if(!cnt) return;
    const must = DATA.filter(i => i.cat===cat && i.priority===1).length;
    const dept = DEPTS[cat] || {{}};
    const el = document.createElement('div');
    el.className = 'cat-sum-row';
    el.innerHTML = `
      <div class="cat-sum-name">${{esc(dept.icon||'')}}\u00a0${{esc(dept.short||cat)}}</div>
      <div class="cat-sum-right">
        <span class="cat-sum-cnt">${{cnt}}</span>
        ${{must ? '<span class="cat-sum-must">'+must+' 必看</span>' : ''}}
      </div>
    `;
    el.onclick = () => openCatView(cat);
    list.appendChild(el);
  }});
}}

// ── ALL NEWS SECTION (grouped by category) ──
function buildAllNews() {{
  const container = document.getElementById('all-news-inner');
  container.innerHTML = '';
  CAT_ORDER.forEach(cat => {{
    const items = DATA.filter(i => i.cat === cat);
    if(!items.length) return;
    const dept = DEPTS[cat] || {{}};

    const section = document.createElement('div');
    section.className = 'news-section';
    section.innerHTML = `
      <div class="ns-header">
        <span class="ns-icon">${{dept.icon||''}}</span>
        <span class="ns-title">${{esc(cat)}}</span>
        <span class="ns-count">${{items.length}} 則</span>
        <button class="ns-more-btn" onclick="openCatView('${{cat}}')">查看全部 →</button>
      </div>
      <div class="ns-grid" id="ns-grid-${{cat.replace(/[^a-z0-9]/gi,'_')}}"></div>
    `;
    container.appendChild(section);

    const grid = section.querySelector('.ns-grid');
    items.slice(0, 6).forEach((item, i) => {{
      const idx = DATA.indexOf(item);
      const card = document.createElement('div');
      card.className = 'ns-card' + (item.priority===1?' ns-card-must':'') + (i===0?' ns-card-lead':'');
      card.innerHTML = `
        ${{item.priority===1 ? '<div class="ns-must-stripe"></div>' : ''}}
        <div class="ns-card-cat">${{esc(item.cat)}}</div>
        <div class="ns-card-title">${{esc(item.title)}}</div>
        ${{i===0 ? '<div class="ns-card-summary">'+esc(item.summary)+'</div>' : ''}}
        <div class="ns-card-src">${{esc(item.source)}}</div>
      `;
      card.onclick = () => openArticle(idx);
      grid.appendChild(card);
    }});
  }});
}}

// ── CATEGORY VIEW ──
function openCatView(cat) {{
  const isMust = cat === 'must';
  const items = isMust ? DATA.filter(i => i.priority===1) : DATA.filter(i => i.cat===cat);
  const title = isMust ? '頭版要聞' : cat;
  document.getElementById('cat-view-title').textContent = title;

  const list = document.getElementById('cat-news-list');
  list.innerHTML = '';
  items.forEach(item => {{
    const idx = DATA.indexOf(item);
    const dept = DEPTS[item.cat] || {{}};
    const row = document.createElement('div');
    row.className = 'list-row' + (item.priority===1?' list-row-must':'');
    row.innerHTML = `
      <div class="list-row-inner">
        ${{item.priority===1 ? '<div class="list-must-bar"></div>' : ''}}
        <div class="list-meta">
          <span class="list-cat-tag">${{esc(item.cat)}}</span>
          ${{item.priority===1 ? '<span class="list-must-tag">頭版</span>' : ''}}
        </div>
        <h3 class="list-title">${{esc(item.title)}}</h3>
        <p class="list-summary">${{esc(item.summary)}}</p>
        <div class="list-footer">
          <span class="list-source">${{esc(item.source)}}</span>
          <span class="list-cta">閱讀全文 →</span>
        </div>
      </div>
    `;
    row.onclick = () => openArticle(idx);
    list.appendChild(row);
  }});

  showView('cat-view');
  setActiveNavBtn(isMust ? 'all' : cat);
}}

// ── ARTICLE VIEW ──
function openArticle(idx) {{
  const item = DATA[idx];
  const dept = DEPTS[item.cat] || {{}};
  document.getElementById('art-cat-tag').textContent = (dept.icon||'') + ' ' + item.cat;
  document.getElementById('art-nav-cat').textContent = item.cat;
  document.getElementById('art-title').textContent = item.title;
  document.getElementById('art-source').textContent = '來源：' + item.source;
  document.getElementById('art-summary').textContent = item.summary;
  document.getElementById('art-summary-box').style.display = item.summary ? 'block' : 'none';
  const rawText = item.full_text || '尚未擷取到內文內容';
  document.getElementById('art-body').innerHTML = rawText.split('\\n\\n').map(p => '<p>' + esc(p.trim()) + '</p>').join('');

  const fromCat = currentView === 'cat-view';
  document.getElementById('art-back-btn').onclick = fromCat
    ? () => showView('cat-view')
    : () => closeArticle();

  showView('article-view');
  history.pushState({{view:'article', idx}}, '');
}}

function closeArticle() {{
  if(history.state && history.state.view === 'cat-view') showView('cat-view');
  else goHome();
}}

// ── VIEW MANAGER ──
var currentView = 'home-view';
function showView(id) {{
  ['home-view','cat-view','article-view'].forEach(v => {{
    document.getElementById(v).style.display = v===id ? 'block' : 'none';
  }});
  currentView = id;
  window.scrollTo(0,0);
}}
function goHome() {{
  showView('home-view');
  setActiveNavBtn('all');
}}

window.addEventListener('popstate', () => {{
  if(currentView==='article-view') closeArticle();
  else if(currentView==='cat-view') goHome();
}});
document.addEventListener('keydown', e => {{
  if(e.key==='Escape') {{
    if(currentView==='article-view') closeArticle();
    else if(currentView==='cat-view') goHome();
  }}
}});

// ── INIT ──
(function() {{
  buildCatNav();
  buildTicker();
  buildTopStory();
  buildSecondary();
  buildMustList();
  buildCatSummary();
  buildAllNews();
  showView('home-view');

  // Fade-in animation
  const observer = new IntersectionObserver(entries => {{
    entries.forEach(e => {{
      if(e.isIntersecting) {{
        e.target.classList.add('is-visible');
        observer.unobserve(e.target);
      }}
    }});
  }}, {{threshold: 0.05, rootMargin: '0px 0px -20px 0px'}});

  document.querySelectorAll('.ns-card, .list-row, .sec-row, .must-row').forEach((el,i) => {{
    el.style.transitionDelay = (i % 6 * 40) + 'ms';
    observer.observe(el);
  }});
}})();
</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8", errors="replace") as f:
        f.write(html)


# ── CSS（日經中文版風格）──────────────────────────────────────
CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --nk-red: #d0011b;
  --nk-red2: #e8001f;
  --nk-black: #111;
  --nk-dark: #1a1a1a;
  --nk-gray1: #333;
  --nk-gray2: #555;
  --nk-gray3: #888;
  --nk-gray4: #aaa;
  --nk-gray5: #ccc;
  --nk-gray6: #e5e5e5;
  --nk-gray7: #f0f0f0;
  --nk-bg: #f7f7f7;
  --nk-white: #fff;
  --nk-border: #ddd;
  --nk-border2: #e8e8e8;
  --nk-must-bg: #fff8f8;
  --nk-serif: 'Noto Serif TC', 'Source Han Serif TC', serif;
  --nk-sans: 'Noto Sans TC', 'Helvetica Neue', sans-serif;
  --nk-max: 1200px;
}

html { scroll-behavior: smooth; font-size: 16px; }
body {
  background: var(--nk-bg);
  font-family: var(--nk-sans);
  color: var(--nk-dark);
  -webkit-font-smoothing: antialiased;
  line-height: 1.6;
}

/* ── UTILITY BAR ── */
#utility-bar {
  background: var(--nk-black);
  border-bottom: 2px solid var(--nk-red);
}
.util-inner {
  max-width: var(--nk-max);
  margin: 0 auto;
  padding: 5px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.util-org { font-size: 11px; color: rgba(255,255,255,0.7); letter-spacing: 0.08em; font-family: var(--nk-sans); font-weight: 500; }
.util-date { font-size: 11px; color: rgba(255,255,255,0.5); }

/* ── MASTHEAD ── */
#masthead {
  background: var(--nk-white);
  border-bottom: 3px solid var(--nk-black);
}
.masthead-inner {
  max-width: var(--nk-max);
  margin: 0 auto;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.masthead-logo { display: flex; align-items: center; gap: 14px; }
.logo-jp {
  font-family: var(--nk-serif);
  font-size: 36px;
  font-weight: 900;
  color: var(--nk-red);
  letter-spacing: 0.02em;
  line-height: 1;
}
.logo-divider {
  width: 1px; height: 40px;
  background: var(--nk-gray5);
}
.logo-sub { display: flex; flex-direction: column; gap: 2px; }
.logo-cn {
  font-family: var(--nk-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--nk-black);
  letter-spacing: 0.05em;
}
.logo-en { font-size: 10px; color: var(--nk-gray3); letter-spacing: 0.1em; text-transform: uppercase; font-weight: 500; }

.masthead-stats { display: flex; align-items: center; gap: 0; }
.stat-pill {
  display: flex; flex-direction: column; align-items: center;
  padding: 4px 20px; cursor: default;
}
.must-pill { cursor: pointer; }
.must-pill:hover .stat-num { color: var(--nk-red2); }
.stat-label { font-size: 10px; color: var(--nk-gray3); letter-spacing: 0.06em; font-weight: 500; margin-bottom: 1px; }
.stat-num { font-size: 24px; font-weight: 700; color: var(--nk-black); font-family: var(--nk-serif); line-height: 1; }
.stat-num.red { color: var(--nk-red); }
.stat-sep { width: 1px; height: 32px; background: var(--nk-gray6); }

/* ── CATEGORY NAV BAR ── */
#cat-nav-bar {
  background: var(--nk-white);
  border-bottom: 1px solid var(--nk-border);
  position: sticky; top: 0; z-index: 900;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.cat-nav-inner {
  max-width: var(--nk-max);
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  gap: 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.cat-nav-inner::-webkit-scrollbar { display: none; }
.cat-btn {
  padding: 10px 18px;
  border: none;
  background: none;
  font-size: 13px;
  font-weight: 500;
  font-family: var(--nk-sans);
  color: var(--nk-gray2);
  cursor: pointer;
  white-space: nowrap;
  border-bottom: 3px solid transparent;
  transition: color 0.15s, border-color 0.15s;
  letter-spacing: 0.02em;
}
.cat-btn:hover { color: var(--nk-black); }
.cat-btn.active { color: var(--nk-red); border-bottom-color: var(--nk-red); font-weight: 700; }

/* ── TICKER ── */
.ticker-wrap {
  background: var(--nk-black);
  display: flex;
  align-items: center;
  overflow: hidden;
  height: 34px;
  border-bottom: 1px solid #222;
}
.ticker-label {
  flex-shrink: 0;
  background: var(--nk-red);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 0 14px;
  height: 100%;
  display: flex; align-items: center;
  letter-spacing: 0.1em;
  font-family: var(--nk-sans);
}
.ticker-track {
  display: flex;
  align-items: center;
  white-space: nowrap;
  animation: tickerScroll 40s linear infinite;
  padding-left: 20px;
}
.ticker-track:hover { animation-play-state: paused; }
@keyframes tickerScroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
.ticker-item {
  font-size: 12px;
  color: rgba(255,255,255,0.85);
  cursor: pointer;
  transition: color 0.15s;
  font-family: var(--nk-sans);
}
.ticker-item:hover { color: #fff; text-decoration: underline; }
.ticker-sep { color: rgba(255,255,255,0.25); margin: 0 16px; font-size: 11px; }

/* ── MAIN LAYOUT ── */
.main-container {
  max-width: var(--nk-max);
  margin: 0 auto;
  padding: 24px 20px;
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 24px;
  align-items: start;
}

/* ── TOP STORY ── */
.top-story {
  background: var(--nk-white);
  border: 1px solid var(--nk-border);
  border-top: 3px solid var(--nk-black);
  padding: 28px 32px;
  cursor: pointer;
  transition: box-shadow 0.2s;
  position: relative;
  overflow: hidden;
}
.top-story:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
.ts-must-bar {
  position: absolute; top: 0; left: 0; right: 0; height: 3px;
  background: var(--nk-red);
}
.ts-cat-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.ts-cat-tag {
  font-size: 11px; font-weight: 700;
  color: var(--nk-red);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-family: var(--nk-sans);
  padding: 2px 8px;
  border: 1px solid var(--nk-red);
}
.ts-must-badge {
  font-size: 10px; font-weight: 700;
  background: var(--nk-red); color: #fff;
  padding: 2px 8px; letter-spacing: 0.06em;
}
.ts-headline {
  font-family: var(--nk-serif);
  font-size: 26px; font-weight: 700;
  line-height: 1.45; color: var(--nk-black);
  margin-bottom: 14px; letter-spacing: -0.01em;
}
.ts-summary {
  font-size: 14px; color: var(--nk-gray2);
  line-height: 1.8; margin-bottom: 20px;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.ts-footer {
  display: flex; align-items: center; justify-content: space-between;
  border-top: 1px solid var(--nk-gray6); padding-top: 12px;
}
.ts-source { font-size: 12px; color: var(--nk-gray4); }
.ts-cta { font-size: 13px; color: var(--nk-red); font-weight: 600; }

/* ── SECTION DIVIDER ── */
.section-divider {
  height: 1px; background: var(--nk-border);
  margin: 20px 0;
}

/* ── SECONDARY NEWS ── */
.sec-header {
  font-size: 11px; font-weight: 700;
  letter-spacing: 0.1em; color: var(--nk-gray3);
  text-transform: uppercase;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--nk-black);
  margin-bottom: 0;
}
.sec-list { background: var(--nk-white); border: 1px solid var(--nk-border); border-top: none; }
.sec-row {
  border-bottom: 1px solid var(--nk-border2);
  cursor: pointer;
  transition: background 0.15s;
}
.sec-row:last-child { border-bottom: none; }
.sec-row:hover { background: var(--nk-gray7); }
.sec-must { background: var(--nk-must-bg); }
.sec-row-inner { display: flex; align-items: flex-start; gap: 14px; padding: 14px 18px; }
.sec-num {
  flex-shrink: 0; width: 22px; height: 22px;
  background: var(--nk-black); color: #fff;
  font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--nk-sans);
  margin-top: 2px;
}
.sec-must-dot {
  flex-shrink: 0; width: 8px; height: 8px;
  background: var(--nk-red); border-radius: 50%;
  margin-top: 7px;
}
.sec-content { flex: 1; }
.sec-cat { font-size: 10px; color: var(--nk-red); font-weight: 700; letter-spacing: 0.06em; margin-bottom: 4px; }
.sec-title { font-size: 14px; font-weight: 600; color: var(--nk-black); line-height: 1.45; font-family: var(--nk-serif); margin-bottom: 4px; }
.sec-source { font-size: 11px; color: var(--nk-gray4); }

/* ── SIDEBAR ── */
.col-sidebar { display: flex; flex-direction: column; gap: 20px; }
.sidebar-box {
  background: var(--nk-white);
  border: 1px solid var(--nk-border);
  border-top: 3px solid var(--nk-black);
}
.sidebar-box-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--nk-border);
  display: flex; align-items: baseline; gap: 10px;
  background: var(--nk-gray7);
}
.sbox-label {
  font-size: 13px; font-weight: 700;
  color: var(--nk-black); letter-spacing: 0.04em;
  font-family: var(--nk-sans);
}
.red-label { color: var(--nk-red); }
.sbox-sub { font-size: 11px; color: var(--nk-gray4); }

/* Must list */
.must-row {
  padding: 12px 16px;
  border-bottom: 1px solid var(--nk-border2);
  cursor: pointer; transition: background 0.15s;
  opacity: 0; transform: translateY(8px);
  transition: opacity 0.3s ease, transform 0.3s ease, background 0.15s;
}
.must-row.is-visible { opacity: 1; transform: translateY(0); }
.must-row:last-child { border-bottom: none; }
.must-row:hover { background: var(--nk-must-bg); }
.must-row-cat { font-size: 10px; color: var(--nk-red); font-weight: 700; letter-spacing: 0.06em; margin-bottom: 3px; }
.must-row-title { font-size: 13px; font-weight: 600; color: var(--nk-black); line-height: 1.5; font-family: var(--nk-serif); margin-bottom: 4px; }
.must-row-src { font-size: 10px; color: var(--nk-gray4); }

/* Category summary */
.cat-sum-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-bottom: 1px solid var(--nk-border2);
  cursor: pointer; transition: background 0.15s;
}
.cat-sum-row:last-child { border-bottom: none; }
.cat-sum-row:hover { background: var(--nk-gray7); }
.cat-sum-name { font-size: 13px; font-weight: 500; color: var(--nk-dark); }
.cat-sum-right { display: flex; align-items: center; gap: 8px; }
.cat-sum-cnt { font-size: 13px; font-weight: 700; color: var(--nk-black); }
.cat-sum-must { font-size: 10px; background: var(--nk-red); color: #fff; padding: 1px 6px; font-weight: 700; }

/* ── ALL NEWS SECTION ── */
.all-news-section {
  background: var(--nk-bg);
  border-top: 1px solid var(--nk-border);
  padding: 32px 0 60px;
}
.all-news-inner {
  max-width: var(--nk-max);
  margin: 0 auto;
  padding: 0 20px;
}
.news-section { margin-bottom: 40px; }
.ns-header {
  display: flex; align-items: center; gap: 10px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--nk-black);
  margin-bottom: 16px;
}
.ns-icon { font-size: 16px; }
.ns-title { font-size: 16px; font-weight: 700; color: var(--nk-black); font-family: var(--nk-serif); flex: 1; }
.ns-count { font-size: 12px; color: var(--nk-gray4); font-weight: 400; }
.ns-more-btn {
  font-size: 12px; color: var(--nk-red); font-weight: 600;
  background: none; border: 1px solid var(--nk-red); padding: 3px 10px;
  cursor: pointer; font-family: var(--nk-sans); transition: all 0.15s;
}
.ns-more-btn:hover { background: var(--nk-red); color: #fff; }

.ns-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--nk-border);
  border: 1px solid var(--nk-border);
}
.ns-card {
  background: var(--nk-white);
  padding: 16px 18px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
  opacity: 0; transform: translateY(10px);
  transition: opacity 0.35s ease, transform 0.35s ease, background 0.15s;
}
.ns-card.is-visible { opacity: 1; transform: translateY(0); }
.ns-card:hover { background: var(--nk-gray7); }
.ns-card-must { background: var(--nk-must-bg); }
.ns-card-lead { grid-column: 1 / -1; border-bottom: 1px solid var(--nk-border); }
.ns-must-stripe {
  position: absolute; top: 0; left: 0; width: 3px; height: 100%;
  background: var(--nk-red);
}
.ns-card-cat { font-size: 10px; color: var(--nk-red); font-weight: 700; letter-spacing: 0.06em; margin-bottom: 5px; }
.ns-card-title { font-size: 14px; font-weight: 600; color: var(--nk-black); line-height: 1.5; font-family: var(--nk-serif); margin-bottom: 6px; }
.ns-card-lead .ns-card-title { font-size: 18px; }
.ns-card-summary { font-size: 13px; color: var(--nk-gray2); line-height: 1.7; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ns-card-src { font-size: 11px; color: var(--nk-gray4); }

/* ── PAGE NAV (cat + article views) ── */
.page-nav {
  background: var(--nk-white);
  border-bottom: 1px solid var(--nk-border);
  padding: 10px 20px;
  display: flex; align-items: center; gap: 16px;
  position: sticky; top: 44px; z-index: 800;
}
.page-back-btn {
  background: none; border: none; font-size: 13px; color: var(--nk-red);
  font-weight: 600; cursor: pointer; font-family: var(--nk-sans);
  padding: 4px 0; transition: opacity 0.15s;
}
.page-back-btn:hover { opacity: 0.7; }
.page-nav-title { font-size: 14px; font-weight: 700; color: var(--nk-black); font-family: var(--nk-serif); }

/* ── CATEGORY VIEW LIST ── */
.cat-view-inner {
  max-width: 800px; margin: 0 auto; padding: 24px 20px 80px;
}
.list-row {
  background: var(--nk-white);
  border: 1px solid var(--nk-border);
  border-top: none;
  cursor: pointer; transition: background 0.15s;
  position: relative;
  opacity: 0; transform: translateY(8px);
  transition: opacity 0.3s ease, transform 0.3s ease, background 0.15s;
}
.list-row.is-visible { opacity: 1; transform: translateY(0); }
.list-row:first-child { border-top: 2px solid var(--nk-black); }
.list-row:hover { background: var(--nk-gray7); }
.list-row-must { background: var(--nk-must-bg); }
.list-row-inner { padding: 20px 24px; position: relative; }
.list-must-bar { position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--nk-red); }
.list-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.list-cat-tag { font-size: 10px; font-weight: 700; color: var(--nk-red); letter-spacing: 0.08em; border: 1px solid var(--nk-red); padding: 1px 7px; }
.list-must-tag { font-size: 10px; font-weight: 700; background: var(--nk-red); color: #fff; padding: 1px 7px; }
.list-title { font-size: 18px; font-weight: 700; font-family: var(--nk-serif); color: var(--nk-black); line-height: 1.5; margin-bottom: 8px; }
.list-summary { font-size: 13px; color: var(--nk-gray2); line-height: 1.75; margin-bottom: 12px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.list-footer { display: flex; justify-content: space-between; align-items: center; }
.list-source { font-size: 11px; color: var(--nk-gray4); }
.list-cta { font-size: 12px; color: var(--nk-red); font-weight: 600; }

/* ── ARTICLE VIEW ── */
.article-container { max-width: 720px; margin: 0 auto; padding: 40px 20px 100px; }
.article-header { border-bottom: 1px solid var(--nk-border); padding-bottom: 28px; margin-bottom: 32px; }
.art-cat-tag {
  display: inline-block;
  font-size: 11px; font-weight: 700; color: var(--nk-red);
  border: 1px solid var(--nk-red); padding: 2px 10px;
  letter-spacing: 0.08em; margin-bottom: 14px;
}
.art-headline {
  font-family: var(--nk-serif);
  font-size: 30px; font-weight: 700;
  line-height: 1.5; color: var(--nk-black);
  margin-bottom: 16px; letter-spacing: -0.01em;
}
.art-meta { margin-bottom: 20px; }
.art-source { font-size: 12px; color: var(--nk-gray4); }
.art-summary-box {
  background: var(--nk-gray7);
  border-left: 3px solid var(--nk-red);
  padding: 16px 20px;
}
.art-summary-label { font-size: 11px; font-weight: 700; color: var(--nk-red); letter-spacing: 0.08em; margin-bottom: 8px; }
.art-summary-text { font-size: 14px; color: var(--nk-gray1); line-height: 1.8; }
.art-body p {
  font-size: 16px; line-height: 2; color: var(--nk-dark);
  margin-bottom: 1.6em; font-family: var(--nk-serif);
  letter-spacing: 0.02em;
}
.art-body p:last-child { margin-bottom: 0; }

/* ── RESPONSIVE ── */
@media (max-width: 960px) {
  .main-container { grid-template-columns: 1fr; }
  .col-sidebar { display: none; }
  .ns-grid { grid-template-columns: repeat(2,1fr); }
}
@media (max-width: 600px) {
  .logo-jp { font-size: 28px; }
  .logo-cn { font-size: 15px; }
  .ts-headline { font-size: 20px; }
  .ns-grid { grid-template-columns: 1fr; }
  .art-headline { font-size: 22px; }
  .art-body p { font-size: 15px; }
  .masthead-stats { display: none; }
}
"""

if __name__ == "__main__":
    run_dashboard()
