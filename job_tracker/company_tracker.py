#!/usr/bin/env python3
"""医疗AI企业岗位追踪：每月监测目标公司的招聘变化（使用web_search API）"""
import os, json, sys
from datetime import datetime

OUTPUT_DIR = "/root/Hermes/knowledge_base/04_规划/岗位追踪"
os.makedirs(OUTPUT_DIR, exist_ok=True)

COMPANIES = [
    "联影智能", "深睿医疗", "推想医疗", "数坤科技",
    "鹰瞳科技", "医渡科技", "卫宁健康", "嘉和美康",
]

ROLES = [
    "医疗AI产品经理 薪资 2026",
    "医疗AI 算法工程师 薪资 2026",
    "医学顾问 临床 AI 招聘 薪资 2026",
    "AI Agent 医疗 招聘 2026",
]

def search(query, limit=5):
    """使用web_search"""
    try:
        from hermes_tools import web_search
        r = web_search(query=query, limit=limit)
        return r.get("data", {}).get("web", [])
    except Exception as e:
        print(f"[WARN] web_search failed: {e}", file=sys.stderr)
        return []

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 公司状态
    company_lines = []
    for c in COMPANIES:
        items = search(f"{c} AI 招聘 2026", 5)
        titles_descs = [(x.get("title","") + " " + x.get("description","")) for x in items]
        has_job = any("招聘" in td or "岗位" in td for td in titles_descs)
        status = "🟢 有招聘" if has_job else "⚪ 未检测到"
        # 提取关键岗位
        key_posts = []
        for item in items:
            t = item.get("title","")
            d = item.get("description","")[:100]
            if "招聘" in t or "岗位" in t:
                key_posts.append(f"{t}: {d}")
        company_lines.append(f"| {c} | {status} | {'; '.join(key_posts[:2])} |")
    
    # 薪资数据
    role_lines = []
    for r in ROLES:
        items = search(r, 5)
        salary_info = []
        for item in items:
            t = item.get("title","")
            d = item.get("description","")[:100]
            salary_info.append(f"{t}")
        role_lines.append(f"| {r} | {'; '.join(salary_info[:2])} |")
    
    md = f"""# 医疗AI企业岗位追踪月报
**生成时间:** {today}
**数据来源:** web_search聚合（BOSS直聘/猎聘/牛客网等）

---

## 一、目标公司招聘状态
| 公司 | 状态 | 关键信息 |
|------|------|---------|
{chr(10).join(company_lines)}

## 二、关键岗位薪资区间
| 岗位 | 信息摘要 |
|------|---------|
{chr(10).join(role_lines)}

## 三、月度变化

**新增岗位:**
- （待填写）

**消失岗位:**
- （待填写）

**薪资变化:**
- （待填写）

**值得关注的信号:**
- （待填写）

---

*下次更新: 2026-08-01*
"""
    out = os.path.join(OUTPUT_DIR, f"企业岗位追踪_{today}.md")
    with open(out, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"✅ {out}")

if __name__ == "__main__":
    main()
