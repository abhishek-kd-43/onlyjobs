import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import json
import os
import re
import hashlib
import time
import random
import traceback
from datetime import date
from datetime import datetime, timezone

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-IN,en;q=0.9,hi;q=0.8',
}

# ─────────────────────────────────────────────
# COMPETITOR DOMAINS — every link/image pointing
# to these will be stripped or replaced
# ─────────────────────────────────────────────
COMPETITOR_DOMAINS = [
    'sarkariresult.com', 'sarkariresult', 'sarkari result',
    'freejobalert.com', 'freejobalert', 'free job alert',
    'sarkariexam.com',  'sarkariexam',  'sarkari exam',
    'naukri.com', 'shine.com', 'freshersworld.com', 'rojgarresult.com',
    'sarkari naukri', 'sarkarinaukri', 'careersage.in', 'employmentnews',
    'indGovtJobs', 'sarkariwallahs', 'sarkarimaster',
]

APP_STORE_PATTERNS = [
    'play.google.com', 'apps.apple.com', 'app.adjust.com',
    'onelink.me', 'apkpure.com', 'apkmirror.com',
    'download app', 'get app', 'install app', 'download now the app',
    'google play', 'app store', 'available on play store',
    'download on the', 'android app', 'ios app',
]

SOCIAL_DOMAINS = [
    'facebook.com', 'twitter.com', 'instagram.com', 'youtube.com', 'youtu.be',
    'whatsapp.com', 'wa.me', 't.me', 'telegram.me', 'linkedin.com',
    'pinterest.com', 'snapchat.com',
]

# Unsplash image categories for different post types
IMAGE_KEYWORDS = {
    'latest_jobs': ['government,jobs,india', 'exam,study,india', 'recruitment,india', 'sarkari,naukri'],
    'results':     ['exam,result,india', 'board,result', 'merit,list', 'government,exam'],
    'admit_cards': ['admit,card,exam', 'hall,ticket,exam', 'exam,india', 'recruitment,exam'],
    'answer_keys': ['answer,key,exam', 'exam,paper,india', 'question,paper', 'exam,solution'],
}

STATE_PORTALS_FILE = os.path.join(os.path.dirname(__file__), 'state_portals.json')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')
SCRAPE_STATUS_FILE = os.path.join(os.path.dirname(__file__), 'scrape_status.json')

try:
    with open(STATE_PORTALS_FILE, 'r', encoding='utf-8') as f:
        STATE_DIRECTORY = json.load(f).get('states', [])
except Exception:
    STATE_DIRECTORY = []

STATE_PORTAL_MAP = {
    entry['name']: entry.get('portal_url', '')
    for entry in STATE_DIRECTORY
    if entry.get('type') in ('state', 'ut')
}

GENERIC_SCOPE_MAP = {
    entry['name']: entry.get('portal_url', '')
    for entry in STATE_DIRECTORY
    if entry.get('type') == 'central'
}

STATE_SIGNAL_PATTERNS = {
    entry['name']: [
        re.compile(r'(?<![a-z])' + re.escape(alias.lower()) + r'(?![a-z])', re.IGNORECASE)
        for alias in entry.get('aliases', [])
    ]
    for entry in STATE_DIRECTORY
    if entry.get('type') in ('state', 'ut')
}

CENTRAL_SCOPE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r'\bcentral govt\b', r'\bcentral government\b', r'\bupsc\b', r'\bssc\b',
        r'\brailway\b', r'\brrb\b', r'\bibps\b', r'\bsbi\b', r'\bindian army\b',
        r'\bindian navy\b', r'\bindian air ?force\b', r'\bagniveer\b',
        r'\bdrdo\b', r'\bnielit\b', r'\bctet\b', r'\bneet\b', r'\bnta\b'
    ]
]

ALL_INDIA_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r'\ball india\b', r'\ball states\b', r'\bnationwide\b',
        r'\bpan india\b', r'\bacross india\b'
    ]
]


