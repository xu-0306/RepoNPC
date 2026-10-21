# 剩餘工作接續 — 2026-10-03

## Luna Max 檢索優化計劃 — 2026-10-06

狀態：研究已完成；2026-10-06擁有者要求Luna Max實作，並明確選擇A：
先修既有檢索，保持介面與API不變。核心A已實作並完成相關離線驗證；B不納入本輪。目標是改善自然中文的詞彙召回，
沿用SQLite FTS5、既有向量／RRF、來源權重與證據ID，不新增服務或模型規劃pass。
本輪不把其他角色／Windows／發布待辦納入，也不提高既有驗收門檻。

本輪A僅實作安全中文詞彙召回及必要回歸。以下分專案候選保留／召回、
打包調整與新介面均保留為研究建議，不是本輪完成條件。

### A實作結果與驗證 — 2026-10-06

一個Luna Max沿用共用compile_fts_query／ReadOnlyIndex.lexical_candidates修正：
primary term／trigram仍使用原本安全literal查詢，有結果便沿用；零結果的純非ASCII
自然語言才使用單一bounded片段召回。三字片段走既有trigram FTS，兩字片段走既有
bound instr；兩者共用32片段上限、按值去重及RRF。片段不跨標點／空白，ASCII
字母／數字停用此補查，因此英文、path／symbol及英中混合精確約束保持原行為。
兩字需兩個不重疊的不同片段命中，三字需兩個不同片段命中；不以通用單片段放大結果。
兩字搜尋仍會掃描索引列，已在程式註明效能上限；本輪未新增tokenizer／依賴／索引表。

原題舊32個三字片段只有1個命中，其餘31個為0，且短主題詞「儲存」被取樣上限遺漏，
所以三字／2-hit草稿仍0。修正後共用兩字／三字表示並均勻抽取短詞，沒有疊第二個補查流程。
既有active bundle唯讀回放（channel limit30）：原63字題0→15候選／91.17ms；
24字改寫問法12候選／81.40ms；混合不匹配path負例0／0.37ms。此為單次本機量測，
不是p95。原題前8筆為live-subtitle的UI_SYNC_REDESIGN_PLAN、UI_SYNC_CONTRACTS與
TRANSLATION_SERVICES文件；完整S4支持已於前輪核對。候選仍集中live-subtitle，
本輪不宣稱完整三repo覆蓋、hybrid選取／packed context改善或模型回答品質已確認。

變更檔案為src/reponpc/retrieval/fts_query.py、src/reponpc/bundles/index_reader.py及
既有unit/integration FTS、retrieval policy測試共3檔；交接與此記憶同步更新。
正常、未見中文問法、短詞、重複片段、不匹配path、injection、邊界及既有policy回歸：
82通過（4.25s）。另跑既有built-index FTS smoke與host-only Phase2 benchmark契約／評分測試，
22通過（1.50s）。Ruff lint／format（5檔）、mypy（2個source）、compileall及diff whitespace
核對通過；git只有既有CRLF提示。正式artifact／Docker Recall@8 benchmark未跑，
上述22項是契約／評分回歸，不是正式模型品質成績；保留AC-009原門檻。

本輪不新增provider／embedding／chat呼叫、不重啟服務、不修改API／介面／schema／
設定／repo scope／filter／packing。已完成A所需工作，沒有待擁有者決策；完整比較對象
選擇B與其他舊待辦仍屬後續可選工作。對應FR-005／007／022，維持FR-006與
AC-007／008／013／023及ADR-003／004／007／023；未提升完整資格或release驗收。

### 依據與尚未證實的部分

2026-10-04同一正式比較題41秒完成，2段公開摘要／102字元、3個引用，但只有
live-subtitle獲得具體介紹。當時active index內三repo證據數2291／91／6；
framefit有應用程式碼但無README，anti-hardcode有README。資料存在不代表
用途／架構／儲存每一項均有充分證據，不能強迫模型補完沒有來源的內容。

