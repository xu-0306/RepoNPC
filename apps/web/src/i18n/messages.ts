export const messages = {
  "zh-TW": {
    title: "認識懂你程式碼的 NPC",
    statusTitle: "目前正在設定 RepoNPC",
    statusDetail: "作品集索引尚未啟用，因此聊天功能暫時無法使用。",
    availabilityDetail: "完成設定後，這裡會提供可驗證的專案導覽與引用。",
    languageLabel: "選擇語言",
    languageName: "繁體中文",
  },
  en: {
    title: "Meet the NPC who knows your code",
    statusTitle: "RepoNPC is being set up",
    statusDetail:
      "The portfolio index is not active yet, so chat is unavailable for now.",
    availabilityDetail:
      "Once setup is complete, this page will offer verifiable project guidance and citations.",
    languageLabel: "Choose language",
    languageName: "English",
  },
} as const;

export type Locale = keyof typeof messages;

const expectedKeys = Object.keys(messages["zh-TW"]).sort();

if (
  JSON.stringify(expectedKeys) !==
  JSON.stringify(Object.keys(messages.en).sort())
) {
  throw new Error("RepoNPC locale message keys are not equivalent");
}