def get_hero_image_url(category: str, title: str) -> str:
    """Return an Unsplash image URL. Uses a deterministic seed so the same post
    always gets the same image."""
    keywords_list = IMAGE_KEYWORDS.get(category, IMAGE_KEYWORDS['latest_jobs'])
    # Use picsum for reliable fallback (no API key needed)
    seed = abs(hash(title)) % 1000
    return f"https://picsum.photos/seed/{seed}/800/400"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json_atomic(path: str, payload: dict):
    tmp_path = path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def is_competitor_href(href: str, current_site_type: str = None) -> bool:
    if not href:
        return False
    href_lower = href.lower()
    
    # Don't skip our own site's links
    site_domain_map = {'SR': 'sarkariresult.com', 'FJA': 'freejobalert.com', 'SE': 'sarkariexam.com'}
    current_domain = site_domain_map.get(current_site_type, 'impossible_domain')
    
    for domain in COMPETITOR_DOMAINS:
        if domain.lower() in href_lower:
            # If it's our own domain, keep it
            if domain.lower() in current_domain:
                continue
            return True
    for pattern in APP_STORE_PATTERNS:
        if pattern.lower() in href_lower:
            return True
    return False


def is_social_href(href: str) -> bool:
    if not href:
        return False
    href_lower = href.lower()
    for domain in SOCIAL_DOMAINS:
        if domain in href_lower:
            return True
    return False


def clean_text(text: str) -> str:
    """Replace all competitor text references with OnlyJobs."""
    if not text: return ""
    # Competitor brand names
    text = re.sub(r'Sarkari\s*Result\.?\s*Com|Sarkari\s*Result|sarkariresult\.com|SARKARI\s*RESULT|sarkariresult', 'OnlyJobs', text, flags=re.IGNORECASE)
    text = re.sub(r'freejobalert\.com|Free\s*Job\s*Alert|FreeJobAlert|freejobalert', 'OnlyJobs', text, flags=re.IGNORECASE)
    text = re.sub(r'sarkariexam\.com|Sarkari\s*Exam|SarkariExam|sarkariexam', 'OnlyJobs', text, flags=re.IGNORECASE)
    text = re.sub(r'rojgarresult\.com|RojgarResult|rojgarresult', 'OnlyJobs', text, flags=re.IGNORECASE)
    text = re.sub(r'sarkarinaukri\.com|Sarkari\s*Naukri|sarkarinaukri', 'OnlyJobs', text, flags=re.IGNORECASE)
    # App download mentions
    for pat in APP_STORE_PATTERNS:
        text = re.sub(re.escape(pat), '', text, flags=re.IGNORECASE)
    return text