該63字無空格中文題被compile_fts_query編成單一quoted phrase，唯讀lexical
回放為0。這已定位詞彙召回缺口；當時query embedding／完整hybrid／真正packed
內容未重播，不能認定實際缺漏全部出在排序、模型或打包。2026-10-06沒有重測
正式runtime，也不把2026-10-04的運行狀態當作今天的新驗證。

S4完整832字支持原子寫入／版本衝突及key／路徑規則；引用preview只顯示500字，
不代表完整來源不支持。S1是live-subtitle視覺參考資料，不能證明其他repo無資料。
依據：[正式訪客結果與唯讀定位](../../release-evidence/a7/waiting-ux-20261004/OWNER_VISITOR_RESPONSES_RESULT.zh-TW.md)。

### 執行順序與最小方案

1. **在既有fixture定位召回、選取、打包的缺漏，再修lexical。**
   沿用現有SQLite測試，以固定向量而非provider生成向量，核對原始channel候選、
   去重／權重後pool、final selected及packed的repo集合／證據ID，只保存安全數字。
   在fts_query.py與ReadOnlyIndex.lexical_candidates共用入口修正，保留原正規化、
   exact技術詞／path／symbol、短查詢、現有字數／term／candidate界限與SQL bind。
   首選候選：primary查詢為0時，對無空格自然語言區段做不跨空白／標點的有限
   trigram短片段搜尋，結果沿用現有fuse_rankings合併；只由後端生成quoted literals，
   不接收使用者FTS運算子。先離線比較召回與不相關命中，再選必要的片段／命中界限，
   不把提議的16 shingles或2-hit變成未驗證的硬門檻／新設定。
   混合英中查詢須保留path／symbol約束；有結果的既有精確搜尋不直接擴大成任意OR。
   若候選在同義問法／英中混合負例上失效，修正原query策略，勿加入這三repo名稱或
   使用者原句特例。此算法仍是離線候選，未聲稱已改善正式題的召回。

2. **只對確定的比較範圍，補足候選覆蓋並合併。**
   若相關target repo已在pool卻被final選取排除，先在既有權重／去重／cap內對
   確定scope中的相關repo保留代表證據，再依分數填剩餘位置。
   若target repo根本不在pool，排序後公平挑選無效：必須在各channel的LIMIT／
   vector top排序前篩repo，再各自召回並合併；重用同一query vector，不追加embedding。
   新的預先篩選應修在現有hybrid_candidates／retrieval filter邊界，不能只在截取後
   補一個guard。單repo範圍保持聚焦；scope不明的一般問題保持全域召回，不硬塞所有repo。
   可沿用既有source類型與入口證據挑選；不為缺README的repo新增模型摘要來假造來源。
   比較範圍來源需先定案，見下方決策；不能宣稱目前已有可信多repo scope。

3. **做相關離線回歸後交付核心修正。**
   在既有FTS／retrieval policy測試補正例、負例與未見過的repo名／資料規模，
   驗證預期證據ID真的進入context，保留安全marker、token budget、filter、source weight、
   overlap／cap與引用位置。再跑受影響檔案的Ruff／format／mypy與相關測試；
   檢索變更跑既有相關eval，保留正式AC-009原門檻，離線固定向量不冒充production
   embedding／Docker／p95驗收。真實生成改善仍須另行授權，不沿用已使用的一題額度。

### grep／rg的角色

rg先用於本機呼叫者追蹤與研究驗證。正式runtime優先使用已有immutable index；
只有確有保留且已驗證的原始repo快照、FTS仍缺所需內容時，才評估後端rg補查。
rg不能直接讀工作目錄最新檔冒充既有bundle commit，也不能繞過source／證據ID、
引用行號、budget及untrusted邊界。模型仍無工具、shell、檔案或任意網路能力。
本計劃的核心修正不依賴安裝rg、重下載repo、重建index或更換服務。

### 必要驗證案例與相關檔案

