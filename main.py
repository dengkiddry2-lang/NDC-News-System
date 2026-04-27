import pdfplumber
import os
import json
import re
from collections import Counter

# ── 1. 分類定義 ──────────────────────────────────────────────
DEPARTMENTS = {
    "社論與評論觀點": {
        "icon": "📝", "short": "社論",
        "keywords": ["社論","時評","社評","專欄","論壇","觀點","評論","名家","經濟教室","縱橫天下","自由廣場"]
    },
    "國際機構與智庫報告": {
        "icon": "📘", "short": "智庫",
        "keywords": ["IMF","OECD","World Bank","WTO","智庫","Brookings","PIIE","BIS","ADB","WEF","聯合國","世界銀行","國際貨幣"]
    },
    "地緣政治與國際衝突": {
        "icon": "🌏", "short": "地緣",
        "keywords": ["戰爭","衝突","制裁","美伊","俄烏","荷莫茲","伊朗","烏克蘭","關稅","川普","貿易戰","地緣","槍響","槍擊","遇襲","外交"]
    },
    "國際金融與貨幣政策": {
        "icon": "🌐", "short": "金融",
        "keywords": ["Fed","FOMC","聯準會","利率決策","升息","降息","鮑爾","ECB","BOJ","英格蘭銀行","央行週","超級央行","美債","美元指數","非農","CPI","核心通膨","PMI","ISM","人民幣","日圓","歐元","英鎊","匯率"]
    },
    "台灣總體經濟與數據": {
        "icon": "📊", "short": "總經",
        "keywords": ["主計","主計總處","GDP","景氣燈號","景氣","物價","通膨","失業率","薪資","外銷訂單","出口統計","進口統計","海關","貿易統計","稅收","超徵","出生率","少子化","高齡化","人口統計","消費者信心","製造業PMI","非製造業"]
    },
    "台灣產業與投資動向": {
        "icon": "🏭", "short": "產業",
        "keywords": ["AI","半導體","台積電","台積","聯發科","聯電","鴻海","台達電","廣達","緯創","英業達","資本支出","供應鏈","算力","伺服器","CoWoS","先進封裝","製程","晶片","離岸風電","綠能","電動車","ASIC","TPU","GPU"]
    },
    "台灣政府與政策訊息": {
        "icon": "🏛️", "short": "政策",
        "keywords": ["國發會","行政院","總統府","經濟部","財政部","金管會","國科會","央行","衛福部","內政部","院會","政院","法案","預算","補助","政策","施政","法規","條例","立法院","立委","修法"]
    },
}

CATEGORY_ORDER = [
    "社論與評論觀點","國際機構與智庫報告","地緣政治與國際衝突",
    "國際金融與貨幣政策","台灣總體經濟與數據","台灣產業與投資動向","台灣政府與政策訊息",
]

MUST_READ_KEYS = ["Fed","FOMC","鮑爾","主計","GDP","景氣燈號","衝突","戰爭","利率決議","升息","降息","外銷訂單","超徵","荷莫茲"]

# 頭版版面識別（各報 A01 / AA01 等）
FRONT_PAGE_PATTERNS = ["A01", "AA01"]



# 頭版版面識別（各報 A01 / AA01 等）
FRONT_PAGE_PATTERNS = ["A01", "AA01"]

def is_front_page(source):
    """判斷是否為各報頭版"""
    return any(p in source for p in FRONT_PAGE_PATTERNS)

# 頭版新聞（A01）若符合分類關鍵字自動升必看，但排除這些社會事件詞

def is_frontpage(source):
    """判斷是否為頭版新聞"""
    return "A01" in source or "AA01" in source

def get_priority(title, source, found_cat):
    """
    優先級判定：
    - A01 頭版 且 符合分類 → 必看 (priority=1)
    - 標題含 MUST_READ_KEYS → 必看
    - 其他 → 一般 (priority=0)
    """
    if is_frontpage(source) and found_cat is not None:
        return 1
    if any(k in title for k in MUST_READ_KEYS):
        return 1
    return 0