def deep_clean_soup(soup_elem, current_site_type=''):
    """
    Aggressively clean a BeautifulSoup element:
    - Remove all scripts, styles, iframes, ads, share widgets, app banners
    - Strip href/src attributes pointing to competitors, app stores, social media
    - Remove entire <a> and <img> tags that point to competitors or apps
    - Replace competitor text with OnlyJobs
    """
    if not soup_elem:
        return soup_elem

    # 1. Remove unwanted tags entirely
    for tag in list(soup_elem.find_all(['script', 'style', 'iframe', 'noscript', 'meta', 'link'])):
        tag.decompose()

    # 2. Remove ads / share / social / app-download divs by class/id keywords
    junk_classes = re.compile(
        r'share|social|addtoany|fb-|whatsapp|telegram|app-download|download-app|'
        r'mobile-app|get-app|playstore|appstore|ad-|ads-|advertisement|'
        r'comments?|comment-form|related-posts?|newsletter|subscribe|signup|'
        r'sidebar|widget|breadcrumb|navigation|footer|header|menu|navbar|'
        r'popup|modal|overlay|cookie|gdpr|notification|alert-bar',
        re.IGNORECASE
    )
    for tag in list(soup_elem.find_all(True)):
        if not tag.parent: continue
        cls = ' '.join(tag.get('class', [])) if tag.get('class') else ''
        tag_id = str(tag.get('id', ''))
        if junk_classes.search(cls) or junk_classes.search(tag_id):
            tag.decompose()

    # 3. Strip competitor / app-store / social links
    for a_tag in list(soup_elem.find_all('a')):
        if not a_tag.parent: continue
        href = a_tag.get('href', '')
        text_lower = a_tag.get_text(strip=True).lower()

        if is_competitor_href(href, current_site_type):
            a_tag.decompose()
            continue
        if is_social_href(href):
            a_tag.decompose()
            continue
        for pat in APP_STORE_PATTERNS:
            if pat.lower() in text_lower:
                a_tag.decompose()
                break
        else:
            if href and href.startswith('http') and 'gov.in' not in href and 'nic.in' not in href:
                a_tag['href'] = href
                if a_tag.has_attr('target'): del a_tag['target']
                a_tag.attrs = {k: v for k, v in a_tag.attrs.items() if k not in ['onclick', 'onmouseover']}

    # 4. Strip competitor images / logos
    for img in list(soup_elem.find_all('img')):
        if not img.parent: continue
        src = img.get('src', '')
        alt = img.get('alt', '')
        if is_competitor_href(src, current_site_type):
            img.decompose()
            continue
        if any(d in alt.lower() for d in ['sarkari', 'freejobalert', 'sarkariexam']):
            img.decompose()
            continue

    # 5. Replace competitor text in all text nodes and common attributes
    for tag in list(soup_elem.find_all(True)):
        if not tag.parent: continue
        for attr in ['title', 'alt', 'aria-label']:
            if tag.has_attr(attr):
                tag[attr] = clean_text(tag[attr])

    for text_node in list(soup_elem.find_all(string=True)):
        if isinstance(text_node, NavigableString):
            new_text = clean_text(str(text_node))
            if new_text != str(text_node):
                text_node.replace_with(new_text)

    return soup_elem


def extract_key_info(title: str, content_soup) -> dict:
    """Try to extract key dates, vacancies, last date from the parsed content."""
    info = {
        'last_date': 'See Notification',
        'vacancies': 'Various',
        'exam_date': 'As per Schedule',
        'category': 'Central Govt',
    }
    if not title: title = "Government Job Update 2026"
    text = content_soup.get_text(' ', strip=True) if content_soup else ''

    # Last date
    m = re.search(r'last\s*date[:\s]+([A-Z][a-z]{2,8}[\s\d,]+\d{4}|[\d/\-]+\s*\d{4})', text, re.IGNORECASE)
    if not m:
         m = re.search(r'last\s*date\s*[:\-]\s*([\d\-\/]+)', text, re.IGNORECASE)
    if m:
        info['last_date'] = m.group(1).strip()

    # Vacancies
    m = re.search(r'(\d[\d,]+)\s*(?:post|vacancy|vacancies|seat)', text, re.IGNORECASE)
    if m:
        info['vacancies'] = m.group(1).strip()

    # Exam date
    m = re.search(r'exam\s*date[:\s]+([A-Z][a-z]{2,8}[\s\d,]+\d{4}|[\d/\-]+\s*\d{4})', text, re.IGNORECASE)
    if m:
        info['exam_date'] = m.group(1).strip()

    # Category from title
    for cat in ['UPSC', 'SSC', 'Railway', 'RRB', 'Banking', 'IBPS', 'SBI', 'Defence', 'Army', 'Navy', 'Air Force', 'Police', 'Teaching', 'CTET', 'TET']:
        if cat.lower() in title.lower():
            info['category'] = cat
            break

    return info


def html_to_text(value: str) -> str:
    if not value:
        return ''
    if '<' in value and '>' in value:
        return BeautifulSoup(value, 'html.parser').get_text(' ', strip=True)
    return value


