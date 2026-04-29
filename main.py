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

# ── 2. 工具函式 ──────────────────────────────────────────────
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

        def is_toc_table(t):
            news_sources = ['時報','日報','聯合','自由','中時','工商','經濟','蘋果','鏡','報']
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

                if re.match(r'^\d{2}-', c1) and not c2:
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

# ── 4. HTML 生成 ─────────────────────────────────────────────
def generate_html(data):
    p_rank = {1: 0, 0: 1}
    data_sorted = sorted(data, key=lambda x: p_rank.get(x["priority"], 1))
    data_json = json.dumps(data_sorted, ensure_ascii=False)
    dept_info = {k: {"icon": v["icon"], "short": v["short"]} for k,v in DEPARTMENTS.items()}
    dept_json = json.dumps(dept_info, ensure_ascii=False)
    cat_order_json = json.dumps(CATEGORY_ORDER, ensure_ascii=False)
    
    must_total = sum(1 for i in data_sorted if i["priority"] == 1)

    # HTML 模板使用 .replace 避免 f-string 衝突
    html_template = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EPC 經濟情報 — 國家發展委員會</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@400;600;700;900&family=Noto+Sans+TC:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
{{CSS_CONTENT}}
</style>
</head>
<body>

<div id="utility-bar">
  <div class="util-inner">
    <span class="util-org">國家發展委員會 · 經濟發展處</span>
    <span class="util-date" id="util-date"></span>
  </div>
</div>

<header id="masthead">
  <div class="masthead-inner">
    <div class="masthead-logo">
      <span class="logo-main">EPC</span>
      <div class="logo-divider"></div>
      <div class="logo-text">
        <span class="logo-cn">經濟情報</span>
        <span class="logo-en">Economic Press Clipping</span>
      </div>
    </div>
    <div class="masthead-stats">
      <div class="stat-item must-stat" id="must-stat-btn">
        <div class="stat-num red">{{MUST_TOTAL}}</div>
        <div class="stat-label">頭版要聞</div>
      </div>
      <div class="stat-sep"></div>
      <div class="stat-item">
        <div class="stat-num">{{TOTAL_COUNT}}</div>
        <div class="stat-label">今日總則</div>
      </div>
    </div>
  </div>
</header>

<nav id="section-nav">
  <div class="section-nav-inner" id="section-nav-inner">
    <button class="nav-btn active" data-cat="all" onclick="goHome()">全部</button>
  </div>
</nav>

<div id="home-view">
  <div class="ticker-bar" id="ticker-bar">
    <span class="ticker-tag">頭版</span>
    <div class="ticker-body">
      <div class="ticker-track" id="ticker-track"></div>
    </div>
  </div>

  <div class="layout-wrapper">
    <div class="layout-main">
      <div id="top-story-wrap"></div>
      <div id="sub-news-wrap"></div>
    </div>
    <aside class="layout-sidebar">
      <div class="sidebar-block" id="must-block">
        <div class="sb-header red-header">
          <span class="sb-title">今日必看</span>
          <span class="sb-sub">頭版 · 重點領域</span>
        </div>
        <div id="must-list"></div>
      </div>
      <div class="sidebar-block">
        <div class="sb-header"><span class="sb-title">分類總覽</span></div>
        <div id="cat-overview"></div>
      </div>
    </aside>
  </div>
  <div class="all-section">
    <div class="all-section-inner" id="all-section-inner"></div>
  </div>
</div>

<div id="cat-view" style="display:none;">
  <div class="sub-nav">
    <button class="back-btn" onclick="goHome()">&#8592; 返回首頁</button>
    <span class="sub-nav-title" id="cat-view-title"></span>
  </div>
  <div class="list-wrapper"><div id="cat-list"></div></div>
</div>

<div id="article-view" style="display:none;">
  <div class="sub-nav">
    <button class="back-btn" id="art-back-btn">&#8592; 返回</button>
    <span class="sub-nav-title" id="art-nav-cat"></span>
  </div>
  <div class="article-wrapper">
    <div class="art-cat-label" id="art-cat-label"></div>
    <h1 class="art-title" id="art-title"></h1>
    <div class="art-meta"><span id="art-source"></span></div>
    <div class="art-summary-block" id="art-summary-block">
      <div class="art-summary-label">▌ 摘要重點</div>
      <p class="art-summary-text" id="art-summary"></p>
    </div>
    <div class="art-body" id="art-body"></div>
  </div>
</div>

<script>
const DATA = {{DATA_JSON}};
const DEPTS = {{DEPT_JSON}};
const CAT_ORDER = {{CAT_ORDER_JSON}};

