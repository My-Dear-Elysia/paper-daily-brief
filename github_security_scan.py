#!/usr/bin/env python3
"""GitHub 安全扫描：检查所有公开仓库的敏感信息泄露"""
import os, sys, json, re, subprocess, urllib.request, urllib.parse, base64, tempfile, shutil

TOKEN = os.environ.get("GITHUB_TOKEN", "")
USER = "WentaoLi-Med"
SCAN_PATTERNS = [
    ("API密钥", r'(?i)(sk-[A-Za-z0-9]{20,}|tvly-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36,}|gho_[A-Za-z0-9]{36,}|xox[bpras]-[A-Za-z0-9-]+|AIza[A-Za-z0-9_-]{35})'),
    ("本地路径", r'(/root/|/home/|D:\\|C:\\|/Users/)'),
    ("个人信息", r'(3465431384|34654@qq\.com|xschang@163\.com)'),
    ("硬编码密钥", r'(DEEPSEEK_API_KEY|TAVILY_API_KEY|OPENAI_API_KEY)\s*[=:]\s*["\'](?!$)'),
]
EXT_FILTER = r'\.(py|json|md|sh|yaml|yml|toml|txt|env|conf|js|html)$'

def api_get(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    if TOKEN: req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    return json.loads(urllib.request.urlopen(req, timeout=15).read())

def get_repos():
    repos = []
    for r in api_get(f"/users/{USER}/repos?per_page=100&type=public"):
        if r.get('fork') or r.get('private'): continue
        if r.get('size', 0) == 0: continue  # 跳过空仓库
        repos.append(r)
    return repos

def scan_repo(name, branch):
    """使用GitHub Code Search API搜索敏感关键词"""
    issues = []
    # 搜索各类非公开信息（防止使用者意外泄露）
    # 注意：search API 只支持关键词搜索，不支持正则；过短的词会导致过多结果
    keywords = [
        # API密钥特征（key= 后跟非占位符内容）
        ("硬编码密钥", '_API_KEY="sk-'),    # DeepSeek/OpenAI
        ("硬编码密钥", '_API_KEY="tvly-'),  # Tavily
        ("硬编码密钥", '_API_KEY="ghp_'),   # GitHub
        ("硬编码密钥", '_API_KEY="AKIA'),   # AWS
        ("硬编码密钥", '_API_KEY="AIza'),   # Google
        ("硬编码密钥", '_API_KEY="xoxb-'),  # Slack
        # 显式密钥赋值（等号后跟具体值，不是占位符）
        ("硬编码密钥", 'DEEPSEEK_API_KEY='),
        ("硬编码密钥", 'TAVILY_API_KEY='),
        ("硬编码密钥", 'OPENAI_API_KEY='),
        ("硬编码密钥", 'GITHUB_TOKEN='),
        ("硬编码密钥", 'GITHUB_PERSONAL_ACCESS_TOKEN='),
        ("硬编码密钥", 'ACCESS_PASSWORD='),
        # 本地Windows路径
        ("本地路径", 'D:/'),
        ("本地路径", 'E:/'),
        ("本地路径", 'C:/Users/'),
        # SSH私钥块
        ("SSH密钥", '-----BEGIN'),
        # 数据库连接串（不含占位符示例）
        ("数据库", 'postgresql://'),
        ("数据库", 'mysql://'),
        ("数据库", 'mongodb://'),
        ("数据库", 'redis://'),
    ]
    for label, keyword in keywords:
        try:
            q = urllib.parse.quote(f'repo:{USER}/{name} "{keyword}"')
            resp = json.loads(urllib.request.urlopen(
                urllib.request.Request(
                    f"https://api.github.com/search/code?q={q}&per_page=30",
                    headers={"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}
                ), timeout=15
            ))
            for item in resp.get('items', []):
                fpath = item['path']
                if not re.search(EXT_FILTER, fpath): continue
                try:
                    c = base64.b64decode(api_get(item['url'].replace('https://api.github.com', ''))['content']).decode()
                    for n, line in enumerate(c.split('\n'), 1):
                        if keyword in line:
                            issues.append((label, f"{name}/{fpath}:{n}", line.strip()[:120]))
                except: pass
        except: pass
    return issues

def main():
    repos = get_repos()
    print(f"=== GitHub 安全扫描 ({USER}) ===\n公开仓库数: {len(repos)}\n")
    all_issues = []
    for repo in repos:
        name = repo['name']
        branch = repo['default_branch']
        print(f"扫描: {name}...", end=" ", flush=True)
        issues = scan_repo(name, branch)
        if not issues:
            print("✅")
        else:
            print(f"⚠️ {len(issues)} 个问题")
            for label, loc, snippet in issues:
                all_issues.append((label, loc, snippet))
                print(f"  [{label}] {loc}\n    {snippet}")
    print(f"\n总计: {len(all_issues)} 个问题")
    for label, loc, _ in all_issues:
        print(f"  ⚠️ [{label}] {loc}")

if __name__ == "__main__":
    main()