def infer_state_data(title: str, content_html: str) -> dict:
    combined_text = ' '.join(
        part for part in [clean_text(title or ''), html_to_text(content_html or '')[:2500]]
        if part
    )
    normalized = re.sub(r'\s+', ' ', combined_text).strip().lower()

    if any(pattern.search(normalized) for pattern in ALL_INDIA_PATTERNS):
        return {'states': [], 'state_label': 'All India', 'official_state_portal': GENERIC_SCOPE_MAP.get('All India', '')}

    matched_states = []
    for state_name, patterns in STATE_SIGNAL_PATTERNS.items():
        if any(pattern.search(normalized) for pattern in patterns):
            matched_states.append(state_name)

    if matched_states:
        unique_states = []
        for state_name in matched_states:
            if state_name not in unique_states:
                unique_states.append(state_name)
        if len(unique_states) > 3:
            return {'states': unique_states, 'state_label': 'All States', 'official_state_portal': ''}
        portal = STATE_PORTAL_MAP.get(unique_states[0], '') if len(unique_states) == 1 else ''
        return {'states': unique_states, 'state_label': ' / '.join(unique_states), 'official_state_portal': portal}

    if any(pattern.search(normalized) for pattern in CENTRAL_SCOPE_PATTERNS):
        return {'states': [], 'state_label': 'Central Govt', 'official_state_portal': GENERIC_SCOPE_MAP.get('Central Govt', '')}

    return {'states': [], 'state_label': 'All India', 'official_state_portal': GENERIC_SCOPE_MAP.get('All India', '')}