(function() {
  const now = new Date();
  const roc = now.getFullYear() - 1911;
  const days = ['日','一','二','三','四','五','六'];
  document.getElementById('util-date').textContent = 
    `民國${roc}年${now.getMonth()+1}月${now.getDate()}日 星期${days[now.getDay()]}`;
})();

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function buildNav() {
  const bar = document.getElementById('section-nav-inner');
  CAT_ORDER.forEach(cat => {
    const btn = document.createElement('button');
    btn.className = 'nav-btn';
    btn.dataset.cat = cat;
    btn.textContent = DEPTS[cat] ? DEPTS[cat].short : cat;
    btn.onclick = () => openCatView(cat);
    bar.appendChild(btn);
  });
  document.getElementById('must-stat-btn').onclick = () => openCatView('must');
}

function buildTicker() {
  const items = DATA.filter(i => i.priority === 1);
  const bar = document.getElementById('ticker-bar');
  if (!items.length) { bar.style.display = 'none'; return; }
  const track = document.getElementById('ticker-track');
  const html = items.map(item => `<span class="t-item" onclick="openArticle(${DATA.indexOf(item)})">${esc(item.title)}</span><span class="t-sep">／</span>`).join('');
  track.innerHTML = html + html;
}

function buildTopStory() {
  const wrap = document.getElementById('top-story-wrap');
  const top = DATA.find(i => i.priority === 1) || DATA[0];
  if (!top) return;
  const idx = DATA.indexOf(top);
  wrap.innerHTML = `
    <div class="top-story" onclick="openArticle(${idx})">
      <div class="${top.priority===1?'ts-red-bar':'ts-black-bar'}"></div>
      <div class="ts-meta">
        <span class="ts-cat">${esc(top.cat)}</span>
        ${top.priority===1?'<span class="ts-badge">頭版要聞</span>':''}
      </div>
      <h2 class="ts-title">${esc(top.title)}</h2>
      <p class="ts-summary">${esc(top.summary)}</p>
      <div class="ts-footer"><span class="ts-src">${esc(top.source)}</span><span class="ts-more">閱讀全文 →</span></div>
    </div>`;
}

function buildSubNews() {
  const wrap = document.getElementById('sub-news-wrap');
  const items = DATA.slice(1, 8);
  if (!items.length) return;
  const rows = items.map((item, i) => `
    <div class="sub-row ${item.priority===1?'sub-must':''}" onclick="openArticle(${DATA.indexOf(item)})">
      ${item.priority===1?'<div class="sub-dot-red"></div>':'<div class="sub-num">'+(i+1)+'</div>'}
      <div class="sub-body">
        <div class="sub-cat">${esc(item.cat)}</div>
        <div class="sub-title">${esc(item.title)}</div>
        <div class="sub-src">${esc(item.source)}</div>
      </div>
    </div>`).join('');
  wrap.innerHTML = `<div class="sub-header">更多要聞</div><div class="sub-list">${rows}</div>`;
}

function buildMustList() {
  const list = document.getElementById('must-list');
  const items = DATA.filter(i => i.priority === 1);
  if (!items.length) { document.getElementById('must-block').style.display='none'; return; }
  items.slice(0,8).forEach(item => {
    const el = document.createElement('div');
    el.className = 'must-item';
    el.innerHTML = `<div class="mi-cat">${esc(item.cat)}</div><div class="mi-title">${esc(item.title)}</div><div class="mi-src">${esc(item.source)}</div>`;
    el.onclick = () => openArticle(DATA.indexOf(item));
    list.appendChild(el);
  });
}

function buildCatOverview() {
  const wrap = document.getElementById('cat-overview');
  CAT_ORDER.forEach(cat => {
    const items = DATA.filter(i => i.cat===cat);
    if (!items.length) return;
    const must = items.filter(i => i.priority===1).length;
    const el = document.createElement('div');
    el.className = 'co-row';
    el.innerHTML = `<span class="co-name">${esc((DEPTS[cat].icon||'')+' '+DEPTS[cat].short)}</span>
      <span class="co-right"><span class="co-cnt">${items.length}</span>${must?`<span class="co-must">${must}必看</span>`:''}</span>`;
    el.onclick = () => openCatView(cat);
    wrap.appendChild(el);
  });
}