NON_ECON_TITLE_KEYS = ["大麻","毒品","詐騙","竊盜","農業","旱情","廚餘","豬","漁業","失智","長照","安樂死","安寧","防癌","觀光旅遊","演唱會","房價指數","租屋"]
NON_ECON_SECTIONS = ["焦點新聞","社會","地方","體育","娛樂","影視","生活","健康","農業","司法","法庭","影劇","副刊","旅遊","美食","寵物","星座"]
ALL_ECON_KEYS = set()
for dept in DEPARTMENTS.values():
    ALL_ECON_KEYS.update(dept["keywords"])
ALL_ECON_KEYS.update(MUST_READ_KEYS)

def should_skip(title, source):
    if any(k in title for k in NON_ECON_TITLE_KEYS):
        return True
    if any(sec in source for sec in NON_ECON_SECTIONS):
        if not any(k in title for k in ALL_ECON_KEYS):
            return True
    return False

# ── 2. PDF 解析 ──────────────────────────────────────────────
NOISE_PREFIXES = ["來源","作者","版面","日期","出處","記者","編輯","回到目錄","本報訊"]

def is_noise_line(line):
    if line.isdigit(): return True
    return any(line.startswith(p) for p in NOISE_PREFIXES)

def clean_text_blocks(text_list):
    if not text_list: return ""
    merged = ""
    for line in text_list:
        line = line.strip()
        if not line or is_noise_line(line): continue
        if re.search(r'報導】$|記者.{0,10}報導', line): continue
        if line.isdigit(): continue
        if not merged:
            merged = line
        elif merged[-1] in ("。","！","？","；","」","\u201d","…"):
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
    return "\n\n".join(cleaned)

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
                if re.search(r'[報導綜合外電]+】\s*$|^\w+\/\w+報導】', lines[body_start]):
                    body_start += 1
                else: break
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
        for page in pdf.pages:
            table = page.extract_table()
            if not table: continue
            def is_toc_table(t):
                news_sources = ['時報','日報','聯合','自由','中時','工商','蘋果','鏡','報']
                for r in t:
                    if not r or len(r) < 2: continue
                    col2 = str(r[1] or '').strip()
                    col3 = str(r[2] or '').strip() if len(r) > 2 else ''
                    if len(col2) > 5 and any(s in col3 for s in news_sources): return True
                return False
            if not is_toc_table(table): continue
            for row in table[1:]:
                if not row or len(row) < 2 or not row[1]: continue
                title = str(row[1]).replace("\n","").strip()
                source = str(row[2]).replace("\n"," ").strip() if len(row) > 2 and row[2] else "EPC彙整"
                if len(title) < 5 or any(k in title for k in ["新聞議題","報導媒體","目錄","頁次"]): continue
                if should_skip(title, source): skipped += 1; continue
                classify_text = title + " " + source
                found_cat = None
                for cat in CATEGORY_ORDER:
                    if any(k in classify_text for k in DEPARTMENTS[cat]["keywords"]):
                        found_cat = cat; break
                if not found_cat: skipped += 1; continue
                content = find_article(article_index, title)
                all_items.append({
                    "title": title, "source": source, "cat": found_cat,
                    "priority": get_priority(title, source, found_cat),
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

    # Pre-compute highlight cards data
    highlights = []
    if must_total > 0:
        highlights.append({"label": f"今日必看", "value": f"{must_total} 則", "cat": ""})
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

    now_script = """
const now = new Date();
const roc = now.getFullYear() - 1911;
document.getElementById('gnav-date').textContent =
  '\u6c11\u570b ' + roc + ' \u5e74 ' + (now.getMonth()+1) + ' \u6708 ' + now.getDate() + ' \u65e5';
"""

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EPC Intelligence Hub</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Serif+TC:wght@700;900&family=Noto+Sans+TC:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
{CSS}
</style>
</head>
<body>

<!-- GLOBAL NAV -->
<nav id="gnav">
  <div class="gnav-left">
    <span class="gnav-dot"></span>
    <span class="gnav-name">EPC</span>
  </div>
  <div class="gnav-tabs" id="gnav-tabs"></div>
  <span class="gnav-date" id="gnav-date"></span>
</nav>

<!-- HOME VIEW -->
<div id="home-view">

  <!-- HERO -->
  <section class="hero-block">
    <p class="hero-eyebrow">National Development Council · Economic Planning Division</p>
    <h1 class="hero-headline">一眼掌握。</h1>
    <p class="hero-sub">今日經濟訊號，重點整理完成。</p>
    <div class="hero-kpis">
      <div>
        <div class="kpi-val red" id="kpi-must">{must_total}</div>
        <div class="kpi-label">Must Read</div>
      </div>
      <div>
        <div class="kpi-val blue" id="kpi-total">{len(data_sorted)}</div>
        <div class="kpi-label">Today's Total</div>
      </div>
      <div>
        <div class="kpi-val" id="kpi-cat">{len(cat_counts)}</div>
        <div class="kpi-label">Categories</div>
      </div>
    </div>
  </section>

  <!-- HIGHLIGHTS STRIP -->
  <section class="highlights-section">
    <p class="highlights-eyebrow">看這裡，畫重點。</p>
    <div class="highlights-scroll" id="highlights-scroll"></div>
  </section>

  <!-- 今日必看 -->
  <section class="must-section" id="must-section">
    <div class="must-section-header">
      <span class="must-section-label">今日必看</span>
      <span class="must-section-sub">以下新聞今日登上各大報頭版，且符合本科關注領域</span>
    </div>
    <div class="must-grid" id="must-grid"></div>
  </section>

  <!-- 所有新聞 -->
  <section class="all-section">
    <div class="all-section-header">
      <span class="all-section-label">全部新聞</span>
    </div>
    <div id="brick-grid"></div>
  </section>

</div><!-- end home-view -->

<!-- CATEGORY VIEW (drill-down) -->
<div id="cat-view">
  <div class="cat-nav">
    <button class="back-btn" onclick="closeCatView()">&#8249; 返回</button>
    <span class="cat-nav-title" id="cat-view-title"></span>
  </div>
  <div id="cat-news-list"></div>
</div>

<!-- ARTICLE VIEW (full-page reading) -->
<div id="article-view">
  <nav class="article-nav">
    <button class="back-btn" onclick="closeArticle()" id="art-back-btn">&#8249; 返回</button>
    <span class="article-nav-cat" id="art-nav-cat"></span>
  </nav>
  <div class="article-hero">
    <p class="article-eyebrow" id="art-cat"></p>
    <h1 class="article-headline" id="art-title"></h1>
    <p class="article-source" id="art-source"></p>
  </div>
  <div class="article-summary-block" id="art-summary-block">
    <p class="art-summary-label">三句重點</p>
    <p class="art-summary-text" id="art-summary"></p>
  </div>
  <div class="article-body" id="art-body"></div>
</div>

<script>
const DATA = {data_json};
const DEPTS = {dept_json};
const CAT_ORDER = {cat_order_json};
const HIGHLIGHTS = {highlights_json};

{now_script}

// ESC helper
function esc(s){{
  let r = String(s||'');
  r = r.split('&').join('&amp;');
  r = r.split('<').join('&lt;');
  r = r.split('>').join('&gt;');
  r = r.split('"').join('&quot;');
  return r;
}}

// ── GLOBAL NAV TABS ──
function buildGnavTabs(){{
  const bar = document.getElementById('gnav-tabs');
  bar.innerHTML = '';
  const tabs = [{{'label':'\u6982\u89bd','cat':'all'}}].concat(
    CAT_ORDER.map(c=>({{'label': DEPTS[c]?DEPTS[c].short:c, 'cat': c}}))
  );
  tabs.forEach(t=>{{
    const btn = document.createElement('button');
    btn.className = 'gnav-tab';
    btn.textContent = t.label;
    btn.dataset.cat = t.cat;
    btn.onclick = ()=>{{
      if(t.cat==='all') goHome();
      else openCatView(t.cat);
    }};
    bar.appendChild(btn);
  }});
  setActiveTab('all');
}}

function setActiveTab(cat){{
  document.querySelectorAll('.gnav-tab').forEach(b=>{{
    b.classList.toggle('active', b.dataset.cat===cat);
  }});
}}

// ── HIGHLIGHTS STRIP ──
function buildHighlights(){{
  const scroll = document.getElementById('highlights-scroll');
  scroll.innerHTML = '';
  HIGHLIGHTS.forEach(h=>{{
    const card = document.createElement('div');
    card.className = 'highlight-card' + (h.cat===''?' highlight-must':'');
    card.innerHTML = '<div class="hl-label">'+esc(h.label)+'</div><div class="hl-value">'+esc(h.value)+'</div>';
    card.onclick = ()=>{{
      if(h.cat==='') openCatView('must');
      else openCatView(h.cat);
    }};
    scroll.appendChild(card);
  }});
}}

// ── CATEGORY BRICKS (home) ──
function makeBrick(item, idx, isMustZone){{
  const dataIdx = DATA.indexOf(item);
  const dept = DEPTS[item.cat] || {{}};
  const isFull = idx === 0;
  const isLight = !isMustZone && !isFull && idx % 5 === 3;
  const brick = document.createElement('div');
  brick.className = 'brick'
    + (isFull ? ' brick-full' : '')
    + (isMustZone ? ' brick-must-zone' : '')
    + (isLight ? ' brick-light' : ' brick-dark');
  let inner = '';
  if(isMustZone) inner += '<div class="brick-must-bar"></div>';
  inner += '<div class="brick-eyebrow">'+(dept.icon||'')+' '+esc(item.cat)+'</div>';
  inner += '<div class="brick-title">'+esc(item.title)+'</div>';
  inner += '<div class="brick-summary">'+esc(item.summary)+'</div>';
  inner += '<div class="brick-meta"><span class="brick-source">'+esc(item.source)+'</span>'
    + (isMustZone?'<span class="badge-must">必看</span>':'')+'</div>';
  inner += '<div class="brick-cta">閱讀全文 ›</div>';
  brick.innerHTML = inner;
  brick.onclick = ()=>openArticle(dataIdx);
  return brick;
}}

function renderBricks(cat){{
  const mustGrid = document.getElementById('must-grid');
  const allGrid = document.getElementById('brick-grid');
  const mustSec = document.getElementById('must-section');
  const allSec = allGrid ? allGrid.closest('.all-section') : null;
  if(mustGrid) mustGrid.innerHTML = '';
  if(allGrid) allGrid.innerHTML = '';

  const allItems = (cat&&cat!=='all') ? DATA.filter(i=>i.cat===cat) : DATA;
  const mustItems = allItems.filter(i=>i.priority===1);
  const restItems = allItems.filter(i=>i.priority!==1);

  // 今日必看區
  if(mustSec) mustSec.style.display = mustItems.length ? 'block' : 'none';
  if(mustGrid) mustItems.forEach((item,idx)=>mustGrid.appendChild(makeBrick(item,idx,true)));

  // 全部新聞區
  if(allSec) allSec.style.display = restItems.length ? 'block' : 'none';
  if(allGrid){{
    if(!restItems.length && !mustItems.length)
      allGrid.innerHTML='<div class="empty-brick">目前無資料</div>';
    else
      restItems.forEach((item,idx)=>allGrid.appendChild(makeBrick(item,idx,false)));
  }}
}}


// ── CATEGORY VIEW ──
function openCatView(cat){{
  const isMust = cat==='must';
  const items = isMust ? DATA.filter(i=>i.priority===1) : DATA.filter(i=>i.cat===cat);
  const title = isMust ? '\u5fc5\u770b\u60c5\u5831' : cat;
  document.getElementById('cat-view-title').textContent = title;
  const list = document.getElementById('cat-news-list');
  list.innerHTML = '';
  items.forEach(item=>{{
    const dataIdx = DATA.indexOf(item);
    const row = document.createElement('div');
    row.className = 'news-row' + (item.priority===1?' news-row-must':'');
    row.innerHTML =
      '<div class="news-row-inner">' +
        (item.priority===1?'<div class="row-must-bar"></div>':'') +
        '<div class="row-cat">'+(DEPTS[item.cat]?DEPTS[item.cat].icon:'')+' '+esc(item.cat)+'</div>'+
        '<h3 class="row-title">'+esc(item.title)+'</h3>'+
        '<p class="row-summary">'+esc(item.summary)+'</p>'+
        '<div class="row-footer">'+
          '<span class="row-source">'+esc(item.source)+'</span>'+
          '<span class="row-cta">\u95b1\u8b80\u5168\u6587 \u203a</span>'+
        '</div>'+
      '</div>';
    row.onclick=()=>openArticle(dataIdx);
    list.appendChild(row);
  }});
  showView('cat-view');
  setActiveTab(isMust?'all':cat);
}}
function closeCatView(){{ goHome(); }}

// ── ARTICLE VIEW ──
function openArticle(idx){{
  const item = DATA[idx];
  const cat = DEPTS[item.cat]?(DEPTS[item.cat].icon+' '+item.cat):item.cat;
  document.getElementById('art-cat').textContent = cat;
  document.getElementById('art-nav-cat').textContent = cat;
  document.getElementById('art-title').textContent = item.title;
  document.getElementById('art-source').textContent = '\u4f86\u6e90\uff1a' + item.source;
  document.getElementById('art-summary').textContent = item.summary;
  document.getElementById('art-summary-block').style.display = item.summary ? 'block' : 'none';
  const rawText = item.full_text || '\u5c1a\u672a\u64f7\u53d6\u5230\u5167\u6587\u5167\u5bb9';
  const paras = rawText.split('\\n\\n').map(p=>'<p>'+esc(p.trim())+'</p>').join('');
  document.getElementById('art-body').innerHTML = paras;

  // back button context
  const fromCat = currentView === 'cat-view';
  document.getElementById('art-back-btn').onclick = fromCat
    ? ()=>{{ showView('cat-view'); }}
    : ()=>closeArticle();

  showView('article-view');
  history.pushState({{view:'article', idx}}, '');
}}
function closeArticle(){{
  if(currentView==='article-view'){{
    const prev = history.state;
    if(prev && prev.view==='cat-view') showView('cat-view');
    else goHome();
  }}
}}

// ── VIEW MANAGER ──
let currentView = 'home-view';
function showView(id){{
  ['home-view','cat-view','article-view'].forEach(v=>{{
    document.getElementById(v).style.display = v===id ? 'block' : 'none';
  }});
  currentView = id;
  window.scrollTo(0,0);
  document.body.style.overflow = '';
}}
function goHome(){{
  showView('home-view');
  setActiveTab('all');
}}

window.addEventListener('popstate', e=>{{
  if(currentView==='article-view') closeArticle();
  else if(currentView==='cat-view') goHome();
}});
document.addEventListener('keydown', e=>{{ if(e.key==='Escape'){{
  if(currentView==='article-view') closeArticle();
  else if(currentView==='cat-view') goHome();
}} }});

// ── INIT ──
buildGnavTabs();
buildHighlights();
renderBricks('all');
showView('home-view');
</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8", errors="replace") as f:
        f.write(html)

# ── CSS ──────────────────────────────────────────────────────
CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #f5f5f7;
  --black: #000; --dark1: #1d1d1f; --dark2: #161617;
  --white: #fff; --offwhite: #fbfbfd;
  --border: rgba(255,255,255,0.1); --border-b: rgba(0,0,0,0.08);
  --tw: #f5f5f7; --tw2: #a1a1a6; --tw3: #6e6e73;
  --tb: #1d1d1f; --tb2: #6e6e73; --tb3: #86868b;
  --blue: #0071e3; --must: #ff3b30;
}
html { scroll-behavior: smooth; }
body { background: var(--bg); font-family: 'Inter',-apple-system,'SF Pro Display','Helvetica Neue','Noto Sans TC',sans-serif; -webkit-font-smoothing: antialiased; overflow-x: hidden; color: var(--tb); }

/* ── GLOBAL NAV ── */
#gnav {
  height: 44px; background: rgba(0,0,0,0.88);
  backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 22px; position: sticky; top: 0; z-index: 900; gap: 0;
}
.gnav-left { display: flex; align-items: center; gap: 7px; flex-shrink: 0; }
.gnav-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--blue); }
.gnav-name { font-size: 15px; font-weight: 600; color: var(--tw); letter-spacing: 0.02em; }
.gnav-tabs { display: flex; overflow-x: auto; scrollbar-width: none; gap: 0; flex: 1; justify-content: center; }
.gnav-tabs::-webkit-scrollbar { display: none; }
.gnav-tab {
  padding: 0 14px; height: 44px; border: none; background: none;
  font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.55);
  cursor: pointer; white-space: nowrap; font-family: inherit;
  transition: color 0.15s; letter-spacing: 0.02em;
}
.gnav-tab:hover { color: var(--tw); }
.gnav-tab.active { color: var(--tw); }
.gnav-date { font-size: 11px; color: var(--tw3); flex-shrink: 0; }