def generate_seo_post(title: str, category: str, info: dict, clean_content_html: str, original_url: str) -> str:
    """
    Generate a full SEO-optimised professional blog-style HTML post.
    """
    hero_img = get_hero_image_url(category, title)
    safe_title = clean_text(title).replace('"', '&quot;')
    safe_heading = clean_text(title)
    meta_desc = clean_text(f"Check complete details for {title}. Includes important dates, application link, eligibility, syllabus and result info — updated live on OnlyJobs.")

    cat_label_map = {
        'latest_jobs': 'Latest Jobs 2026',
        'results':     'OnlyJobs Result 2026',
        'admit_cards': 'Admit Card 2026',
        'answer_keys': 'Answer Key 2026',
    }
    cat_label = cat_label_map.get(category, 'OnlyJobs Update 2026')

    toc_items_map = {
        'latest_jobs': ['Important Dates', 'Vacancies &amp; Category', 'Age Limit', 'Qualification', 'Application Fee', 'How to Apply', 'Official Links'],
        'results':     ['Result Status', 'Cut Off Marks', 'Score Card Download', 'Merit List', 'Next Steps', 'Official Links'],
        'admit_cards': ['Exam Date', 'Download Admit Card', 'Important Instructions', 'Exam Pattern', 'Official Links'],
        'answer_keys': ['Download Answer Key', 'Raise Objections', 'Expected Cut Off', 'Result Date', 'Official Links'],
    }
    toc_items = toc_items_map.get(category, toc_items_map['latest_jobs'])
    toc_html = ''.join([f'<li><a href="#sec-{i+1}" style="color:#1D4ED8;text-decoration:none;">→ {item}</a></li>' for i, item in enumerate(toc_items)])

    highlights_html = f"""
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0;">
      <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;">📅</div>
        <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;margin:4px 0;">Last Date</div>
        <div style="font-size:14px;font-weight:700;color:#1D4ED8;">{info['last_date']}</div>
      </div>
      <div style="background:#ECFDF5;border:1px solid #A7F3D0;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;">💼</div>
        <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;margin:4px 0;">Vacancies</div>
        <div style="font-size:14px;font-weight:700;color:#059669;">{info['vacancies']}</div>
      </div>
      <div style="background:#FFF3EB;border:1px solid #FED7AA;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;">📝</div>
        <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;margin:4px 0;">Exam Date</div>
        <div style="font-size:14px;font-weight:700;color:#E85D04;">{info['exam_date']}</div>
      </div>
      <div style="background:#F5F3FF;border:1px solid #DDD6FE;border-radius:10px;padding:14px;text-align:center;">
        <div style="font-size:22px;">🏛️</div>
        <div style="font-size:11px;color:#64748B;font-weight:700;text-transform:uppercase;margin:4px 0;">Category</div>
        <div style="font-size:14px;font-weight:700;color:#7C3AED;">{info['category']}</div>
      </div>
    </div>
    """

    full_html = f"""
<article style="font-family:'Figtree',sans-serif;max-width:900px;margin:0 auto;color:#2D2D3A;line-height:1.7;">
  <div style="border-radius:14px;overflow:hidden;margin-bottom:22px;position:relative;height:260px;background:#1A1A2E;">
    <img src="{hero_img}" alt="{safe_title}" style="width:100%;height:100%;object-fit:cover;opacity:0.55;" onerror="this.style.display='none'"/>
    <div style="position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;padding:22px 24px;background:linear-gradient(to top,rgba(0,0,0,0.7) 0%,transparent 60%);">
      <span style="display:inline-block;background:#E85D04;color:#fff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;margin-bottom:8px;width:fit-content;">{cat_label}</span>
      <h1 style="font-size:clamp(17px,2.5vw,24px);font-weight:800;color:#fff;line-height:1.3;margin:0;">{safe_heading}</h1>
    </div>
  </div>
  <div style="display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:#64748B;padding:12px 16px;background:#F7F8FC;border-radius:8px;margin-bottom:20px;align-items:center;">
    <span>📅 Updated: {date.today().strftime('%d %b %Y')}</span>
    <span>✍️ By: <strong style="color:#E85D04;">OnlyJobs Editorial Team</strong></span>
    <span>🌐 Source: <a href="{original_url}" target="_blank" rel="nofollow noopener" style="color:#1D4ED8;">Official Notification</a></span>
  </div>
  <p style="font-size:15px;color:#374151;margin-bottom:18px;">{meta_desc}</p>
  <h2 style="font-size:18px;font-weight:800;color:#1A1A2E;border-left:4px solid #E85D04;padding-left:12px;margin:24px 0 12px;">⚡ Key Highlights</h2>
  {highlights_html}
  <div style="background:#F0F2F8;border-radius:10px;padding:16px 20px;margin:24px 0;">
    <div style="font-weight:800;font-size:14px;color:#1A1A2E;margin-bottom:10px;">📋 Quick Navigation</div>
    <ol style="margin:0;padding-left:20px;color:#374151;font-size:13.5px;line-height:2;">{toc_html}</ol>
  </div>
  <h2 style="font-size:18px;font-weight:800;color:#1A1A2E;border-left:4px solid #E85D04;padding-left:12px;margin:28px 0 16px;">📄 Complete Details &amp; Notification</h2>
  <div id="scraped-body" style="overflow-x:auto;">
    {clean_content_html if clean_content_html.strip() else '<p>Detailed content available on the official website.</p>'}
  </div>
  <div style="background:linear-gradient(135deg,#1A1A2E 0%,#3730A3 100%);border-radius:12px;padding:24px;margin:30px 0;text-align:center;color:#fff;">
    <h3 style="margin-bottom:8px;">Get Instant Job Alerts on OnlyJobs</h3>
    <p style="font-size:13px;margin-bottom:16px;">Join 4.8 Cr+ aspirants. Free mock tests, live results, and daily job updates.</p>
    <a href="index.html" style="background:#E85D04;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:700;">🏠 Browse All Jobs</a>
  </div>
</article>
"""
    return full_html


