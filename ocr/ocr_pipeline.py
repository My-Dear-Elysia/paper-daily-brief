"""
单PDF逐页OCR管线 — Qwen-vl-max via DashScope
每页：渲染300DPI → base64 → API OCR → 追加MD → 释放
审计点：33%/66%/100% 时保存检查点并退出，等待审计后重启
用法：python3 ocr_pipeline.py "<pdf_path>"
"""

import fitz, base64, json, os, sys, time
from datetime import datetime
from openai import OpenAI

PDF_PATH = sys.argv[1]
PDF_NAME = os.path.splitext(os.path.basename(PDF_PATH))[0]
BASE_DIR = "/root/Hermes/knowledge_base"
AUDIT_DIR = "/root/Hermes/_ocr_audit"
OUTPUT_MD = os.path.join(BASE_DIR, f"{PDF_NAME}.md")
CHECKPOINT = os.path.join(BASE_DIR, f"_ckpt_{PDF_NAME}.json")
AUDIT_FLAG = os.path.join(AUDIT_DIR, f"{PDF_NAME}.flag")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(AUDIT_DIR, exist_ok=True)

client = OpenAI(
    api_key=os.environ.get("DASHSCOKE_API_KEY", ""),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 恢复检查点
results = {}
start_page = 0
if os.path.exists(CHECKPOINT):
    with open(CHECKPOINT) as f:
        ckpt = json.load(f)
        results = ckpt.get("results", {})
        last = max(int(k) for k in results) if results else -1
        start_page = last + 1
    print(f"[恢复] 第 {start_page+1} 页继续 ({len(results)} 页已有)")

doc = fitz.open(PDF_PATH)
total = len(doc)
print(f"[开始] {PDF_NAME} ({total} 页)")

audit_33 = int(total * 0.33)
audit_66 = int(total * 0.66)

# 如果输出MD不存在，写文件头
if start_page == 0:
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(f"# {PDF_NAME}\n**创建时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n**总页数:** {total}\n\n")

for p in range(start_page, total):
    page = doc[p]
    pix = page.get_pixmap(dpi=300)
    b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
    
    text = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="qwen-vl-max",
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": "完整提取这一页的所有中文和英文字，保留标题、段落、表格和标注。不要总结省略。直接输出原文。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]}],
                max_tokens=4096, timeout=120
            )
            text = resp.choices[0].message.content.strip()
            break
        except Exception as e:
            print(f"  [重试] P{p+1}: {e}")
            time.sleep(10)
    
    results[str(p)] = text if text else "[OCR失败]"
    
    with open(OUTPUT_MD, "a", encoding="utf-8") as f:
        f.write(f"\n## Page {p+1}\n{results[str(p)]}\n")
    
    del pix, b64  # 释放内存
    
    if (p + 1) % 10 == 0:
        print(f"  [{p+1}/{total}] {((p+1)/total*100):.0f}%")
    
    # 检查点
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump({"results": results, "last_page": p}, f, ensure_ascii=False)
    
    # 审计点到达 → 输出样本页 → 退出
    if p + 1 == audit_33 or p + 1 == audit_66 or p + 1 == total:
        stage = f"{p+1}/{total} ({(p+1)/total*100:.0f}%)"
        # 提取样本：本段前3页和后3页
        sample_start = max(start_page, p - 5)
        sample_pages = list(range(sample_start, p + 1))
        sample_text = "\n".join([f"--- Page {s+1} ---\n{results.get(str(s),'')[:200]}..." for s in sample_pages])
        
        with open(AUDIT_FLAG, "w", encoding="utf-8") as f:
            f.write(f"审计点 {stage}\n{OUTPUT_MD}\n\n样本页:\n{sample_text}")
        print(f"\n=== 审计点 {stage} ===")
        print(f"输出: {OUTPUT_MD}")
        print(f"Flag: {AUDIT_FLAG}")
        print("等待Agent审计...\n")
        doc.close()
        sys.exit(0)

doc.close()
print(f"\n✔ {PDF_NAME} 全部完成")