/* ── HERO ── */
.hero-block {
  background: var(--black); text-align: center;
  padding: 100px 24px 72px; border-bottom: 1px solid var(--border);
}
.hero-eyebrow { font-size: 12px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--tw3); margin-bottom: 20px; }
.hero-headline { font-size: 72px; font-weight: 700; letter-spacing: -0.05em; line-height: 1.0; color: var(--tw); margin-bottom: 16px; }
.hero-sub { font-size: 21px; color: var(--tw2); font-weight: 300; margin-bottom: 56px; letter-spacing: -0.01em; }
.hero-kpis { display: flex; justify-content: center; gap: 72px; padding-top: 40px; border-top: 1px solid var(--border); }
.kpi-val { font-size: 52px; font-weight: 700; letter-spacing: -0.04em; line-height: 1; }
.kpi-val.red { color: var(--must); }
.kpi-val.blue { color: var(--blue); }
.kpi-label { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--tw3); margin-top: 8px; }

/* ── HIGHLIGHTS STRIP ── */
.highlights-section { background: var(--offwhite); padding: 40px 0 36px; border-bottom: 1px solid var(--border-b); }
.highlights-eyebrow { font-size: 28px; font-weight: 700; letter-spacing: -0.025em; color: var(--tb); text-align: center; margin-bottom: 24px; }
.highlights-scroll {
  display: flex; gap: 12px; overflow-x: auto; scrollbar-width: none;
  padding: 0 24px; scroll-snap-type: x mandatory;
}
.highlights-scroll::-webkit-scrollbar { display: none; }
.highlight-card {
  flex-shrink: 0; width: 160px; background: var(--white);
  border-radius: 18px; padding: 22px 18px; cursor: pointer;
  border: 1px solid var(--border-b); scroll-snap-align: start;
  transition: transform 0.2s, box-shadow 0.2s;
}
.highlight-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
.highlight-card.highlight-must { background: var(--must); border-color: transparent; }
.highlight-card.highlight-must .hl-label,
.highlight-card.highlight-must .hl-value { color: #fff; }
.hl-label { font-size: 13px; font-weight: 600; color: var(--tb); margin-bottom: 6px; letter-spacing: -0.01em; }
.hl-value { font-size: 13px; color: var(--tb3); font-weight: 400; }

/* ── CATEGORY BRICKS ── */
#brick-grid {
  background: var(--bg); display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px; padding: 12px;
}
.brick {
  border-radius: 22px; min-height: 440px;
  padding: 48px 40px; display: flex; flex-direction: column;
  justify-content: flex-end; cursor: pointer; position: relative;
  overflow: hidden; transition: transform 0.25s cubic-bezier(.25,.46,.45,.94);
}
.brick:hover { transform: scale(1.01); }
.brick-full { grid-column: 1 / -1; min-height: 480px; justify-content: center; align-items: flex-start; }
.brick-dark { background: var(--dark1); }
.brick-light { background: var(--white); border: 1px solid var(--border-b); }

