export interface AdminErrorState {
  globalMessage: string;
  guidedCode: string;
}

export type AdminErrorAction =
  | { type: "SET_GLOBAL_ERROR"; message: string }
  | { type: "CLEAR_GLOBAL_ERROR" }
  | { type: "SET_GUIDED_ERROR"; code: string }
  | { type: "CLEAR_GUIDED_ERROR" }
  | { type: "CLEAR_ALL_ERRORS" };

export const initialAdminErrorState: AdminErrorState = {
  globalMessage: "",
  guidedCode: "",
};

export function adminErrorStateReducer(
  state: AdminErrorState,
  action: AdminErrorAction,
): AdminErrorState {
  switch (action.type) {
    case "SET_GLOBAL_ERROR":
      return { ...state, globalMessage: action.message };
    case "CLEAR_GLOBAL_ERROR":
      return { ...state, globalMessage: "" };
    case "SET_GUIDED_ERROR":
      return { ...state, guidedCode: action.code };
    case "CLEAR_GUIDED_ERROR":
      return { ...state, guidedCode: "" };
    case "CLEAR_ALL_ERRORS":
      return initialAdminErrorState;
  }
}
