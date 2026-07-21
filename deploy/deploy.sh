#!/bin/bash
# deploy.sh — 服务器从 GitHub 拉取最新稳定版本
# 用法: bash deploy/deploy.sh
# 假设: 已在 repo 根目录执行（git clone 的位置）

set -e

echo "🔄 Pulling latest stable version from GitHub..."
git pull origin main

echo "✅ Deploy complete at $(date)"
echo "   Branch: $(git rev-parse --abbrev-ref HEAD)"
echo "   Commit: $(git rev-parse --short HEAD)"
