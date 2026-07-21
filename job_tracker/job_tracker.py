#!/usr/bin/env python3
"""医疗AI岗位追踪：每月拉取BOSS直聘/猎聘等平台的关键岗位信息"""
import subprocess, json, re, os
from datetime import datetime

OUTPUT_DIR = "/root/Hermes/knowledge_base/04_规划/岗位追踪"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 标竿岗位搜索关键词
QUERIES = [
    # 医院端
    ("医院信息科/AI", "site:zhipin.com 医院 信息中心 AI OR 数据分析 OR 工程师 2026"),
    # 医疗AI企业端
    ("医疗AI产品经理", "医疗AI产品经理 25K BOSS直聘 2026"),
    ("医疗AI算法", "医疗AI 算法 OR 大模型 工程师 薪资 BOSS直聘 2026"),
    # HIS厂商
    ("HIS厂商AI岗位", "卫宁健康 OR 创业慧康 OR 东华软件 AI OR 大模型 招聘 2026"),
    # 医学顾问/临床顾问
    ("医学顾问AI", "医学顾问 OR 临床顾问 AI OR 大模型 医疗 招聘 2026"),
    # 与国际对比
    ("美国临床信息学", "clinical informatics AI hospital hiring 2026 salary"),
]

def search(query, label):
    try:
        result = subprocess.run(
            ["curl", "-sL", "-H", "User-Agent: Mozilla/5.0", f"https://www.baidu.com/s?wd={query}&rn=5"],
            capture_output=True, text=True, timeout=15
        )
        # 提取搜索结果摘要
        snippets = re.findall(r'<div class="c-abstract">(.*?)</div>', result.stdout, re.DOTALL)[:5]
        if not snippets:
            snippets = re.findall(r'<span class="content-right_[^"]*">(.*?)</span>', result.stdout, re.DOTALL)[:5]
        text = '\n'.join(s.strip() for s in snippets) if snippets else "（无结果）"
        return f"## {label}\n{text[:2000]}"
    except Exception as e:
        return f"## {label}\n搜索失败: {e}"

def check_known_companies():
    """检查已知医疗AI公司的招聘动态"""
    companies = [
        "联影智能", "深睿医疗", "推想医疗", "医渡科技",
        "腾讯健康", "阿里健康", "数坤科技", "鹰瞳科技",
    ]
    results = []
    for c in companies:
        try:
            r = subprocess.run(
                ["curl", "-sL", f"https://www.baidu.com/s?wd={c} 招聘 AI 2026&rn=3"],
                capture_output=True, text=True, timeout=10
            )
            count = len(re.findall(r'c-abstract', r.stdout))
            results.append(f"- {c}: {'有招聘信息' if count > 0 else '未检测到招聘'}")
        except:
            results.append(f"- {c}: 检查失败")
    return "## 已知公司动态\n" + "\n".join(results)

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    content = [f"# 医疗AI岗位追踪月报\n**生成时间:** {today}\n"]
    
    for label, q in QUERIES:
        content.append(search(q, label))
    
    content.append(check_known_companies())
    
    # 关键指标汇总
    content.append(f"""
## 关键指标变化
| 指标 | 本月 | 上月变化 |
|------|------|----------|
| 医院信息科AI岗位 | （待填写） | — |
| 医疗AI产品经理薪资区间 | （待填写） | — |
| 医疗AI算法岗薪资区间 | （待填写） | — |
| 医学顾问/临床顾问岗数量 | （待填写） | — |
""")
    
    out = os.path.join(OUTPUT_DIR, f"岗位追踪_{today}.md")
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(content))
    print(f"✅ {out}")

if __name__ == "__main__":
    main()
