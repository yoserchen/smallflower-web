#!/bin/bash
# 把 Q故事 的 213 張原圖壓成網站用的大小，放進 public/s/。
#
#   public/s/2024/11/IMG_8376.jpeg      長邊 1200px  ← 故事頁面裡看的
#   public/s/t/2024/11/IMG_8376.jpeg    長邊 480px   ← 清單的小圖
#
# 用 macOS 內建的 sips，不用裝任何東西。
# 原圖留在 ~/Documents/花曆更新/故事/圖片/ 不要刪，那是你的底片。
# 壓過的會跳過，所以中斷了再跑一次就好。

SRC=~/Documents/花曆更新/故事/圖片
DST=~/Documents/smallflower-web/public/s

[ -d "$SRC" ] || { echo "找不到原圖資料夾：$SRC"; exit 1; }
mkdir -p "$DST"

n=0
while IFS= read -r f; do
  rel="${f#$SRC/}"
  big="$DST/$rel"
  thumb="$DST/t/$rel"
  if [ ! -s "$big" ]; then
    mkdir -p "$(dirname "$big")"
    sips -Z 1200 -s format jpeg -s formatOptions 80 "$f" --out "$big" >/dev/null 2>&1
  fi
  if [ ! -s "$thumb" ]; then
    mkdir -p "$(dirname "$thumb")"
    sips -Z 480 -s format jpeg -s formatOptions 72 "$f" --out "$thumb" >/dev/null 2>&1
  fi
  n=$((n+1))
  [ $((n % 25)) -eq 0 ] && echo "  已處理 $n 張…"
done < <(find "$SRC" -type f \( -iname '*.jpeg' -o -iname '*.jpg' -o -iname '*.png' \))

echo
echo "完成 $n 張"
echo -n "原圖共 "; du -sh "$SRC" | cut -f1
echo -n "壓縮後共 "; du -sh "$DST" | cut -f1