.brick-must-bar { position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--must); border-radius: 22px 22px 0 0; }
.brick-eyebrow { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--blue); margin-bottom: 14px; }
.brick-title {
  font-size: 22px; font-weight: 700; letter-spacing: -0.025em; line-height: 1.25;
  color: var(--tw); margin-bottom: 10px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.brick-full .brick-title { font-size: 28px; -webkit-line-clamp: 2; }
.brick-light .brick-title { color: var(--tb); }
.brick-summary {
  font-size: 15px; color: var(--tw2); line-height: 1.65; margin-bottom: 20px;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.brick-full .brick-summary { -webkit-line-clamp: 4; }
.brick-source { font-size: 12px; color: var(--tw3); }
.brick-light .brick-source { color: var(--tb3); }
.brick-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; }
.badge-must { background: var(--must); color: #fff; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 20px; letter-spacing: 0.05em; }
.brick-light .brick-summary { color: var(--tb2); }
.brick-cta-row { display: flex; gap: 24px; align-items: center; }
.brick-cta { font-size: 17px; color: var(--blue); font-weight: 400; letter-spacing: -0.01em; }
.brick-cta2 { font-size: 17px; color: var(--tw2); font-weight: 400; letter-spacing: -0.01em; }
.brick-light .brick-cta2 { color: var(--tb2); }

/* ── CATEGORY VIEW ── */
#cat-view { display: none; background: var(--bg); min-height: 100vh; }
.cat-nav {
  background: rgba(245,245,247,0.88); backdrop-filter: blur(20px);
  height: 44px; display: flex; align-items: center;
  padding: 0 22px; gap: 16px; border-bottom: 1px solid var(--border-b);
  position: sticky; top: 44px; z-index: 800;
}
.cat-nav-title { font-size: 14px; font-weight: 600; color: var(--tb); letter-spacing: -0.01em; }
.back-btn {
  background: none; border: none; font-size: 17px; color: var(--blue);
  cursor: pointer; font-family: inherit; padding: 0; display: flex;
  align-items: center; gap: 2px; transition: opacity 0.15s;
}
.back-btn:hover { opacity: 0.7; }

/* News rows in cat-view */
#cat-news-list { max-width: 800px; margin: 0 auto; padding: 0 24px 80px; }
.news-row {
  background: var(--white); border-radius: 18px; margin-top: 12px;
  overflow: hidden; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;
  border: 1px solid var(--border-b);
}
.news-row:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
.news-row-inner { padding: 28px 32px; position: relative; }
.row-must-bar { position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--must); }
.row-cat { font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--blue); margin-bottom: 10px; }
.row-title { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.3; color: var(--tb); margin-bottom: 10px; }
.row-summary { font-size: 14px; color: var(--tb2); line-height: 1.65; margin-bottom: 16px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.row-footer { display: flex; align-items: center; justify-content: space-between; }
.row-source { font-size: 12px; color: var(--tb3); }
.row-cta { font-size: 14px; color: var(--blue); }

/* ── ARTICLE VIEW ── */
#article-view { display: none; background: var(--white); min-height: 100vh; }
.article-nav {
  background: rgba(255,255,255,0.88); backdrop-filter: saturate(180%) blur(20px);
  height: 44px; display: flex; align-items: center; padding: 0 22px;
  border-bottom: 1px solid var(--border-b); position: sticky; top: 44px; z-index: 800; gap: 16px;
}
.article-nav-cat { font-size: 13px; color: var(--tb3); margin-left: auto; }
.article-hero {
  background: var(--white); padding: 72px 24px 48px; text-align: center;
  border-bottom: 1px solid var(--border-b);
}
.article-eyebrow { font-size: 12px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--blue); margin-bottom: 16px; }
.article-headline { font-size: 44px; font-weight: 700; letter-spacing: -0.04em; line-height: 1.1; color: var(--tb); margin-bottom: 20px; max-width: 760px; margin-left: auto; margin-right: auto; }
.article-source { font-size: 14px; color: var(--tb3); }
.article-summary-block {
  background: var(--offwhite); border-bottom: 1px solid var(--border-b);
  padding: 32px 24px;
}
.article-summary-block > * { max-width: 680px; margin-left: auto; margin-right: auto; }
.art-summary-label { font-size: 11px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--blue); margin-bottom: 10px; }
.art-summary-text { font-size: 17px; color: var(--tb2); line-height: 1.7; font-weight: 400; letter-spacing: -0.01em; }
.article-body { max-width: 680px; margin: 0 auto; padding: 52px 24px 100px; }
.article-body p { font-size: 19px; line-height: 1.9; color: var(--tb); margin-bottom: 1.5em; font-weight: 400; letter-spacing: -0.01em; }
.article-body p:last-child { margin-bottom: 0; }