- fts_query.py／index_reader.py及tests/unit/test_fts_query.py、
  tests/integration/test_fts_query.py：無空格繁中、英文、換句話說、短詞、path／symbol、
  混合語言且path不匹配、僅命中通用片段的負例、空值、超長與惡意FTS輸入。
- tests/integration/test_retrieval_policy.py：三repo分數／規模不均但都在pool、
  兩repo被global截取排除、明確單repo、scope不明、overlap／權重／cap及budget。
  期望是找回本題範圍內且確有來源的內容，無資料／不適用仍應如實說明。
- chat/service.py為共用呼叫者與query vector／context邊界；eval與
  tests/integration/test_chat_grounding_security.py核對既有證據隔離及引用控制。
  本輪只確認檔案／呼叫者／既有測試，沒有執行上述實作後檢查或提升AC狀態。

### 實作前決策與可選項

FTS候選的召回／精度取捨需經小型離線比較確認。§6規範allowlisted語法與bind，
沒有要求AND-only；目前AND-only主要是compiler與測試行為。正式修正需對齊
已同意的自然語言搜尋行為，過時的literal-query測試可更新，安全負例不得削弱。

**比較範圍來源是必要的產品決策：**
A. 沿用目前問題／已明確識別的repo filter；無可信scope時維持全域搜尋，沒有額外API欄位，
但不能保證泛稱「各個專案」會完整涵蓋三repo。
B. 建議讓訪客由已有公開專案清單明確指定比較對象（含全部作品集），後端重驗當前
bundle中的slug，以這個scope召回。若需要新增request欄位／UI選擇，必須先取得
擁有者同意並同步API／規格／雙語無障礙測試；不新增模型scope分類器。
擁有者已選A，本輪不採B或修改端點。完整比較scope仍是後續可選決策，不阻擋A交付。

遇首筆超預算即break目前是明確測試行為；skip-and-continue與跨repo預算分配
僅在定位證明packing丟失必要證據時再提案。它涉及§7第7項rank-order packing取捨，
不能為通過測試直接換行為。引用preview截斷提示／更精確支持行、比較表呈現與
overview補強列為可選，不阻擋這次檢索核心修正；未同意的schema變更不納入。

對應FR-005/006/007、FR-009/010/011、FR-022；AC-007/008/009、AC-010–013、AC-023；
沿用ADR-003/004/007/023與Technical Specification §6及§7第2–8項。
舊資格、完整API／大型repo品質、角色權利與release gate仍是其他工作，沒有提高或豁免門檻。