function buildAllSections() {
  const container = document.getElementById('all-section-inner');
  CAT_ORDER.forEach(cat => {
    const items = DATA.filter(i => i.cat===cat);
    if (!items.length) return;
    const sec = document.createElement('div');
    sec.className = 'cat-section';
    sec.innerHTML = `<div class="cs-header"><span class="cs-icon">${DEPTS[cat].icon}</span><span class="cs-title">${esc(cat)}</span>
      <button class="cs-more" onclick="openCatView('${cat}')">查看全部 →</button></div><div class="cs-grid"></div>`;
    const grid = sec.querySelector('.cs-grid');
    items.slice(0,6).forEach((item, i) => {
      const card = document.createElement('div');
      card.className = 'cs-card ' + (item.priority===1?'cs-must ':'') + (i===0?'cs-lead':'');
      card.innerHTML = `${item.priority===1?'<div class="cs-red-stripe"></div>':''}
        <div class="cs-card-cat">${esc(item.cat)}</div><div class="cs-card-title">${esc(item.title)}</div>
        ${i===0?`<div class="cs-card-summary">${esc(item.summary)}</div>`:''}<div class="cs-card-src">${esc(item.source)}</div>`;
      card.onclick = () => openArticle(DATA.indexOf(item));
      grid.appendChild(card);
    });
    container.appendChild(sec);
  });
}

function openCatView(cat) {
  const isMust = cat==='must';
  const items = isMust ? DATA.filter(i=>i.priority===1) : DATA.filter(i=>i.cat===cat);
  document.getElementById('cat-view-title').textContent = isMust ? '頭版要聞' : cat;
  const list = document.getElementById('cat-list');
  list.innerHTML = items.map(item => `
    <div class="list-row ${item.priority===1?'list-must':''}" onclick="openArticle(${DATA.indexOf(item)})">
      <div class="lr-inner">
        ${item.priority===1?'<div class="lr-red-bar"></div>':''}
        <div class="lr-meta"><span class="lr-cat">${esc(item.cat)}</span>${item.priority===1?'<span class="lr-must-tag">頭版</span>':''}</div>
        <div class="lr-title">${esc(item.title)}</div>
        <div class="lr-summary">${esc(item.summary)}</div>
        <div class="lr-footer"><span class="lr-src">${esc(item.source)}</span><span class="lr-cta">閱讀全文 →</span></div>
      </div>
    </div>`).join('');
  showView('cat-view');
}

function openArticle(idx) {
  const item = DATA[idx];
  const dept = DEPTS[item.cat] || {};
  document.getElementById('art-cat-label').textContent = (dept.icon||'') + ' ' + item.cat;
  document.getElementById('art-nav-cat').textContent = item.cat;
  document.getElementById('art-title').textContent = item.title;
  document.getElementById('art-source').textContent = '來源：' + item.source;
  document.getElementById('art-summary').textContent = item.summary;
  document.getElementById('art-body').innerHTML = (item.full_text || '尚未擷取到內文內容').split('\\n\\n').map(p => `<p>${esc(p.trim())}</p>`).join('');
  showView('article-view');
}

function showView(id) {
  ['home-view','cat-view','article-view'].forEach(v => document.getElementById(v).style.display = v===id?'block':'none');
  ['masthead','section-nav','utility-bar'].forEach(v => document.getElementById(v).style.display = id==='home-view'?'block':'none');
  window.scrollTo(0,0);
}
function goHome() { showView('home-view'); }

