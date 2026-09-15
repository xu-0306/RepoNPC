# 分析 JSON 失敗診斷 — 2026-09-13

狀態：歷史診斷保留；後續使用者已批准 8,192 預設／16,384 最大的管理分析預算，並於 2026-09-14 以規格 0.3.0 / ADR-037 將公開聊天改為 4,096／8,192、分析 active/provider timeout 改為 1,800／300 秒與可配置安全上限。第 1–6 節描述當時證據與修復歷程，不代表目前仍採 1,000-token、120 秒或 45 秒限制。

範圍：FR-025、FR-027、FR-033；AC-039、AC-040、AC-045。先處理管理端分析失敗，不以更換 RAG 框架作為前提。

## 結論

最新批次可確認是模型回應解析／schema 驗證失敗，但無法從既有資料證明究竟是截斷、JSON 語法、包裝文字或欄位問題。失敗回應與 token usage 沒有持久化；現有 `PROVIDER_OUTPUT_SCHEMA_INVALID` 合併了多種原因。

已用目前程式與合成資料重現：非空回應即使以 `finish_reason=length` 結束，仍進入分析解析；截斷 JSON 被誤歸為一般 schema 錯誤。如果內容剛好是合法 JSON，分析甚至會忽略 `length` 而接受。

800 tokens 是管理端分析的固定程式限制，不是已探測的模型能力。它對最多六項雙語敘述及證據 ID 偏緊，但不能把它直接認定為歷史失敗的唯一原因。

## 1. 實際批次證據

以唯讀 SQLite 連線檢查 `runtime-data/local/runtime.sqlite` 的批次、項目與事件；未讀取或輸出金鑰、端點、原始提示詞或原始模型回應。

最新批次 `pyRhit9xCeKu0-dfMaeLH3Lw`：2026-09-13 17:31:44 至 17:32:28（Asia/Taipei）。

| 專案 | 生成次數 | 最後階段與結果 |
| --- | ---: | --- |
| `anti-hardcode-engineering` | 1 | 17:32:06.124 開始生成，17:32:28.477 進入驗證，隨即 `PROVIDER_OUTPUT_SCHEMA_INVALID` |
| `STT_extension` | 0 | indexing 階段失敗，未執行聊天生成 |
| `framefit-media-shrinker` | 0 | indexing 階段失敗，未執行聊天生成 |

聊天設定記錄為 `claude-sonnet-5`、`openai_compatible`；名稱不能證明代理後方的實際供應商或 schema 能力。模型呼叫到驗證間約 22.35 秒，因此此項記錄不是 provider timeout。

事件未保存 `finish_reason`、input/output token usage 或 JSON/Pydantic 子類。當前分析快取有零筆記錄；當天服務 log 未找到可回溯的 token usage 記錄。不能從耗時或設定上限推算那次實際輸出了多少 tokens。

另外兩項 embedding 失敗的 2 MiB 回應容量原因，已有先前的合成 Ollama 實驗紀錄；本次只核對它們確實尚未進入聊天生成，未重新呼叫 Ollama。

## 2. 已核實的程式問題與疑點

### A. 終止原因未傳到分析判斷

- `src/reponpc/providers/openai_compatible.py:150` 讀取 `finish_reason`。
- 只有內容為空且原因為 `length` 時，adapter 才拋出 output-limit 診斷；非空內容會連同原因回傳。
- `src/reponpc/admin/onboarding.py:492` 左右的批次分析只把 `provider_result.content` 交給 `_parse_analysis`，未先檢查終止原因。
- `_parse_analysis` 將 JSON 語法與 Pydantic schema 錯誤都映射為同一個公開原因。
- 相對地，`src/reponpc/admin/chat_profiles.py:201` 的模型測試有明確拒絕 `length`。

這是本次已重現的缺陷，尚不能證明歷史回應的終止原因就是 `length`。

### B. 輸出預算有兩層限制

目前實際要求值為：

`min(800, provider.capabilities().max_output_tokens)`

