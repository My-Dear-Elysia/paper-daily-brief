#!/bin/bash
# 从config.yaml读DashScope API key（key在api_key:的下一行）
KEY=$(python3 -c "
with open('/root/.hermes/config.yaml') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'api_key' in line and i+1 < len(lines):
        k = lines[i+1].strip()
        if k: print(k)
        break
")
export DASHSCOKE_API_KEY="$KEY"
PDF="$1"
echo "Starting OCR: $(basename "$PDF")"
python3 /root/Hermes/ocr_pipeline.py "$PDF"
