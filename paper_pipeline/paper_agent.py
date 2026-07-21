#!/usr/bin/env python3
"""
医学文献Agent系统 — 核心框架
三模块：search → download → summary
队列驱动，认证失效时不阻塞
"""
import sqlite3, os, json, time, hashlib, sys
from datetime import datetime, timedelta

BASE = "/root/Hermes"
DB_PATH = os.path.join(BASE, "paper_agent.db")
PDF_DIR = os.path.join(BASE, "knowledge_base", "papers")
os.makedirs(PDF_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pmid TEXT UNIQUE,
            doi TEXT,
            title TEXT,
            journal TEXT,
            pubdate TEXT,
            authors TEXT,
            url TEXT,
            status TEXT DEFAULT 'discovered',
            -- discovered | open_access | carsi_needed | downloaded | analysed | failed
            pdf_path TEXT,
            has_fulltext INTEGER DEFAULT 0,
            carsi_attempts INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS carsi_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cookie_json TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            is_valid INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS daily_brief (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            file_path TEXT,
            paper_count INTEGER,
            analysed_count INTEGER
        );
    """)
    conn.commit()
    conn.close()
    print("DB初始化完成")

# ====== 论文搜索 ======
def search_pubmed(query, max_results=10):
    """搜PubMed，返回论文列表"""
    import urllib.request, urllib.parse, json
    
    params = urllib.parse.urlencode({
        'db': 'pubmed', 'term': query,
        'retmax': max_results, 'sort': 'relevance', 'retmode': 'json'
    })
    try:
        resp = urllib.request.urlopen(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}",
            timeout=15
        )
        ids = json.loads(resp.read()).get('esearchresult', {}).get('idlist', [])
        
        # 获取详情
        if ids:
            params2 = urllib.parse.urlencode({
                'db': 'pubmed', 'id': ','.join(ids),
                'retmode': 'json', 'retmax': max_results
            })
            resp2 = urllib.request.urlopen(
                f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{params2}",
                timeout=15
            )
            data = json.loads(resp2.read())
            papers = []
            for uid in data.get('result', {}).get('uids', []):
                info = data['result'][uid]
                doi = info.get('elocationid', '')
                if doi.startswith('doi:'):
                    doi = doi[4:].strip()
                papers.append({
                    'pmid': uid,
                    'doi': doi,
                    'title': info.get('title', ''),
                    'journal': info.get('source', ''),
                    'pubdate': info.get('pubdate', ''),
                    'authors': ', '.join(a.get('name','') for a in info.get('authors', [])[:5]),
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"
                })
            return papers
    except Exception as e:
        print(f"  PubMed搜索失败: {e}")
    return []

def save_papers(papers):
    """保存论文到库"""
    conn = get_db()
    saved = 0
    for p in papers:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO papers (pmid, doi, title, journal, pubdate, authors, url, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'discovered')
            """, (p['pmid'], p['doi'], p['title'], p['journal'],
                  p['pubdate'], p['authors'], p['url']))
            saved += conn.total_changes
        except:
            pass
    conn.commit()
    conn.close()
    return saved

def check_open_access(pmid):
    """检查PMC是否可免费获取"""
    import urllib.request, json
    try:
        resp = urllib.request.urlopen(
            f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json",
            timeout=10
        )
        data = json.loads(resp.read())
        records = data.get('records', [])
        if records and 'pmcid' in records[0]:
            pmcid = records[0]['pmcid']
            return pmcid
    except:
        pass
    return None

def download_pmc_pdf(pmcid, save_path):
    """从PMC下载PDF"""
    import urllib.request
    url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/main.pdf"
    try:
        resp = urllib.request.urlopen(url, timeout=30)
        with open(save_path, 'wb') as f:
            f.write(resp.read())
        return True
    except:
        return False

def get_abstract(pmid):
    """获取摘要"""
    import urllib.request, re
    try:
        resp = urllib.request.urlopen(
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&retmode=xml&rettype=abstract",
            timeout=15
        )
        xml = resp.read().decode('utf-8')
        m = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>', xml, re.DOTALL)
        return re.sub(r'<[^>]+>', '', m.group(1))[:2000] if m else ''
    except:
        return ''