/* ── MUST SECTION ── */
.must-section {
  background: var(--black); padding: 0 0 2px;
  border-bottom: 2px solid rgba(255,59,48,0.3);
}
.must-section-header {
  padding: 36px 24px 20px;
  display: flex; align-items: baseline; gap: 16px;
}
.must-section-label {
  font-size: 28px; font-weight: 700; letter-spacing: -0.03em; color: var(--tw);
}
.must-section-sub {
  font-size: 13px; color: var(--tw3); font-weight: 400;
}
.must-grid {
  display: grid; grid-template-columns: repeat(2,1fr); gap: 2px;
}
.brick-must-zone {
  background: #1a0a0a;
}
.brick-must-zone .brick-eyebrow { color: #ff6b60; }
.brick-must-zone .brick-title { color: var(--tw); }
.brick-must-zone .brick-summary { color: var(--tw2); }
.brick-must-zone .brick-source { color: var(--tw3); }
.brick-must-zone .brick-cta { color: #ff6b60; }

.all-section { background: var(--bg); }
.all-section-header {
  padding: 32px 24px 16px;
}
.all-section-label {
  font-size: 22px; font-weight: 700; letter-spacing: -0.025em; color: var(--tb);
}

/* responsive */
@media (max-width: 720px) {
  .hero-headline { font-size: 48px; }
  .hero-sub { font-size: 17px; }
  .hero-kpis { gap: 32px; }
  .kpi-val { font-size: 40px; }
  #brick-grid { grid-template-columns: 1fr; }
  .brick { min-height: 340px; padding: 36px 28px; border-radius: 18px; }
  .brick-title { font-size: 22px; }
  .brick.brick-full .brick-title { font-size: 26px; }
  .article-headline { font-size: 30px; }
  .article-body p { font-size: 17px; }
  .gnav-tabs { display: none; }
  .gnav-date { display: none; }
}
"""

if __name__ == "__main__":
    run_dashboard()