研究查證：[SQLite FTS5語法](https://www.sqlite.org/fts5.html#full_text_query_syntax)、
[分組召回原理](https://qdrant.tech/course/beginners/module-6/grouping/)；後者只作方法參考，
不引入Qdrant。Luna回報完整讀取規定核心文件與README、相關源碼／呼叫者／檢索測試，
並核對最近證據及四個相關技能；未修改檔案、正式runtime／provider、依賴或執行全套測試。
以上為研究階段紀錄；擁有者其後選A，實作與驗證結果以上方A實作結果為準。

---

**後續唯讀定位（2026-10-04）：**三專案均已索引，證據數2291／91／6；同一63字中文題被編成一個長詞組，正式FTS唯讀回放0候選。未追加embedding／chat，未重播完整hybrid，不能斷言實際候選分布。完整S4已確認原子寫入／版本衝突及key／路徑規則有支持，先前500字preview疑點解除。建議先改善安全詞彙召回及目標專案分組召回／打包，再改善比較覆蓋與引用預覽；尚未改程式／契約。見[訪客結果追加定位](../../release-evidence/a7/waiting-ux-20261004/OWNER_VISITOR_RESPONSES_RESULT.zh-TW.md)。

**最新正式訪客實測（2026-10-04）：**擁有者對精確作品集資料傳送回答「同意」，
已只送出一題至既有coderelay／gpt-5.6-terra；41秒完成，2段公開摘要／102字元、3個固定版本引用。
摘要在完成答案前已出現；雙語Enter展開／收起與完成耗時凍結核對通過，未保存摘要正文。
答案只具體介紹live-subtitle，另外兩個專案資料不足；部分細節與引用支持度仍須定位，
不提升跨專案品質／資格／release驗收，未測真實取消。此題授權已使用，沒有重試或追加生成。
[正式訪客結果與限制](../../release-evidence/a7/waiting-ux-20261004/OWNER_VISITOR_RESPONSES_RESULT.zh-TW.md)。下方等待傳送授權是此前歷史，已由本段取代。

**最新實際服務（2026-10-04）：**正式備份／schema35／原資料保留、localhost:8090啟動、
同服務gpt-5.6-terra Responses revision9正式probe／啟用及ready/chat可用已完成。
原revision8為last_known_good，Embedding／bundle不變；沒有application source改動。
正式訪客比較題已取得精確資料傳送授權並完成，詳見上方最新實測。
見[正式啟用結果與待答覆事項](../../release-evidence/a7/waiting-ux-20261004/OWNER_RUNTIME_ACTIVATION_RESULT.zh-TW.md)。

**最新白話問題與進度（2026-10-04）：**擁有者要求將六項使用情境寫入交接及記憶；
接續請先讀[目前還剩什麼：使用者情境與進度](CONTINUATION_HANDOFF_2026-10-03.md#目前還剩什麼使用者情境與進度2026-10-04)。

1. 等待時的公開摘要：程式及合成畫面接線完成；簡單題13.177秒／摘要0，擁有者批准的追加較複雜題已HTTP200／117.462秒、答案2/2正確，上游完整摘要10事件，正式過濾回呼8段／385字元。摘要能力與正式設定已確認；一題實際訪客摘要／答案已完成，41秒／2段摘要／3引用。跨專案比較品質仍不完整。
2. 實際服務啟用：正式備份／schema35保留升級／probe／Responses revision9啟用及管理頁、health／ready／chat可用已完成；正式訪客摘要／答案及雙語展開已確認；真實停止未測。
3. 回答／引用可靠度：已做對照及通用候選；找漏資料、有資料卻無答案及引用支持度仍須原因判別／修正，正式引用schema整合尚未批准。
4. 大型專案／API品質：兩次不同合成API題成功不等於完整問答品質通過；此前本機qwen3.5:9b仍9/12，推薦catalog空白，API完整問答與大型repo未驗證。
5. Man角色：私有七像素修整已完成；來源／授權及正式預設角色、卡片與匯出接線待完成。
6. 完整交付：開發機安裝／還原／資料保留與部分雙語／鍵盤／對比已測；乾淨Windows、正式升級、200%zoom、螢幕閱讀器、完整互動及外部發布驗收仍待完成。

建議接著處理跨專案覆蓋、回答原因／引用通用修正及API／大型repo品質；
前次單次合成追加呼叫已完成；本輪另依「繼續」完成正式資料升級、probe、啟用及服務啟動，未改application source。
後續額外生成不能延用已使用的一次合成呼叫額度；實際訪客題已同意並完成，授權已使用。
見[最新較複雜摘要結果](../../release-evidence/a7/waiting-ux-20261004/LIVE_COMPLEX_SUMMARY_RESULT.zh-TW.md)。
Approved0.4.10／OR-032／ADR-058公開摘要實作已完成；下方「真實API未呼叫」與舊規格版本
保留原輪範圍，現況以本段、主交接及[真實API結果](../../release-evidence/a7/waiting-ux-20261004/LIVE_RESPONSES_RESULT.zh-TW.md)為準。

**最新判讀修正（2026-10-04）：**[服務商／設計歸因審查](../../release-evidence/a7/rag-paired-20261004/ATTRIBUTION_REVIEW.zh-TW.md)完成4例離線控制（provider／embedding0），新腳本static通過。no-match與空discarded_segments不能排除envelope拒收，需先补安全的內部原因判別；缺SQLite不必然是訪客問題。前輪技術完整性5/10與7/10、正式門檻／catalog／帳本均保留，沒有新模型推論或正式修正。

**最新定位（2026-10-04）：**[實際搜尋與直接提供資料對照](../../release-evidence/a7/rag-paired-20261004/README.md)完成24次生成，未重跑失敗題。10題有資料：檢索5完整正確／1部分／1誤拒答／3超時；直接7正確／1誤拒答／2超時；無資料各2題均拒答。
檢索必要文件覆蓋8/10，儲存雙語題已在搜尋輸出漏掉；兩組各3題有文件仍失敗。搜尋相關耗時中位54.102ms、生成等待數十秒，後續需分開查選資料品質與回答穩定性；未證明embedding唯一成因或改善幅度。
120相關檢查＋10新報告控制、四脚本static、三JSON replay及241受保護檔一致通過。測試tabs與18768／18769已關閉，停止PTY exit1。正式整合／完整資格／真實API與大型repo仍未完成，schema批准／9/12／catalog空白／帳本／Man權利不變。

**最新候選（2026-10-04）：**[通用引用修正及驗證](../../release-evidence/a7/citation-fix-20261004/README.md)
已完成隔離實作：共用提示／來源映射通過Ollama、OpenAI相容與vLLM實際adapter的合成控制，
API不送Ollama專用預載／think欄位；尚未呼叫真實API模型。
165相關檢查＋最後55新控制重驗均通過（重疊不相加），三腳本Ruff／format／mypy及三檔replay通過。
本機固定12題只各生成一次：有資料10題7完整正確／1不支持的推論／1誤報無資料／1逾時，
2題無資料正確拒答。完成回應主要等待生成階段，不能將一次預載當通用速度修復。
未正式整合，schema批准仍待決定，資格9/12／catalog空白／ledger不提升；三種失敗仍要處理。
以下研究及舊對照保留原時點；它們不是本次新測試或正式模型資格。

**最新研究（2026-10-04）：**完成擁有者要求的
[外部設計比較及 Luna max 獨立查核](../../release-evidence/a7/citation-design-review-20261003/README.md)。
候選的事前來源限制方向較合理，但不保證語意引用或速度，現有候選暫不正式整合。
原後端來源／人物／URL 控制全部保留；不增加第二模型 pass，亦未修改程式或進行新推論。
後續需分開定位逾時與引用支持度，正式 schema 變更仍未取得批准。

**最新新增交付：**[實際訪客問答對照](../../release-evidence/a7/visitor-ux-comparison-20261003/REPORT.zh-TW.md)
完成24組預定問答；25次本機generation含1筆不同輸入的偏離，已保留排除。
有資料10題，完整正確原版1／候選4；候選另1題引用缺口、5題超時，原版6題誤報無資料／3題超時。
兩組無資料各2題均正確拒答。只證明合成作品集上的UX影響及混合結果，未估計真實發生率；
建議暫不正式整合。82檢查／四腳本static checks／241檔unchanged及saved-data replay通過。
正式schema仍未變、資格9/12／catalog空白／ledger不提升；Man私有修整及權利狀態未變。

**本輪新增交付：**[離線人物歸屬診斷與Man精準七像素修整](OFFLINE_ATTRIBUTION_MAN_HANDOFF_2026-10-03.md)
已完成；98獨立合成案例有24誤判，43項回答回歸／76項素材回歸通過。
私有Man候選只變七像素，23輸出重現一致，rights／正式接線仍待確認。
selected-ID enum已有四種可審查樣本，production schema變更待擁有者批准；
沒有重跑live模型或更動catalog／oracle／門檻／deadline／app／公開資產。

**最新執行狀態：**正式builtin AC-009已通過；600組in-app對比、八個雙語已載入響應式view、installed retained restore／relogin與uninstall／資料保留已取得部分證據。擁有者追加「推理預設開啟、至少約16k」，由A7完成16384預算／bounded context／原deadline與安全回歸，A6独立審查並同步Approved0.4.8／ADR-055／OR-029；完整Python2613pass／2既有skip。另批准僅修正two-facts問句、保留判分，ADR-056／OR-030；修正題雙語通過，但完整suite9/12，catalog仍空白。A9後續承接最終frozen smoke；Root更新wheel／source identity與交接。最終成果與仍未完成的模型資格、Man圖像／權利、clean-host及完整人工／外部閘門见[當前交接](CONTINUATION_HANDOFF_2026-10-03.md)。下文是起始分派，不作最終狀態。

擁有者在上一輪交付後要求繼續完成剩餘任務。沿用三位 GPT-6.1 Sol；Root 完成共用文件、整合、in-app browser 與發布候選證據。Approved0.4.7／ADR-048／052／054 的現有契約適用，不改驗收門檻、fallback、公開權限或素材規格。這是上一輪後的新增工作紀錄；舊 receipts 不重寫。

- **Sol A6：正式 AC-009**。擁有 `evals/phase2/run_benchmark.py`、`candidate_runner.py`、`Dockerfile`、`README.md`、`tests/fixtures/phase2/reponpc.yml`、`tests/integration/test_phase2_benchmark.py` 與既有 formal-controller tests。用現有 pinned builtin provider／verified artifact，替換陳舊 E5／Torch 預設；保留 questions／expected oracle／thresholds／4CPU／8GiB／network-none／host-only scoring／access probe。真實權重沿用既有 disposable 八檔，不下載新模型。新 evidence 放 `release-evidence/a6/formal-builtin-20261003/`。不得修改 production provider、公共 API、其他 runtime 契約或帳本。
- **Sol A7：回答模型 catalog**。擁有 `src/reponpc/admin/model_catalog.yml`、必要 `tests/unit/test_model_guidance.py`，以及 `release-evidence/a7/catalog-continuation-20261003/`。先診斷原 strict-case 失敗；不改既有 oracle／門檻、不為單題加 prompt 特例、不冒充模型 revision／授權。先提交通用修正建議再移交其他 source 檔案。只測既有已安裝本機 Ollama、合成資料；無 cloud、model pull、owner settings／runtime／raw prompt-response retention。僅真正全案例通過且 provenance 完整者入 catalog；失敗保留。
- **Sol A9：Man 私有修整與正式接線準備**。`PixelNPC/` 唯讀；擁有 `tools/prepare_character_assets.py`、相應 unit tests，以及 `release-evidence/a9/man-repair-20261003/`。使用既有 deterministic converter／validated alignment 修整可確認位移；不能把缺失像素、模糊片段、無授權來源當成完成。必要圖像編輯使用 imagegen skill／工具，保存原版及生成 provenance，不覆寫來源。正式 default／pack／bundle／card 的最小接線 proposal 先交 Root，Root 擁有 public assets／composer／registry／共用 CSS。未提供來源授權前不公開散布 Man。
- **Root：A5／A8／A11／A12 本機部分**。in-app browser 補實際鍵盤／對比／響應式與可證明的 zoom；正式 retained-bundle frozen restore／installed browser；保持 latest wheel／installer source identity。可準備乾淨 Windows／外部 URL 的完整可執行驗收材料；不存在的主機／螢幕閱讀器／公開 URL 不能冒充完成。外部 GitHub／Pages／Funnel 寫入及真實 owner runtime 仍需明確目標與授權，先完成可審查候選。

共用 checkout，保留全部既有 dirty edits；不 stage／commit／push、不清除曾被拒絕的暫存路徑。各 worker 只修改自己的檔案、使用 fresh basetemp，Root 控制 shared dist／browser ports18763–18766。正式計時期間不並行其他重推論；A6 完成計時後通知 A7。uv／pnpm；新概念預算零（沿用既有 controller／provider／catalog／converter／fixtures），移除陳舊 benchmark E5 assumptions，不新增推薦 service、狀態機、DB 或 fallback。只提升有完整 exact-source 證據的個別驗收項目，不用本機 subset 宣稱全部 v1 完成。
