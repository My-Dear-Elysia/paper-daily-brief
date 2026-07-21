"""
批量从文字版PDF提取全文（pymupdf）
输出格式与OCR管线一致：## Page N 分隔 + 文件头
"""
import fitz, os, sys, time
from datetime import datetime

KB_DIR = "/root/Hermes/knowledge_base"
SRC_DIR = "/root/Hermes/course file"
os.makedirs(KB_DIR, exist_ok=True)

# 要提取的PDF列表: (输出名, 路径)
PDFS = [
    ("Principles of Neural Science（第5版）", "Principles of Neural Science(the 5th edition).pdf"),
    ("First Aid For USMLE Step 1", "First Aid Cases For The USMLE Step 1（公众号：在逃小番茄Lynn）.pdf"),
    ("First Aid For USMLE Step 2 CK", "《First Aid For The USMLE Step 2 CK》（公众号：在逃小番茄Lynn）.pdf"),
    ("盖顿生理学", "《盖顿 physiology》（公众号：在逃小番茄Lynn）.pdf"),
    ("癌生物学（The Biology of Cancer）", "癌生物学/The Biology of Cancer - 2nd edition.pdf"),
]

# 修正盖顿生理学文件名
import glob
actual_guyton = glob.glob(SRC_DIR + "/*盖顿*生理学*.pdf")
if actual_guyton:
    PDFS[3] = ("盖顿生理学", os.path.basename(actual_guyton[0]))

total_start = time.time()

for name, rel_path in PDFS:
    full_path = os.path.join(SRC_DIR, rel_path)
    if not os.path.exists(full_path):
        print(f"[跳过] 未找到: {rel_path}")
        continue
    
    t0 = time.time()
    doc = fitz.open(full_path)
    total = len(doc)
    
    out_path = os.path.join(KB_DIR, f"{name}.md")
    print(f"[开始] {name} ({total}页)")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# {name}\n")
        f.write(f"**创建时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**总页数:** {total}\n")
        f.write(f"**来源:** 文字版直接提取 (pymupdf)\n\n")
    
    for p in range(total):
        text = doc[p].get_text().strip()
        if not text:
            text = "*[此页无文字]*"
        
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(f"\n## Page {p+1}\n{text}\n")
        
        if (p + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (p + 1) / elapsed * 60 if elapsed > 0 else 0
            print(f"  [{p+1}/{total}] {elapsed:.0f}s ({rate:.0f}页/分)")
    
    doc.close()
    elapsed = time.time() - t0
    print(f"  ✔ 完成 ({elapsed:.0f}s, {total/elapsed*60:.0f}页/分)")
    print()

total_elapsed = time.time() - total_start
print(f"全部提取完成，耗时 {total_elapsed:.0f}s ({total_elapsed/60:.1f}min)")