(function() {
  buildNav(); buildTicker(); buildTopStory(); buildSubNews(); buildMustList(); buildCatOverview(); buildAllSections();
})();
</script>
</body>
</html>"""

    # 執行內容替換
    final_html = html_template.replace("{{CSS_CONTENT}}", CSS) \
                               .replace("{{DATA_JSON}}", data_json) \
                               .replace("{{DEPT_JSON}}", dept_json) \
                               .replace("{{CAT_ORDER_JSON}}", cat_order_json) \
                               .replace("{{MUST_TOTAL}}", str(must_total)) \
                               .replace("{{TOTAL_COUNT}}", str(len(data_sorted)))

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(final_html)

# ── 5. CSS 定義 ──────────────────────────────────────────────
CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --red: #d0011b; --black: #111111; --dark: #1a1a1a;
  --g1: #333; --g2: #555; --g3: #777; --g4: #999; --g5: #bbb; --g6: #ddd; --g7: #eeeeee; --g8: #f5f5f5;
  --white: #ffffff; --mustbg: #fff8f8;
  --serif: 'Noto Serif TC', serif; --sans: 'Noto Sans TC', sans-serif; --wrap: 1160px;
}
body { background: var(--g8); font-family: var(--sans); color: var(--dark); line-height: 1.6; }
#utility-bar { background: var(--black); border-bottom: 2px solid var(--red); }
.util-inner { max-width: var(--wrap); margin: 0 auto; padding: 5px 20px; display: flex; justify-content: space-between; font-size: 11px; color: rgba(255,255,255,.5); }
#masthead { background: var(--white); border-bottom: 3px solid var(--black); }
.masthead-inner { max-width: var(--wrap); margin: 0 auto; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }
.logo-main { font-family: var(--serif); font-size: 38px; font-weight: 900; color: var(--red); }
.logo-cn { font-family: var(--serif); font-size: 18px; font-weight: 700; color: var(--black); }
.masthead-stats { display: flex; align-items: center; text-align: center; }
.stat-item { padding: 0 15px; }
.stat-num { font-family: var(--serif); font-size: 24px; font-weight: 700; }
.stat-num.red { color: var(--red); }
.stat-label { font-size: 10px; color: var(--g4); }
#section-nav { background: var(--white); border-bottom: 1px solid var(--g6); position: sticky; top: 0; z-index: 99; }
.section-nav-inner { max-width: var(--wrap); margin: 0 auto; display: flex; overflow-x: auto; }
.nav-btn { padding: 12px 15px; border: none; background: none; font-size: 13px; font-weight: 500; color: var(--g3); cursor: pointer; white-space: nowrap; border-bottom: 3px solid transparent; }
.nav-btn.active { color: var(--red); border-bottom-color: var(--red); font-weight: 700; }
.ticker-bar { background: var(--black); display: flex; height: 32px; align-items: center; overflow: hidden; }
.ticker-tag { background: var(--red); color: white; font-size: 11px; padding: 0 10px; height: 100%; display: flex; align-items: center; }
.ticker-track { display: flex; white-space: nowrap; animation: scroll 40s linear infinite; }
@keyframes scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
.t-item { color: rgba(255,255,255,.8); font-size: 12px; padding: 0 10px; cursor: pointer; }
.layout-wrapper { max-width: var(--wrap); margin: 20px auto; display: grid; grid-template-columns: 1fr 300px; gap: 20px; padding: 0 20px; }
.top-story { background: var(--white); padding: 25px; border: 1px solid var(--g6); cursor: pointer; position: relative; }
.ts-red-bar { position: absolute; top: 0; left: 0; right: 0; height: 4px; background: var(--red); }
.ts-black-bar { position: absolute; top: 0; left: 0; right: 0; height: 4px; background: var(--black); }
.ts-title { font-family: var(--serif); font-size: 24px; margin: 10px 0; }
.ts-summary { font-size: 14px; color: var(--g2); display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.sub-header { font-size: 12px; font-weight: 700; color: var(--g4); margin: 15px 0 5px; }
.sub-list { background: var(--white); border: 1px solid var(--g6); }
.sub-row { display: flex; border-bottom: 1px solid #eee; cursor: pointer; padding: 10px; }
.sub-num { width: 25px; color: var(--g5); font-weight: 700; }
.sub-dot-red::after { content: '●'; color: var(--red); font-size: 10px; padding-right: 10px; }
.sub-title { font-size: 14px; font-weight: 600; font-family: var(--serif); }
.sidebar-block { background: var(--white); border: 1px solid var(--g6); border-top: 3px solid var(--black); margin-bottom: 20px; }
.sb-header { padding: 8px 12px; background: var(--g8); border-bottom: 1px solid var(--g6); }
.sb-title { font-size: 13px; font-weight: 700; }
.must-item { padding: 10px 12px; border-bottom: 1px solid #eee; cursor: pointer; }
.mi-title { font-size: 13px; font-family: var(--serif); font-weight: 600; }
.cat-section { margin: 40px auto; max-width: var(--wrap); padding: 0 20px; }
.cs-header { display: flex; align-items: center; border-bottom: 2px solid var(--black); padding-bottom: 5px; }
.cs-title { font-family: var(--serif); font-size: 18px; font-weight: 700; flex: 1; }
.cs-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; background: var(--g6); border: 1px solid var(--g6); }
.cs-card { background: var(--white); padding: 15px; cursor: pointer; }
.cs-lead { grid-column: 1 / -1; }
.cs-card-title { font-family: var(--serif); font-size: 15px; font-weight: 600; }
.sub-nav { background: var(--white); padding: 10px 20px; border-bottom: 1px solid var(--g6); position: sticky; top: 0; display: flex; align-items: center; }
.article-wrapper { max-width: 700px; margin: 40px auto; padding: 0 20px; }
.art-title { font-family: var(--serif); font-size: 28px; line-height: 1.4; margin-bottom: 20px; }
.art-body p { margin-bottom: 20px; font-size: 17px; font-family: var(--serif); }
"""

if __name__ == "__main__":
    run_dashboard()
