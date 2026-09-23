# 小花老師的花曆　網站

網址：https://smallflower.tw

一個網站放多個花曆，用子路徑分開：

| 路徑 | 內容 |
|---|---|
| `/` | 首頁，列出所有花曆 |
| `/tpbg/` | 台北植物園花曆 |
| `/tpbg/month/9/` | 九月開的花 |
| `/tpbg/flower/薑-07/` | 單一種花 |
| `/tpbg/map/` | 用地圖編號查花（口袋地圖的 QR 指向這裡） |
| `/support/`、`/about/` | 全站共用 |

## 本機執行

```bash
npm install     # 第一次才需要
npm run dev     # 開發模式，瀏覽器開 http://localhost:4321
npm run build   # 產生正式檔案到 dist/
```

## 要改文字或連結

改 `src/config.mjs`：站名、FB 網址、YouTube 頻道、贊助連結，
以及每個花曆的名稱、簡介、地圖版本年份。

## 要新增一個花曆（例如合歡山）

1. 把資料檔放進 `src/data/hehuan.json`
2. 在 `src/config.mjs` 的 `CALENDARS` 加一筆，`slug` 填 `hehuan`

頁面、花鐘、月份、搜尋全部共用，不用另外寫程式。
沒有地圖編號的花曆把 `hasMap` 設成 false，相關欄位會自動不顯示。

## 要更新花的資料

換掉 `src/data/<slug>.json`，重新 build 即可。這個檔案由 Claude 從
主檔試算表、My Maps 位置和名稱對照表產生。

## 部署

推到 GitHub 後由 Cloudflare Pages 自動建置。
建置指令 `npm run build`，輸出目錄 `dist`，框架選 Astro。