def fetch_inner_content_clean(url: str, site_type: str, category: str = 'latest_jobs') -> str:
    """Fetch the post page, deep-clean it, return SEO-wrapped professional HTML."""
    try:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        session.mount('https://', adapter)
        
        res = session.get(url, headers=HEADERS, timeout=30)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        title_tag = soup.find('h1')
        page_title = title_tag.get_text(strip=True) if title_tag else ""

        content = None
        if site_type == 'SR':
            content = soup.find('div', id='post') or soup.find('div', class_=re.compile(r'postab|post-content|post_detail'))
        elif site_type in ['FJA', 'SE']:
            content = soup.find('div', class_=re.compile(r'entry-content|post-content|single-post')) or soup.find('article')

        if not content:
            tables = soup.find_all('table')
            if tables: content = max(tables, key=lambda t: len(str(t)))

        if not content: return "", {}

        content = deep_clean_soup(content, site_type)
        info = extract_key_info(page_title or "", content)
        return str(content), info
    except Exception:
        print(f"  ❌ Failed inner [{site_type}] {url}: {traceback.format_exc()}")
        return "", {}


def generate_entry(title: str, url: str, site_type: str, category: str = 'latest_jobs') -> dict:
    post_id = hashlib.md5(f'{category}:{url}'.encode('utf-8')).hexdigest()
    print(f"  🔍 [{site_type}] {title[:70]}...")
    try:
        raw_content_html, info = fetch_inner_content_clean(url, site_type, category)
        if not info: info = extract_key_info(title, None)
        seo_html = generate_seo_post(title, category, info, raw_content_html, url)
        state_data = infer_state_data(title, raw_content_html)
        time.sleep(0.5)
        return {
            "id": post_id, "title": clean_text(title),
            "original_url": url, "content_html": seo_html,
            "source": site_type, "_cat": category,
            "states": state_data['states'],
            "state_label": state_data['state_label'],
            "official_state_portal": state_data['official_state_portal']
        }
    except Exception:
        print(f"  ❌ Failed [GEN] {title}: {traceback.format_exc()}")
        return None


def scrape_sarkariresult(limit=5):
    res = {'results': [], 'admit_cards': [], 'latest_jobs': [], 'answer_keys': []}
    counts = {key: 0 for key in res}
    url = "https://www.sarkariresult.com/"
    print(f"\n📡 Scraping SarkariResult ({url})...")
    try:
        html = requests.get(url, headers=HEADERS, timeout=25).text
        soup = BeautifulSoup(html, 'html.parser')
        columns = soup.find_all('div', id='post')
        mapping = {'Result': 'results', 'Admit Card': 'admit_cards', 'Latest Job': 'latest_jobs', 'Online Form': 'latest_jobs', 'Answer Key': 'answer_keys'}
        for col in columns:
            head_txt = col.get_text().strip().split('\n')[0].strip()
            cat = next((v for k, v in mapping.items() if k.lower() in head_txt.lower()), None)
            if not cat: continue
            for link in col.find_all('a')[:limit]:
                title, href = link.text.strip(), link.get('href', '')
                if not title or not href: continue
                full_url = href if href.startswith('http') else url.rstrip('/') + '/' + href.lstrip('/')
                if is_competitor_href(full_url, 'SR'): continue
                e = generate_entry(title, full_url, "SR", cat)
                if e:
                    res[cat].append(e)
                    counts[cat] += 1
                if counts[cat] >= limit:
                    break
    except Exception as e: print(f"  ❌ SR Error: {e}")
    return res

def scrape_freejobalert(limit=5):
    res = {'results': [], 'admit_cards': [], 'latest_jobs': [], 'answer_keys': []}
    counts = {key: 0 for key in res}
    url = "https://www.freejobalert.com/"
    print(f"\n📡 Scraping FreeJobAlert ({url})...")
    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        html = session.get(url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, 'html.parser')
        mapping = {'Result': 'results', 'Admit Card': 'admit_cards', 'Notification': 'latest_jobs', 'Updates': 'latest_jobs', 'Answer Key': 'answer_keys'}
        headings = soup.find_all(['h2', 'h3', 'div', 'span'], class_=re.compile(r'nutitle|gb-headline|widget-title|section-head', re.I)) or soup.find_all(['h2', 'h3'])
        for h in headings:
            txt = h.get_text().strip()
            cat = next((v for k, v in mapping.items() if k.lower() in txt.lower()), None)
            if not cat: continue
            nxt = h.find_next_sibling('ul') or h.find_next('ul')
            if not nxt: continue
            if counts[cat] >= limit:
                continue
            for link in nxt.find_all('a')[:limit]:
                title, href = link.text.strip(), link.get('href', '')
                if not title or not href: continue
                full_url = href if href.startswith('http') else 'https://www.freejobalert.com' + href
                if is_competitor_href(full_url, 'FJA'): continue
                e = generate_entry(title, full_url, "FJA", cat)
                if e:
                    res[cat].append(e)
                    counts[cat] += 1
                if counts[cat] >= limit:
                    break
    except Exception as e: print(f"  ❌ FJA Error: {e}")
    return res

