# 配色與頁面狀態補查（2026-09-12）

擁有者指出本機啟動器提示頁仍有米色底部、貼邊巨型標題。前輪動態驗證集中在已登入管理工作區，未包含登入前的狀態分支，不能稱為全站視覺驗收。本輪按入口與狀態盤點修復。

## 根因與修復

- `LocalLaunchAccessPanel` 原先直接輸出無樣式的段落／section；其 h1 繼承公開首頁的展示字級。現在與 `AdminAccessPanel` 共用新增的 `AdminAccessLayout`，取得全頁背景、置中卡片、留白、可換行標題與語意標記。
- `App` 的管理模組載入 fallback 同樣原為裸段落，現在也使用共用框架。
- 管理主題原先只定義在 `.admin-workspace`；`body` 內容不足一屏時，根元素的米色背景會露出。現在基礎配色集中於 `:root` 的 `--ui-*`，`--admin-*` 相容名稱引用它們；管理入口同時標記 html/body，body 至少填滿視窗，登入前框架也直接取得主題。
- 掃描發現公開頁的卡片、對話、邊框、陰影、連結與送出按鈕仍使用舊米色／棕色，已接到共用紫色／淡灰／白色體系。狀態警告色與角色插圖的顏色有各自用途，不以背景配色統一之名消除語意或重繪插圖。
- 公開首頁的大標題規則限定在 `.visitor-shell`，管理標題明確設定尺寸與 margin，避免跨頁影響。
- 登入前的 input 使用共用欄位背景／邊框／內距；英文標題不再強制 nowrap。登入前提示、錯誤、按鈕與手機卡片陰影改用主題變數。

本輪修改：`apps/web/src/styles.css`、`apps/web/src/main.tsx`、`apps/web/src/app/App.tsx`、`apps/web/src/features/admin/AdminPage.tsx`、`LocalLaunchAccessPanel.tsx`，新增 `AdminAccessLayout.tsx` 與 `LocalLaunchAccessPanel.test.tsx`。原有登入授權、啟動器要求及狀態轉換均保留；沒有引入新服務或 API。

## 頁面狀態清單與證據

| 入口／狀態                     | 正式元件                        | 本輪動態覆蓋                                                           |
| ------------------------------ | ------------------------------- | ---------------------------------------------------------------------- |
| 管理模組載入                   | App fallback／AdminAccessLayout | 共用框架的合成載入畫面；沒有注入真實模組下載故障                       |
| 本機工作階段確認、要求重新啟動 | LocalLaunchAccessPanel          | checking、relaunch                                                     |
| 首次設定狀態載入               | AdminAccessPanel                | loading                                                                |
| 管理員登入及登入失敗           | AdminAccessPanel                | login、login-error                                                     |
| 首次設定                       | AdminAccessPanel                | setup                                                                  |
| 恢復管理存取                   | AdminAccessPanel                | recovery                                                               |
| 設定服務不可用                 | AdminAccessPanel                | unavailable                                                            |
| 公開作品集                     | App                             | 合成長內容的卡片、背景、字色、邊框與頁面寬度                           |
| 已登入工作區、引導／模型／草稿 | AdminWorkspace 等               | 本輪保留同值主題別名；沿用前輪元件與事件證據，不把前輪結果冒充本輪重跑 |

九種登入前合成畫面 × 中英文 × 100%／200% 根字體 × 320／375／768／1440px，共 **144 組斷言通過**：html、body、shell 的背景一致，無頁面橫向溢出、卡片／標題裁切，單一 main landmark，shell 至少填滿視窗。公開頁另有 **4 種寬度通過**，背景 rgb(248,247,252)、白色卡片、深紫文字及共用邊框均符合目前主題。桌面啟動器畫面已實際擷取並目視檢查。

可重跑材料：`tests/browser/access-theme-review.tsx`（無伺服器動作的合成狀態選擇器）、`tests/browser/access-theme-matrix-2026-09-12.json`（最終實測資料）。使用 `tests/browser/README.md` 的複製／Vite 方法，reviewName 設為 `access-theme`；逐一選 Scenario、Language、Text size。這是元件／樣式驗證，不是實際登入、啟動器安全性或模組載入故障的端到端驗收。200% 指根字體放大，不是瀏覽器原生 zoom。

最終 `pnpm run web:check`（2026-09-12 15:06，Asia/Taipei）：格式、ESLint、TypeScript、125 個測試（20 檔）及正式建置通過；ESLint 為 0 errors、12 個既有 Fast Refresh warnings。新增四組雙語 checking／relaunch 測試，驗證主題框架、標題、載入狀態與不存在未授權登入／重試操作。沒有修改後端，未重跑 Docker、真實登入或模型服務。測試用 app 入口已移除，服務停止、視窗尺寸復原。

對應 FR-014／022／025／040、NFR-003／008／009，以及 AC-019／023／040／057 的部分呈現行為。既有真人新手走查、完整讀屏與瀏覽器原生 zoom 驗收仍不能由這些測試取代。本輪配色修復沒有待擁有者批准的事項；前輪資訊架構簡化提案維持未實作。