# ====== 下载队列 ======
def get_download_queue():
    """获取待下载队列"""
    conn = get_db()
    rows = conn.execute("""
        SELECT id, pmid, doi, title, journal FROM papers 
        WHERE status IN ('discovered', 'carsi_needed')
        ORDER BY carsi_attempts ASC, created_at ASC
        LIMIT 10
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_status(pid, status, pdf_path=None):
    conn = get_db()
    conn.execute("UPDATE papers SET status=?, updated_at=datetime('now') WHERE id=?",
                 (status, pid))
    if pdf_path:
        conn.execute("UPDATE papers SET pdf_path=?, has_fulltext=1 WHERE id=?", (pdf_path, pid))
    conn.commit()
    conn.close()

# ====== CARSI管理器 ======
def get_carsi_cookies():
    """获取保存的Cookie"""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM carsi_session WHERE is_valid=1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        expires = row['expires_at']
        if expires and datetime.now() < datetime.fromisoformat(expires):
            return json.loads(row['cookie_json'])
    return None

def save_carsi_cookies(cookies, expires_days=30):
    conn = get_db()
    expires = (datetime.now() + timedelta(days=expires_days)).isoformat()
    conn.execute("""
        INSERT INTO carsi_session (cookie_json, expires_at, is_valid)
        VALUES (?, ?, 1)
    """, (json.dumps(cookies), expires))
    conn.commit()
    conn.close()

# ====== 日报生成 ======
def generate_brief(papers_data, output_path):
    """用DeepSeek生成结构化简报"""
    from openai import OpenAI
    
    # 读DeepSeek key
    key = ""
    with open("/root/.hermes/.env") as f:
        for line in f:
            if line.startswith("DEEPSEEK_API_KEY="):
                key = line.split("=", 1)[1].strip()
    
    client = OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
    
    report = f"# 每日医学AI论文简报\n**日期:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    for p in papers_data[:10]:
        analysis = "分析失败"
        try:
            prompt = f"""分析以下医学论文，输出JSON:
{{"领域":"","方法":"","创新点":"","结论":"","相关度":"高/中/低"}}
标题: {p['title']}
期刊: {p['journal']}
摘要: {p.get('abstract','')[:1500]}"""
            resp = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=500
            )
            analysis = resp.choices[0].message.content
        except:
            pass
        
        report += f"\n## {p['title']}\n**{p['journal']}** | PMID: {p['pmid']}\n\n{analysis}\n---\n"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    return output_path

# ====== 主调度 ======
def daily_run():
    """每日执行"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n=== 每日文献Agent [{today}] ===\n")
    
    from openai import OpenAI
    key = ""
    with open("/root/.hermes/.env") as f:
        for line in f:
            if line.startswith("DEEPSEEK_API_KEY="):
                key = line.split("=", 1)[1].strip()
    llm = OpenAI(api_key=key, base_url="https://api.deepseek.com/v1")
    
    # 1. 搜索
    queries = [
        '"large language model" AND medical AND 2026[dp]',
        '"clinical AI" OR "medical agent" AND 2026[dp]',
        '"clinical reasoning" AND "large language model" AND 2026[dp]',
    ]
    
    all_papers = []
    for q in queries:
        papers = search_pubmed(q, max_results=8)
        all_papers.extend(papers)
        time.sleep(0.3)
    
    # 去重
    seen = set()
    unique = []
    for p in all_papers:
        if p['pmid'] not in seen:
            seen.add(p['pmid'])
            unique.append(p)
    
    print(f"搜索到 {len(unique)} 篇论文")
    
    # 2. 入库
    n = save_papers(unique)
    print(f"新增 {n} 篇")
    
    # 3. 检查Open Access
    conn = get_db()
    discovered = conn.execute(
        "SELECT id, pmid, title FROM papers WHERE status='discovered' AND has_fulltext=0"
    ).fetchall()
    conn.close()
    
    fulltext = []
    for row in discovered:
        pmcid = check_open_access(row['pmid'])
        if pmcid:
            pdf_path = os.path.join(PDF_DIR, f"{pmcid}.pdf")
            if download_pmc_pdf(pmcid, pdf_path):
                update_status(row['id'], 'downloaded', pdf_path)
                fulltext.append(dict(row))
                print(f"  ✅ PMC: {row['title'][:60]}")
                time.sleep(1)
    
    # 4. CARSI队列（标记需要登录的）
    conn = get_db()
    carsi_pending = conn.execute(
        "SELECT id, pmid, title FROM papers WHERE status='discovered' AND has_fulltext=0"
    ).fetchall()
    conn.close()
    for row in carsi_pending:
        update_status(row['id'], 'carsi_needed')
    
    if carsi_pending:
        print(f"\n⚠️ {len(carsi_pending)} 篇需要CARSI登录下载")
    
    # 5. 获取摘要用于简报
    papers_for_brief = []
    for p in unique[:10]:
        p['abstract'] = get_abstract(p['pmid'])
        time.sleep(0.3)
        papers_for_brief.append(p)
    
    # 6. 生成简报
    brief_dir = os.path.join(BASE, "knowledge_base", "01_时间链", "日报")
    os.makedirs(brief_dir, exist_ok=True)
    brief_path = os.path.join(brief_dir, f"daily_{today}.md")
    generate_brief(papers_for_brief, brief_path)
    
    print(f"\n✅ 简报已生成: {brief_path}")
    print(f"   {len(fulltext)} 篇全文下载, {len(carsi_pending)} 篇待CARSI")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init_db()
    elif len(sys.argv) > 1 and sys.argv[1] == "search":
        daily_run()
    else:
        print("用法: python3 paper_agent.py init|search")