800 位於 `src/reponpc/admin/onboarding.py:43`。管理模型的 capability 預設取自共用聊天設定；`src/reponpc/config/environment.py:645` 的預設值是 1,000、設定硬上限是 2,000。這是程式預設與上限，不是已讀取到的歷史程序實際環境值。

因此只把 800 改成 8,192，預設情況仍會被另一層壓成 1,000。需要分清楚模型實際能力、訪客回答政策與管理分析政策。

Schema 允許最多六項推論，每項含繁中與英文各一個非空字串，以及 1–8 個證據 ID。字串每個最多 2,000 字元。JSON 欄位、雙語內容及 ID 都消耗輸出 tokens；現行提示詞沒有相應的單項字數分配。

### C. 歷史失敗未驗證新版提示詞

最新失敗在 17:32；當前 `onboarding.py` 的 prompt/schema v2 修改時間是 17:54，embedding batching 修改時間是 18:00。既有批次不能作為新版成功或失敗的證據。

`git diff` 確認先前提示詞未完整寫出 JSON envelope、精確欄位與範例，主要依賴 provider 的 schema 參數；先前傳送的 schema 也未包含 Pydantic 的部分字串與證據 ID 數量限制。新版已補上這些，但仍維持 800 tokens。

### D. 模型測試通過不等於分析 schema 已驗證

目前 probe 只要求並檢查 `{"ok":true}`；沒有覆蓋分析的巢狀陣列、雙語欄位或完整限制，也未嚴格拒絕額外欄位。`structured_output=True` 是組裝 adapter 時的設定，並非已確認代理強制遵守完整 schema。

### E. 輸入預算也需一起核對

分析目前是單次概覽檢索，最多八筆證據，證據 context 預算最多 12,000；不是把整個 repo 一次交給聊天模型。`_conservative_token_count` 實際採字元數除以四，不能視為繁中／程式碼的精確或保守 tokenizer。Context packing 也未完整計入 system prompt、證據 ID 清單與 schema 的額外成本。

提高輸出預算時，必須一併預留完整輸入與封裝空間。大型專案的證據覆蓋率是另一個後續品質議題，不能只靠提高輸出上限解決，也不應阻擋此次格式修復。

## 3. 本次驗證

未修改應用程式；以 `.venv/Scripts/python.exe` 執行合成資料診斷，沒有呼叫真實 provider。

| 測試輸入 | 目前結果 |
| --- | --- |
| 正常單項雙語 JSON | 接受 |
| 截斷 JSON | schema-invalid；內部原因 JSONDecodeError |
| Markdown fence 包住合法 JSON | schema-invalid；內部原因 JSONDecodeError |
| 缺少英文欄位 | schema-invalid；內部原因 Pydantic missing |
| 額外頂層欄位 | schema-invalid；內部原因 Pydantic extra_forbidden |
| 合成 HTTP 200、非空截斷內容、finish_reason=length | adapter 回傳成功，分析誤歸 schema-invalid |
| 合成 HTTP 200、合法空 inferences、finish_reason=length | adapter 回傳成功，分析接受 |

後兩項使用注入式假 HTTP transport，實際網路呼叫為零。合成 usage=800 只用來重現行為，不是歷史失敗的 usage。

## 4. 診斷當時的建議（數值已由第 6 節的使用者決策取代）

1. 在解析前判斷截斷／異常終止；保留拒絕不完整結果的規則。
2. 補上受限診斷：請求輸出上限、provider 回報 usage、終止原因，以及封閉的 JSON／schema 錯誤類別。Schema 路徑只使用已知欄位映射；不要記錄原始回應、任意欄位名、validation input 或提示詞。
3. 將管理分析預算與訪客回答預算分開。可用 **4,096 作為一般分析起始值，8,192 作為較完整分析值，16,384 作為待驗證的可配置上限候選**；實際值仍受已確認的模型容量、完整 context 預算、時間及用量政策限制。這些是試驗候選，不是已測定門檻。
4. 較高輸出預算也要檢查 provider deadline 及每專案 120 秒總執行期限，避免將截斷問題轉成 timeout。將輸出預算／生成政策納入分析 cache identity，避免不同深度重用舊結果。
5. 保留現有 Pydantic、證據 ID 與個人歸屬驗證；先用實際分析 schema 驗證所選端點，再決定是否需要小型開源輸出元件。