def scrape_sarkariexam(limit=5):
    res = {'results': [], 'admit_cards': [], 'latest_jobs': [], 'answer_keys': []}
    counts = {key: 0 for key in res}
    url = "https://www.sarkariexam.com/"
    print(f"\n📡 Scraping SarkariExam ({url})...")
    try:
        html = requests.get(url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, 'html.parser')
        mapping = {'Result': 'results', 'Admit Card': 'admit_cards', 'Exam': 'results', 'Online Form': 'latest_jobs', 'New Updates': 'latest_jobs', 'Answer Key': 'answer_keys'}
        for h in soup.find_all(['h2', 'h3', 'h4']):
            cat = next((v for k, v in mapping.items() if k.lower() in h.get_text().lower()), None)
            if not cat: continue
            if counts[cat] >= limit:
                continue
            nxt = h.find_next_sibling('ul') or h.find_next('ul')
            if not nxt: continue
            for link in nxt.find_all('a')[:limit]:
                title, href = link.text.strip(), link.get('href', '')
                if not title or not href: continue
                full_url = href if href.startswith('http') else 'https://www.sarkariexam.com' + href
                if is_competitor_href(full_url, 'SE'): continue
                e = generate_entry(title, full_url, "SE", cat)
                if e:
                    res[cat].append(e)
                    counts[cat] += 1
                if counts[cat] >= limit:
                    break
    except Exception as e: print(f"  ❌ SE Error: {e}")
    return res

def main():
    started_at = utc_now_iso()
    scrape_status = {
        'status': 'running',
        'started_at': started_at,
        'finished_at': None,
        'duration_seconds': None,
        'counts': {},
        'sources': ['sarkariresult', 'freejobalert', 'sarkariexam'],
        'error': None
    }
    write_json_atomic(SCRAPE_STATUS_FILE, scrape_status)

    started_ts = time.time()
    try:
        all_data = {'status': 'success', 'results': [], 'admit_cards': [], 'latest_jobs': [], 'answer_keys': []}
        for scraper_func in [scrape_sarkariresult, scrape_freejobalert, scrape_sarkariexam]:
            site_data = scraper_func(5)
            for cat in ['results', 'admit_cards', 'latest_jobs', 'answer_keys']:
                all_data[cat].extend(site_data.get(cat, []))

        write_json_atomic(DATA_FILE, all_data)

        finished_at = utc_now_iso()
        scrape_status.update({
            'status': 'success',
            'finished_at': finished_at,
            'duration_seconds': round(time.time() - started_ts, 2),
            'counts': {cat: len(all_data.get(cat, [])) for cat in ['results', 'admit_cards', 'latest_jobs', 'answer_keys']}
        })
        write_json_atomic(SCRAPE_STATUS_FILE, scrape_status)
        print("\n✅ Done! Scraped and saved to data.json")
        return all_data
    except Exception as exc:
        scrape_status.update({
            'status': 'error',
            'finished_at': utc_now_iso(),
            'duration_seconds': round(time.time() - started_ts, 2),
            'error': str(exc)
        })
        write_json_atomic(SCRAPE_STATUS_FILE, scrape_status)
        raise

if __name__ == "__main__":
    main()
