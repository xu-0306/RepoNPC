# 剩餘實作接續交接 — 2026-10-03

**最新實作（2026-10-06）：**擁有者已選A：修既有檢索，介面與API不變。一個Luna Max已修正共用中文詞彙召回，零結果才使用共用32個兩字／三字安全片段，重用instr／FTS／RRF；保留精確path、SQL bind與既有filter／packing。82項相關回歸及22項索引smoke／benchmark契約檢查通過，Ruff／format／mypy／compileall通過。active bundle唯讀limit30回放原題0→15、改寫12、缺失path負例0；單次原題91.17ms，不是p95。候選仍集中live-subtitle，沒有重測正式chat或完整Recall@8、沒有provider呼叫／服務重啟／scope改動。A已交付，沒有待決策；B與全三repo覆蓋不屬本輪。[完整結果與限制](REMAINING_WORK_EXECUTION_2026-10-03.md#a實作結果與驗證--2026-10-06)。下方研究／舊待辦是歷史，不是新的完成條件。

**最新研究／計劃（2026-10-06）：**擁有者指定一個Luna Max研究grep／FTS與跨專案優化，已完成；[計劃已併入既有執行文件](REMAINING_WORK_EXECUTION_2026-10-03.md#luna-max-檢索優化計劃--2026-10-06)。優先安全lexical召回與確定scope下的分專案召回；排序後保留repo不能補回global候選池缺漏。比較scope來源列有現有filter／明確公開清單選擇兩案，後者若改API須先同意；pack skip與引用preview等是條件／可選，不阻擋核心修正。本輪只有研究與計劃，未改application／契約／runtime、未做新模型請求、未提升驗收。2026-10-04的服務狀態是歷史，不當作今天重新驗證。

**後續唯讀定位（2026-10-04）：**三專案均已索引，證據數2291／91／6；同一63字中文題被編成一個長詞組，正式FTS唯讀回放0候選。未追加embedding／chat，未重播完整hybrid，不能斷言實際候選分布。完整S4已確認原子寫入／版本衝突及key／路徑規則有支持，先前500字preview疑點解除。建議先改善安全詞彙召回及目標專案分組召回／打包，再改善比較覆蓋與引用預覽；尚未改程式／契約。見[訪客結果追加定位](../../release-evidence/a7/waiting-ux-20261004/OWNER_VISITOR_RESPONSES_RESULT.zh-TW.md)。

**最新正式訪客實測（2026-10-04）：**擁有者對精確作品集資料傳送回答「同意」，
已只送出一題至既有coderelay／gpt-5.6-terra；41秒完成，2段公開摘要／102字元、3個固定版本引用。
摘要在完成答案前已出現；雙語Enter展開／收起與完成耗時凍結核對通過，未保存摘要正文。
答案只具體介紹live-subtitle，另外兩個專案資料不足；部分細節與引用支持度仍須定位，
不提升跨專案品質／資格／release驗收，未測真實取消。此題授權已使用，沒有重試或追加生成。
[正式訪客結果與限制](../../release-evidence/a7/waiting-ux-20261004/OWNER_VISITOR_RESPONSES_RESULT.zh-TW.md)。下方等待傳送授權是此前歷史，已由本段取代。

**最新正式本機啟用（2026-10-04）：**擁有者要求「繼續」後，已完成受限權限全資料備份、
正式schema27→35及原資料保留核對，正常啟動器於localhost:8090啟動。
同一coderelay／gpt-5.6-terra保留端點及key，新Responses revision9通過一次正式probe並啟用；
原revision8留為last_known_good，原embedding及bundle IDs不變。health／ready／chat status通過。
[結果與復原方式](../../release-evidence/a7/waiting-ux-20261004/OWNER_RUNTIME_ACTIVATION_RESULT.zh-TW.md)。
先前訪客送出遭自動核准審查拒絕；擁有者已同意精確payload至既有外部模型，
本題已完成。真實取消尚未測，訪客結果以上方最新實測為準。

## 目前還剩什麼：使用者情境與進度（2026-10-04）

擁有者要求將最近以白話說明的六項問題及目前進度寫入交接與記憶。
本節是最新接續入口；以下各輪實測保留當時範圍，不把舊的待批准狀態當作現況。
最新追加：擁有者批准一次較複雜合成題，現已完成；同一gpt-5.6-terra
HTTP200、117.462秒、兩個情境答案2/2正確，上游完整摘要10事件，正式過濾回呼8段／385字元。
該次合成題沒有改正式設定或啟停服務；其後另依「繼續」完成上方正式啟用。
[完整結果與限制](../../release-evidence/a7/waiting-ux-20261004/LIVE_COMPLEX_SUMMARY_RESULT.zh-TW.md)。

| 問題與使用情境 | 已完成的進度 | 接下來仍要完成 |
| --- | --- | --- |
| **1. 等待時看得到有用的公開摘要。** 訪客問「兩個專案的設計差在哪？」時，希望展開後看到模型提供的比較思路摘要。此例是期望情境，不是已收到的模型文字。 | 真實處理階段、耗時、展開、停止、公開摘要接線與雙語畫面已完成程式整合；隔離畫面驗證通過。簡單API題13.177秒／摘要0；追加較複雜合成題117.462秒、兩個情境答案2/2正確，完整摘要事件10、正式過濾回呼8段／385字元。 | 此服務／模型已觀察到公開摘要；正式probe／activate與一題正式訪客畫面確認已完成，雙語鍵盤與摘要先於答案通過。回呼計數不是正式訪客UI證據，也不能保證每題有摘要或大型repo效能。追加一次授權已使用。 |
| **2. 平常打開的版本真正用得到新功能。** 測試畫面能展開與停止之後，還要讓實際使用的服務採用已驗證的設定。 | 正式全資料備份／27→35保留升級、localhost:8090正常啟動、同模型／端點／key的Responses revision9正式probe／activate均完成。原revision8留為last_known_good，embedding／bundle不變；管理頁「目前使用」、health／ready／chat可用已確認。 | 一題正式訪客比較題已取得資料傳送授權並完成，41秒／2段摘要／3引用，雙語展開與凍結耗時通過。跨專案比較仍不完整、引用支持度須改善；未做真實取消驗證。 |
| **3. 文件有寫，能答對，引用也能支持答案。** 例如資料明明存在本機卻回答「找不到資訊」，或文件只說「支援ZIP備份」卻推論「只能用ZIP備份」。 | 已做訪客問答對照、真實檢索／直接給資料對照、人物歸屬離線診斷，以及跨Ollama／API共用引用候選控制。已觀察到選資料漏項與有資料仍無答案的不同情況。 | 查清選資料、模型輸出與後端拒收各自的原因，補安全的內部原因判別，再修正並驗證。引用修正與本次可引用來源限制仍是隔離候選，未正式整合，正式schema變更仍待決定。不能把問題一律歸咎服務商或RAG效能。 |
| **4. 真正的問題與大型專案也能回答。** 「連得上模型」之後，還要能可靠回答「比較三個大型專案的架構與限制」。 | 有合成作品集的本機問答／檢索證據，以及一次真實API接口測試。先前本機qwen3.5:9b完整固定資格測試為9/12，推薦catalog仍空白。 | 真實API模型的完整問答品質、大型repo、等待／取消體驗與完整模型資格仍未驗證。9/12是此前本機模型的結果，不是gpt-5.6-terra的成績；新的180秒預設／300秒上限也尚不能保證每個大型問題都完成。 |
| **5. Man角色可以合法隨程式交付。** 圖修好了，還要確認可提供給使用者、當預設角色或匯出。 | 擁有者批准的Python精準七像素私有清理已完成；其餘像素與來源保留，私有輸出可重現。 | 作者／授權／自作來源確認，以及正式default／card／export接線仍待完成。不要重新把七像素修整列為未完成，也不要先公開散布素材。 |
| **6. 別人的電腦與外部網站也能正常使用。** 新Windows沒有開發工具也能安裝、升級及保留資料；放大畫面、螢幕閱讀器及外部連線也能操作。 | 開發機隔離安裝、備份還原／重新登入／解除安裝與資料保留有部分證據；雙語響應式、鍵盤及必要對比已有本機驗證。 | 乾淨Windows非管理員安裝／正式升級／SmartScreen／解除安裝、真正200%zoom、螢幕閱讀器、完整外觀／管理／匯出／跨瀏覽器互動，以及外部GitHub／Pages／Funnel驗收仍未完成。需實際設備、目標與相應外部寫入授權。 |

**接續順序建議：**摘要能力與正式probe／啟用已完成，一題正式訪客畫面確認已完成；
接著處理回答／引用原因判別及通用修正，補API／大型專案品質驗證。
角色權利確認與需要實際設備的交付驗收可獨立準備；此排序是建議，沒有新增執行授權。

**已完成範圍與限制：**公開摘要整合的最後一次相關Python回歸539通過／2平台跳過，
Web503通過／44檔，靜態檢查、建置及原生合成UI通過；這不是本輪重跑或完整release驗收。
公開摘要只能使用服務商可公開的摘要，不能公開原始thinking或虛構指令／工具紀錄；
RepoNPC聊天模型仍沒有shell或工具能力。保留原引用、人物、安全檢查及既有明確較低設定，
不自動換模型／服務、不追加第二模型生成摘要、不放寬資格或驗收門檻。

**接續證據：**[摘要實作與本機驗證](../../release-evidence/a7/waiting-ux-20261004/PUBLIC_SUMMARY_RESULT.zh-TW.md)、
[一次真實API檢查與候選](../../release-evidence/a7/waiting-ux-20261004/LIVE_RESPONSES_RESULT.zh-TW.md)、
[回答原因判讀修正](../../release-evidence/a7/rag-paired-20261004/ATTRIBUTION_REVIEW.zh-TW.md)、
[私有角色修整](OFFLINE_ATTRIBUTION_MAN_HANDOFF_2026-10-03.md)、
[乾淨主機交接](../../release-evidence/a12/continuation-20261003/CLEAN_HOST_HANDOFF.md)。
對應既有ADR-057／ADR-058、FR-040／043／044／047、AC-019／023／057／062／063／064／068／071，
角色與交付另見FR-015／018／048／053及AC-069／072／076／079；本次只整理進度，不提升驗收狀態。

**前一次真實 API 檢查（2026-10-04，以下待追加授權已由上方結果取代）：**擁有者指定沿用 gpt-5.6-terra，已完成約定的
一次合成 Responses 請求：HTTP200、有效探測回覆、13.177秒，完整公開摘要事件0。
接口與摘要選項被接受，尚不能確認模型會提供摘要；不是模型永久不支援的證據。
已在私有資料副本核對27→35升級、舊資料保留及Responses候選，候選仍probe／未啟用。
正式schema27、原啟用profile／連線版本8與秘密未改，沒有owner服務啟停或其他生成。
[本次結果與候選](../../release-evidence/a7/waiting-ux-20261004/LIVE_RESPONSES_RESULT.zh-TW.md)
已完成；額外一次較複雜合成題的確認已送出，未取得回答前不追加呼叫。
前輪「沒有真實API呼叫」仍是當時的歷史結論；本輪沒有提升資格或release驗收。

**最新公開摘要整合（2026-10-04）：**擁有者明確回答「批准公開摘要方案（建議）」；
Approved 0.4.10／OR-032／ADR-058 依 [正式摘要契約](../../docs/CHAT_PUBLIC_SUMMARY_CONTRACT_2026-10-04.md)
完成既有連線中的 Responses 選項、版本保存、舊密文相容、隱私檢查、SSE 與雙語展開。
公開摘要與最終驗證答案分開，只在暫存畫面中保留；Ollama／舊接口不自動切換。
最終單次 Python539通過／2平台跳過；Web503／44檔，Ruff／format19檔、mypy9來源，
Web format／lint／type／build／registry／source guard 通過，既有警告保留。
原生隔離畫面核對摘要先於答案、雙語 Enter 展開、純文字、摘要後停止／回焦／凍結、
390px 無水平溢出；分頁、viewport 與自建18773服務已清理。
[完整新結果](../../release-evidence/a7/waiting-ux-20261004/PUBLIC_SUMMARY_RESULT.zh-TW.md)
不含真實 API 呼叫、owner runtime 重啟、Git／發布或release提升；資格9/12／catalog空白／
Man權利及外部驗收不變。本機已批准實作無待決事項，真實服務選擇及相容性測試屬後續。
下方思考文字待批准與0.4.9是此前歷史狀態；原始 thinking 仍不可公開。

**最新等待UX實作（2026-10-04）：**擁有者附圖並明確要求先修改，Luna Max完成
[官方研究與本輪整合結果](../../release-evidence/a7/waiting-ux-20261004/README.md)。
Approved規格0.4.9／ADR-057／OR-031：預設180秒、最大300、既有明確值保留；
原生provider串流僅公開真實階段與耗時，最終答案沿用原驗證。雙語原生可展開紀錄、
完成／失敗／取消耗時凍結、停止及回焦／再次提問已整合。Python316通過／2跳過、
Web493／43檔、owned static／format／build／registry／source guard通過；
原生合成UI操作及390px雙語無水平溢出，沒有真實模型品質聲稱。
**思考文字尚未完成：**自動核准審查拒絕原始thinking公開callback，因提示／秘密／
未驗證內容風險；已移除該接線，只保留有限階段。建議明確選擇可公開provider摘要接口，
不把Ollama raw trace或未知reasoning欄位冒充摘要；此接口／文字契約決定仍待擁有者。
沒有owner runtime重啟、真實模型推論、Git／發布或ledger提升，資格9/12／catalog空白／
Man權利及外部驗收不變。下段的「未改app／預設45」是本輪實作前歷史狀態。

**最新等待UX方向（2026-10-04）：**擁有者質疑45秒對大項目是否太短，要求對話框顯示模型處理過程；[時間與可見進度查核／提案](../../release-evidence/a7/rag-paired-20261004/WAITING_UX_REVIEW.zh-TW.md)已保存。現有chat timeout預設45、最大300，並非固定45上限；現有buffered chat只於等待時發keepalive，不提供真實上游活動或思考文字。方向為更長可調總期限、真實階段／等待時間、依能力提供公開推理摘要與取消；180秒預設及公開摘要契約仍為提案，未改正式設定／privacy／SSE或做新模型測試。不能把先前維持45秒的測量限制當作擁有者新UX要求的否决；同時不能冒稱所有API已提供摘要，或顯示虛構思考。

**最新歸因審查（2026-10-04）：**擁有者追問服務商／項目設計與問題合理性，[補充分析及4例離線控制](../../release-evidence/a7/rag-paired-20261004/ATTRIBUTION_REVIEW.zh-TW.md)已完成，沒有新provider／embedding呼叫。前輪合法ID、空discarded_segments與no-match無法分清模型判資料不足、空segments或envelope完整性拒收；不能將兩次有資料無答案直接歸咎模型。缺SQLite是技術完整性標準，回答本機／無雲端同步可能已满足訪客，不應與超時／錯誤等價。現有錯誤訊息合併與觀測缺口屬項目設計；模型／裝置／提示匹配及上游故障尚未區分，cloud服務商未測。先補內部原因判別、以訪客效用核對修正。4控制及新腳本static通過，原24次數字與正式資格不改；130歷史程式檢查不是模型成功次數。

**最新定位（2026-10-04）：**擁有者批准[真實檢索／直接必要資料的同題對照](../../release-evidence/a7/rag-paired-20261004/README.md)，已完成24次生成（每題每組一次）及一次獨立預載。
同一13筆證據／9來源索引，真實builtin CPU BGE-M3與現有搜尋／打包，未調政策；有資料10題檢索組5完整正確／1部分回答／1誤拒答／3超時，直接組7正確／1誤拒答／2超時；無資料各2題均拒答。
必要文件檢索8/10送到、直接10/10；儲存雙語題在檢索輸出已缺文件，未見打包再丟失。兩組各3次已有必要資料仍失敗，不能全部歸因檢索未找到。
檢索＋embedding＋打包中位54.102ms（範圍48.426–172.982ms）；服務中位檢索29.210s／直接32.511s；19完成生成原生eval佔79.06–99.02%，5超時原生未知。索引建立含首次embedding5.495s另記；小樣本／上下文差異／模型隨機性不支持因果或頻率聲稱。
120儀器與既有相關回歸＋10新報告控制通過，四owned腳本static及三JSON byte-identical replay通過；241受保護檔不變。兩新tab及18768／18769 listener已關閉，Ctrl-C後PTY exit1，不聲稱正常exit0。
新增僅隔離實驗／安全數字／公開合成UI截圖與交接，未正式整合。後續分別查排名選擇漏資料與有資料仍拒答／超時；真實API、大型repo及完整資格未測，schema批准／9/12資格／catalog空白／ledger／Man權利等狀態不變。以下保留舊輪當時證據。

**最新候選（2026-10-04）：**擁有者要求修正，並強調聊天模型也可能使用API；
[共用引用修正候選與實際結果](../../release-evidence/a7/citation-fix-20261004/README.md)已完成。
共用提示沿用現有分段與來源映射，Ollama／OpenAI相容／vLLM adapter路徑控制通過；
不支援結構化限制時保留後端檢查，不能冒稱同等生成保證。165項相關檢查通過，
55項新控制在CLI import修復後再驗證通過，不相加；三腳本static及三份保存數字重算通過。
實際本機12題：有資料10題7完整正確／1多作推論／1誤報無資料／1逾時；另2題無資料正確拒答。
一次獨立空消息預載，沒有重跑失敗題、沒有cloud API推論；API模型實際品質仍未驗證。
完成回應載入約3ms，生成階段佔85.37–98.95%；逾時原生數字未知，不歸因於載入。
241受保護檔案未變，18767 listener與新tab已關閉，PTY exit code未知。
只改隔離候選與紀錄，未正式整合；schema批准、9/12資格／catalog空白／ledger及Man權利狀態不變。
下文保留前輪當時的證據與限制，不把候選測試提升為正式資格。

**最新研究（2026-10-04）：**擁有者要求外部設計比較並明確授權 Luna max 獨立查核；
[官方文件與成熟實作比較](../../release-evidence/a7/citation-design-review-20261003/README.md)
已完成。建議保留「生成時限制本次可引用資料＋原後端驗證」方向；現有候選仍未達正式整合條件。
合法來源不代表支持答案每個細節；小樣本不能證明引用限制導致逾時。先前是本機對照，
外部設計比較於本輪補上。只新增研究／交接記錄，沒有 app／schema／prompt／runtime 改動、
沒有新模型推論，正式整合批准及所有資格／catalog／ledger 狀態不變。

**最新本輪：**擁有者要求先確認實際訪客體驗，已完成
[24組中英文訪客問答對照](../../release-evidence/a7/visitor-ux-comparison-20261003/REPORT.zh-TW.md)。
有資料的10題：原版1題答案與引用皆正確／6題誤報無資料／3題超時；候選4題完整正確／
1題內容正確但引用不精確／5題超時。兩組各2題無資料問題均正確拒答。
25次本機generation含1筆送出問題多出字元的偏離，保留但不計入24組；沒有重跑失敗的預定題。
82項相關回歸與控制檢查、四腳本Ruff／format／mypy通過，241個受保護source／Web／fixture
檔案未變。只在隔離實驗改schema，**未批准或實作正式整合**；建議先處理超時與引用精確度。
模型資格仍9/12／catalog空白，ledger不提升。測試ports與兩個新browser tabs已關閉，
沒有process exit0聲稱。擁有者說明偏好：用訪客問題、畫面結果和等待時間說明價值，
不要用S1／S8等內部代碼要求擁有者判斷。

**前一輪：**[離線診斷與七像素修整](OFFLINE_ATTRIBUTION_MAN_HANDOFF_2026-10-03.md)
已完成。Man由擁有者明確批准Python精準刪除七像素，其餘114,681像素、27幀與
19來源檔保持一致；23個私有輸出可重現，正式接線仍待來源／權利確認。
獨立98案例診斷確認24個普通專案人物歸屬誤判，未證明先前live失敗的實際成因。
模型仍9/12／catalog空白；四種selected-ID enum樣本已完成，正式schema變更待批准。
本輪43＋76既有測試、三腳本Ruff／format／mypy與重現核對通過；application未改。
以下舊證據保留當時範圍，七像素「仍待清理」狀態由本段取代。

擁有者要求繼續完成剩餘任務，沿用三位 GPT-6.1 Sol 與 Root。最新追加決定是預設開啟推理、支援約 16k 生成預算；先前 `think=false` 提案未获批准，沒有採用。現行規格為 Approved0.4.8／ADR-055／OR-029。舊 receipts 保留當時的程式與驗證範圍；尚未提交 Git、發布網站或操作真實 owner runtime。

## 已完成的接續工作

- **A6，FR-006／049、AC-009**：正式 controller 已改用唯一 pinned builtin CPU ONNX baseline，保留題目、oracle、門檻及 host-only scoring。4CPU／8GiB／network-none、唯讀 model／input；Recall@8=1.0、雙語配對一致性=1.0，100 samples 的 warm p95=99.123306ms。獨立審查確認全部25 receipt檔、八個模型檔、隔離與重算一致，僅本次實際量測的 dirty retrieval snapshot 可標 pass；不代表 arbitrary repositories、完整 v1、8192-token peak 或 OS disk-cold。[正式證據](../../release-evidence/a6/formal-builtin-20261003/README.md)、[獨立審查](../../release-evidence/a12/continuation-20261003/ac009-independent-review.json)。
- **A5，FR-015／016／018、NFR-009、AC-019／072 部分**：in-app browser 實際完成150組角色／配色／背景 ×兩語言 ×明暗模式，共600 views；16,800個文字量測、焦點對比、9,600個必要配對與600個NPC-edge／stage量測均通過。原始150個裝飾性 border／stage低於3的額外診斷保留；此配對不是已宣告必要規則，不冒充完整人工可辨識性驗收。實際手機抽屜焦點、Escape回焦、suggestion填入、送出、來源summary鍵盤展開及固定GitHub引用已操作；320／390／768／1440雙語布局無水平溢出。真正200%瀏覽器zoom、screen reader、完整admin／export／cross-browser矩陣仍未完成。[必要配對審查](../../release-evidence/a5/native-continuation-20261003/normative-contrast-review.json)、[原始browser量測](../../release-evidence/a5/native-continuation-20261003/browser-matrix-observations.json)。
- **A9，FR-015／018、AC-068／079 部分**：從完整原始衣裝補回4,419個鞋部延續像素，未補畫或改來源。七states／28frames deterministic私有草稿可重現、19原始檔不變。仍有一個分離七像素黑點；imagegen清理版本改動40,112 pixels／全部28frames，已明確拒絕並保留provenance。Man來源權利未確認，沒有正式公開接線。[修整與接線提案](../../release-evidence/a9/man-repair-20261003/README.md)。
- **A8／A11，FR-048／053、AC-069／076 部分**：完成 exact `d017…` 舊候選的298檔隔離安裝、兩份完整retained bundle的frozen API pin／restore、pointer／SQLite／index一致性、credential保留、CSRF／錯誤密碼／竄改／取消／session與grant撤銷、自動加密先備份。實際installed in-app browser完成中文密文下載、重新選檔／英文錯密碼拒絕／檢查／取消、鍵盤pin／中文還原、旧session拒絕與新一次性授權重新登入；還原前後34個retained檔案一致，撤銷時sessions與grants均0，明確重登入後唯一grant已consumed。八個双語320／390／768／1440頁面無水平溢出。中英文建立備份後密碼欄位均清空；第二次英文下載因原600秒host到期而timeout，不能報通過。两个bounded host均正常exit0，沒有延長；隔離安裝已uninstall0，fixture registry／program／shortcuts清除，external data與34檔保留，實際下載密文與host檔byte-identical、錯密碼拒絕、host記憶體內解密後SQLite integrity／FK通過。這是開發機disposable fixture，沒有clean-host／真正發布版升級聲稱。[installed lifecycle](../../release-evidence/a11/frozen-retained-continuation-20261003/native-browser-host-ui-complete-receipt.json)、[下載與解除安裝核對](../../release-evidence/a12/continuation-20261003/native-completion-verification-final.json)。

## 推理與16k修正

A7擁有 backend provider／factory／profile preparation／output-budget／cache-policy 與相應tests。聊天及分析各自 default／hard maximum=16,384；保留owner明確較低的舊設定。Ollama支援boolean true時明確送 `think:true`，named controls使用精確支援的named default；未知metadata保留模型default並標明未知，永不主動關閉推理。明確傳入bounded `num_ctx`，保留配置32768上限與較低verified model ceiling；輸入message／schema／framing reserve加生成預算必須容得下。

首輪新版真實qwen3.5:9b固定12案例為 **10/12，423.727s**；兩個two-facts案例仍不滿足既有citation oracle，未改題目或放寬。所有案例有推理，無OUTPUT_LIMIT／timeout；實際輸出2136–4761 tokens、19.760–44.082s。固定suite的180s deadline不等於公開聊天45s資格；20s profile probe與全部原deadline保留。catalog仍空白。16k是可用生成預算，包含推理與答案，不承諾生成16k可見文字或完整原生262k context品質。

獨立審查發現並修復：public有效非空但 `finish_reason=length` 必須拒絕；late probe完成不得越過同一20s deadline；malformed thinking default必須驗證；明確較低context不得讓manual app startup崩潰。首輪全Python有2580passed／23failed／2existing skips，23fail是22個舊精確20s transport斷言及一個旧8192 budget fixture；失敗log保留。最終完整非Docker-smoke Python **2613passed／2既有Windows-POSIX skips／495既有warnings，516.43s**。20s實際production profile probe為ready、11.510s，確認使用16384與32768context及推理。[完整log](../../release-evidence/a12/continuation-20261003/python-reasoning-16k-final-full.log)、[source regression](../../release-evidence/a7/reasoning-16k-20261003/final-source-review.json)。

擁有者另批准只把two-facts中英文題目改為明確詢問「檢索融合＋儲存」，保留expected／source IDs／oracle／12題全通過門檻。ADR-056／OR-030記錄此fixture-only修正，Spec仍0.4.8；全新suite與原始fixture副本／SHA獨立保存，舊10/12不改寫。完整新suite結果另見[修正後證據](../../release-evidence/a7/two-facts-correction-20261003/)。

修正後一次完整重驗為 **9/12，388.086s**，兩個two-facts案例均通過。既有規則拒絕三個案例：owner-assertion英文缺少`{{owner}}` reference；中文使用未選來源ID；labeled-inference中文被判為個人稱述而缺少owner assertion。前兩項確認違反既有anchor／source-ID契約；第三項現有safe receipts不足以區分不當個人推論與中文matcher誤判，未證明production bug或同層級規格矛盾。[後續診斷](../../release-evidence/a7/two-facts-correction-20261003/follow-up-diagnosis.md)列出離線正反例審查及一般schema／prompt選項，不更動安全規則。所有案例維持推理，沒有180s timeout或生成上限截斷；三題50.144／48.408／53.337s超過public45s。這是180s adapter quality suite，不能算public deadline資格。Exact revision與官方Apache-2.0來源通過，不抵消品質失敗；catalog byte-identical空白。沒有反覆重跑直到偶然通過、改production prompt、放寬validator或oracle。

新增production推理與budget修正的wheel、Web、frozen EXE及完整Inno installer已重新build。最終source／artifact核對 **112個wheel檔案／102個frozen modules＋6 namespaces／8 resources／15 compiled Web檔案／300 checksums**全部一致；wheel內README與目前source一致，無Torch／Transformers。最新修復後4ac frozen實際health／admin200、未登入maintenance401、fresh模型／profile／session0、合成draft200、Quit0／portclosed，fresh smoke7.68s；分開標示的PYZ合成檢查確認16384／推理與20／45／300政策，沒有實際model call。完整Docker／Compose **2passed，70.58s**，涵蓋health／runtime重啟保留／private-path denial／gateway stop，隔離project teardown完成。[artifact receipt](../../release-evidence/a12/continuation-20261003/final-release/source-artifact-verification.json)、[repaired frozen smoke](../../release-evidence/a12/continuation-20261003/final-frozen-smoke/verification-receipt-repaired.json)、[Docker log](../../release-evidence/a12/continuation-20261003/docker-final-smoke-retry.log)。

最終EXE SHA `4ac546c5b1ed10ba451da5ed4be4d901e43891ae30358bebc97c1ca20ec2491f`；installer SHA `f821ad32698084f43a37a174e80b7e981ed11a284ac62e257bfc3a8d15635032`；wheel SHA `046f0743aa054559ddcc7d993e151ee6aac1670a4b890386d65b143f54d31671`。舊native維護證據只綁`d017…`，不移植為最新binary或完整AC-076。首次offline wheel build找不到Hatchling；第二次offline及network sandbox失敗log保留，首次log於已批准dependency fetch成功retry時被覆寫，歷史tool結果仍在，不宣稱全部原始log保存。Docker初次sandbox因config／named pipe權限拒絕而2failed；保留log，精確隔離scope的已批准retry才通過。[新版leaf](../../release-evidence/a7/reasoning-16k-20261003/)。

Root最初的artifact verifier覆用`target`變數，把JSON收據寫進frozen OFL license檔；b28成功smoke的snapshot因此含14,094 bytes錯檔，不能作final distribution proof。已保存misdirected收據與舊snapshot、改為獨立receipt／resource路徑及create-only輸出，完整重新build恢復4301 bytes原始license；fresh4ac source核對、8資源／300checksums與smoke均通過。Closeout另在收據寫入後重驗全部300checksums，確保核對程序沒有改候選。沒有app source、owner runtime或公開操作。[修復與舊證據失效範圍](../../release-evidence/a12/continuation-20261003/final-release/artifact-repair-review.json)。

## 真正尚待完成的閘門

- 回答模型仍需完整固定suite安全與品質全通過才可推薦；本輪9/12，catalog空白。後續須以一般模型能力／提示詞設計提案處理三種失敗，保留人物稱述與來源控制；不為單題添加特例或削弱驗證。
- Man七像素私有清理已完成；作者／授權／自作來源確認之後才做正式default／card／export接線。
- clean Windows非管理員無開發工具的安裝／正式版本升級／資料保留／SmartScreen／解除安裝；[已準備交接材料](../../release-evidence/a12/continuation-20261003/CLEAN_HOST_HANDOFF.md)。
- 真正200%zoom、screen reader、完整appearance/admin/export互動矩陣及外部GitHub／Pages／Funnel驗收；需實際設備、目標及對應外部寫入授權。

新79-row候選帳本僅提升AC-009：1pass／75not-run／3blocked。not-run不是75個功能未實作；它表示完整該AC證據尚未綁定本次候選。舊兩份帳本不改寫。[新版帳本](../../release-evidence/a12/continuation-20261003/acceptance-ledger-candidate.json)。

Root的兩個A5合成server以Ctrl-C停止，Windows asyncio已連線pipe在關閉時回報10054／exit1；這不是production launcher的Quit結果。原始tool輸出保留，另核對所屬port關閉；五個Root驗收tabs關閉／viewport reset，使用者原有兩tabs保留。已安裝host與新版frozen smoke的正常Quit0收據各自不改写。一次同tab fragment登入在guard前被AX capture，曾於歷史tool output暴露短期授權；已立即reload消耗及清除，沒有unused有效grant，未將值寫入repo或receipts；歷史tool output無法抹除，今後以fresh tab並在任何capture前檢查fragment清空。