此次沒有新增自動修復呼叫、重試、第二模型或 provider fallback。管理分析上限提高超過現行 2,000 的規格上限，需連同既有契約及驗收文件修訂；本文件不代替該修訂。

## 5. 開源研究旁支

使用者指定的 in-app browser 研究已完成，保留在既有 ChatGPT 對話：

https://chatgpt.com/c/6aa64ee9-4544-83ee-9fae-2fceb688bb8e

直接閱讀的相關原始碼：

- Haystack `AnswerBuilder`：https://github.com/deepset-ai/haystack/blob/main/haystack/components/builders/answer_builder.py
- txtai `RAG`：https://github.com/neuml/txtai/blob/master/src/python/txtai/pipeline/llm/rag.py
- txtai 最小 RAG 範例：https://github.com/neuml/txtai/blob/master/examples/rag_quickstart.py
- `neuml/rag` 應用範例：https://github.com/neuml/rag/blob/master/rag.py

這些作為後續重用參考；本次沒有安裝框架或承諾更换 RAG。ChatGPT 的研究建議不是已批准的 RepoNPC 行為變更，也沒有經過本專案相容性測試。

## 6. Owner-approved repair — 8192 / 16384

使用者於 2026-09-13 明確要求由 Luna Max 修改，預設 token 限制 8,192、最大 16k（16,384）。此決策取代第 4 節的候選數值，記錄於 Approved Technical Specification 0.2.7 / ADR-034 / OR-017。

完成狀態：實作與本機自動驗證完成。主要涵蓋 FR-012/027/033/042、AC-039/040/045/046/059 的本次回歸範圍；不代表這些 AC 的所有外部／發行證據已關閉。使用者另授權 Main 在 Luna 品質不足時直接接手；本次 Main 執行整合、獨立驗證及具體修正 review，Luna 依 findings 完成後端收尾。

- 新增部署設定 `REPONPC_ANALYSIS_MAX_OUTPUT_TOKENS=8192`，只接受 1–16,384 的整數；`.env.example` 與 Compose 同步。Windows launcher 原有通用 `REPONPC_*` 載入可讀取它。
- 管理分析使用獨立 provider output ceiling，避免被訪客的 1,000 夾住；仍尊重較小的 provider 能力與完整 context 空間。訪客／probe 預設 1,000、最大 2,000，貢獻建議 700 的政策維持。
- 兩個分析服務路徑預留完整 messages、證據／ID、schema／framing 及 output；保守估算不是 provider 回報的 usage。無安全輸入空間時，在聊天生成前拒絕，不硬補最低 512。
- `length` 在 JSON 解析前拒絕；空、非空及剛好合法的 JSON 都適用。安全原因改為 `PROVIDER_OUTPUT_LIMIT_REACHED`，避免誤稱 schema mismatch；原始內容仍不持久化。Frontend 有繁中／英文復原說明。
- Runtime migration 24 擴充既有 reason 約束；必須交易式保留舊批次、結果、事件、外鍵與索引，包括事件清理後的序號上界及唯一的 sequence 記錄。舊錯誤不會被改寫為猜測的原因。
- 分析結果 cache 綁定實際生成政策：配置預算、有效 provider output/context 容量及生成／驗證版本；preflight 與 execution 相同。改變容量／預算不重用不相容結果，不刪除已確認個人文字。
- Provider 與每專案總期限維持；沒有自動 repair／retry／第二模型／fallback，沒有 RAG 框架或依賴變更。

