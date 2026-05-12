// JMTY GUI Web版で表示する状態スナップショットです。
// Macワーカーがローカルworkspaceを読み取って返した内容を保存し、
// Vercel側の画面はこのJSONを正本ではなく表示用キャッシュとして扱います。
import { readJson, writeJson } from "@/lib/store";

export type JmtySlotKind = "factory" | "remote1" | "remote2";
export type PostSyncStatus = "synced" | "dirty" | "sheet_only" | "local_only" | "missing" | "unknown";

export type JmtySampleFile = {
  name: string;
  path?: string;
  text?: string;
  updatedAt?: string;
  updated_at?: string;
};

export type JmtySampleGroup = {
  label: string;
  category: string;
  files: JmtySampleFile[];
};

export type JmtyRules = {
  common?: string;
  factory?: string;
  remote?: string;
  [key: string]: unknown;
};

export type JmtySlotState = {
  kind: JmtySlotKind;
  label: string;
  accountName?: string;
  rowNumber?: number | string;
  region?: string;
  salary?: string;
  postText: string;
  localPostText?: string;
  sheetPostText?: string;
  postPreview: string;
  postSyncStatus?: PostSyncStatus;
  promptText?: string;
  promptPreview: string;
  hasPost: boolean;
  hasPrompt: boolean;
  hasImage: boolean;
  imageFile?: string;
  imageThumbnailBase64?: string;
  approved?: boolean;
  validationStatus?: string;
  validationMessage?: string;
  updatedAt?: string;
};

export type JmtyAccountState = {
  accountName: string;
  slots: JmtySlotState[];
};

export type JmtySnapshot = {
  syncedAt: string;
  sourceRoot: string;
  workerStatus?: {
    workerId?: string;
    lastSeenAt?: string;
    status?: string;
  };
  gwsStatus?: {
    label?: string;
    ok?: boolean;
    detail?: string;
  };
  syncSummary?: {
    dirtyCount?: number;
    dirty_count?: number;
    items?: Array<Record<string, unknown>>;
  };
  accountCount: number;
  accounts: JmtyAccountState[];
  postRules?: JmtyRules;
  imageRules?: JmtyRules;
  projectSamples?: { groups: JmtySampleGroup[] };
  postStyleSamples?: { groups: JmtySampleGroup[] };
  imagePromptTemplates?: { groups?: JmtySampleGroup[]; files?: JmtySampleFile[] };
  logsSummary?: Array<Record<string, unknown>>;
};

const STATE_KEY = "jmty:web_gui_state:v1";

export async function getJmtySnapshot() {
  return readJson<JmtySnapshot | null>(STATE_KEY, null);
}

export async function saveJmtySnapshot(snapshot: JmtySnapshot) {
  await writeJson(STATE_KEY, snapshot);
}