實作分工：Luna Max 負責必要 Python 後端與測試；Main 負責契約、文件、部署傳值、雙語 UI、review 與整合驗證。共享工作樹原本已有 prompt/schema v2 與 embedding batching 修改；本次保留，不能把它們全部當成本次新增。

### Verification record

前端使用 repository 已安裝且鎖定的工具，從 `apps/web` 執行對應 Node entrypoint：一般 `pnpm --dir ... exec prettier` 未找到命令，未重新安裝或改動 lockfile。

| Check | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m ruff format --check src tests` | Pass, 162 files already formatted |
| `.venv/Scripts/python.exe -m ruff check src tests` | Pass |
| `.venv/Scripts/python.exe -m mypy src` | Pass, 69 source files |
| `.venv/Scripts/python.exe -m pytest -q --ignore=tests/smoke/test_container.py -p no:cacheprovider --basetemp=.pytest-analysis-budget-verified --maxfail=3 --tb=short` | Final tree: 930 passed / 2 skipped / 1 existing Starlette deprecation warning, 62.54 s |
| `git -c core.safecrlf=false diff --check` | Pass |
| `node node_modules/prettier/bin/prettier.cjs --check .` | Pass |
| `node node_modules/eslint/bin/eslint.js .` | Pass, 0 errors / 12 existing Fast Refresh warnings |
| `node node_modules/typescript/bin/tsc --noEmit` | Pass |
| `node node_modules/vitest/vitest.mjs run` | 138 passed in 22 files; two new bilingual output-limit cases |
| `node node_modules/vite/bin/vite.js build` | Pass |
| `docker compose --env-file .env.example -f compose.yml config --quiet` | Pass; host Docker config read-permission warnings, no daemon/image/container smoke |
| Compose resolved environment (example / process override) | Analysis 8192 / 16384 respectively; public 1000 in both cases; only these allowlisted values printed |
| Production adapter wire tests | 6 cases pass: Ollama / OpenAI-compatible / vLLM each sends analysis 8192 default or 16384 configured and public 1000; injected HTTP only |
| Safe reason API/runtime tests | 17 passed, including output-limit snapshot/event propagation and reload persistence; existing Starlette deprecation warning |

第一輪完整非 Docker 後端測試為 915 passed / 2 skipped / 2 failed；兩個失敗來自文件契約測試仍鎖定 0.2.6，已更新為本次批准的 0.2.7。首次測試指令的巢狀 `--basetemp` 缺少父目錄，另曾造成 fixture 初始化失敗；改用 workspace 直接子目錄後解除，不能把該次當成應用程式回歸或完成證據。最終驗證使用 `-p no:cacheprovider` 避免環境既有 pytest cache 寫入警告。

獨立 review 找到並納入修正的邊界：快取漏掉有效 provider 容量、包裝層預算與生成層可能不一致，以及 migration 重建事件表時的序號水位與重複 sequence 問題。Main 以 SQLite 記憶體資料庫驗證「事件全數清理」及「僅尾端清理」後仍須接續 9001，並檢查 foreign keys；沒有接觸真實 runtime 資料。

Luna Max reviewer 最終複核已關閉兩項 cache findings：容量改變會改變 result key 並使舊 preflight plan 過期；共用預算驗證與唯讀 budget property 使 runner/onboarding、service/runner 不一致時於建構階段拒絕。相關兩個 mismatch tests 通過。修正只有內部 policy/guard，未加入新的模型呼叫。

Vitest/build 的首次 sandbox 執行因 Vite 暫存檔寫入 EPERM 而未開始；經 automatic approval review 允許本機測試／建置後成功。兩項 Python skips 是 Windows 上既有的 POSIX mode-bit 與 descriptor no-follow 測試；Docker container smoke 未執行，Compose 配置已檢查。沒有 provider call、服務 restart、真實 runtime migration、commit 或 push。不可由本機結果宣稱 live gateway、完整 browser/accessibility、embedding 共用容量契約或 v1 驗收完成。部署設定與新版程式須重新載入後端才生效。
