// Vercel版JMTY GUIのクライアントUIです。
// タブ切替、編集フォーム、主要操作ボタンを担当し、
// 実処理は/api/jobs経由でMac workerへ依頼します。
"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { Job, JobType } from "@/lib/jobs";
import type { JmtyAccountState, JmtyHistoryEntry, JmtySampleGroup, JmtySlotState, JmtySnapshot } from "@/lib/jmty-state";

type Props = {
  snapshot: JmtySnapshot | null;
  jobs: Job[];
  user: { accountName: string; isAdmin: boolean };
};

type TabKey = "dashboard" | "posts" | "rotation" | "images" | "prompts" | "logs" | "samples";

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "dashboard", label: "ダッシュボード" },
  { key: "posts", label: "投稿文管理" },
  { key: "rotation", label: "地域・ローテーション" },
  { key: "images", label: "画像生成" },
  { key: "prompts", label: "画像プロンプト管理" },
  { key: "logs", label: "実行ログ" },
  { key: "samples", label: "見本管理" },
];

const slotLabels: Record<string, string> = {
  factory: "工場",
  remote1: "在宅1",
  remote2: "在宅2",
};

const statusLabels: Record<string, string> = {
  queued: "処理待ち",
  running: "実行中",
  done: "完了",
  failed: "失敗",
  cancelled: "取消",
};

const jobLabels: Partial<Record<JobType, string>> = {
  sync_state: "最新状態取得",
  generate_image: "画像生成",
  validate_image: "画像検証",
  sync_drive: "Driveへ反映",
  sync_sheet: "スプレッドシートに反映",
  rotate_sheet: "ローテーションをスプレッドシートに反映",
  prepare_posts: "投稿文AI再作成",
  save_post: "投稿文をアプリに保存",
  sync_post_to_sheet: "投稿文をスプレッドシートに反映",
  sync_all_dirty_posts_to_sheet: "未反映をスプレッドシートに反映",
  restore_post_history: "投稿文履歴から復元",
  restore_image_history: "画像履歴から復元",
  rewrite_post_with_style: "投稿文AI再作成",
  rewrite_all_posts_with_style: "投稿文一括AI再作成",
  rewrite_failed_validation_posts: "検証NG投稿文AI再作成",
  save_image_prompt: "画像プロンプト保存",
  cancel_image: "画像登録取消",
  approve_image: "画像OK",
  save_project_sample: "案件素材保存",
  save_post_style_sample: "スタイル見本保存",
  delete_post_style_sample: "スタイル見本削除",
  save_post_rules: "投稿文ルール保存",
  save_image_rules: "画像ルール保存",
  reload_sheet: "シート読込",
  save_sheet_mapping: "基本情報設定保存",
};

function formatDate(value?: string) {
  if (!value) return "未同期";
  const time = new Date(value).getTime();
  if (Number.isNaN(time)) return value;
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(time));
}

function preview(text?: string, limit = 120) {
  const collapsed = String(text || "").replace(/\s+/g, " ").trim();
  if (!collapsed) return "未作成";
  return collapsed.length > limit ? `${collapsed.slice(0, limit)}...` : collapsed;
}

function slotPayload(account: JmtyAccountState, slot: JmtySlotState, extra: Record<string, unknown> = {}) {
  return {
    accountName: account.accountName,
    account_name: account.accountName,
    slotKind: slot.kind,
    kind: slot.kind,
    rowNumber: slot.rowNumber,
    requestedFrom: "vercel_jmty_gui",
    ...extra,
  };
}

function jobTone(status?: string) {
  if (status === "done") return "done";
  if (status === "failed") return "failed";
  if (status === "running") return "running";
  return "queued";
}

function syncTone(status?: string) {
  if (status === "synced") return "done";
  if (status === "dirty" || status === "local_only") return "warning";
  if (status === "missing") return "failed";
  return "queued";
}

function latestSlotJob(jobs: Job[], accountName: string, kind: string) {
  return jobs.find((job) => {
    const payload = job.payload || {};
    return payload.accountName === accountName || payload.account_name === accountName
      ? payload.slotKind === kind || payload.kind === kind
      : false;
  });
}

function slotHistories(slot: JmtySlotState, type: "post" | "image") {
  const camel = type === "post" ? slot.postHistory : slot.imageHistory;
  const snake = type === "post" ? slot.post_history : slot.image_history;
  return camel || snake || [];
}

function historyKey(account: JmtyAccountState, slot: JmtySlotState, type: "post" | "image") {
  return `${account.accountName}::${slot.kind}::${type}`;
}

function FieldPayloadForm({
  children,
  onSubmit,
  className,
}: {
  children: ReactNode;
  onSubmit: (form: HTMLFormElement) => void;
  className?: string;
}) {
  return (
    <form
      className={className || "web-form"}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(event.currentTarget);
      }}
    >
      {children}
    </form>
  );
}

export default function JmtyDashboardClient({ snapshot, jobs, user }: Props) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [pendingMessage, setPendingMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [activeJobType, setActiveJobType] = useState<JobType | null>(null);
  const [expandedHistoryKey, setExpandedHistoryKey] = useState("");
  const accounts = snapshot?.accounts || [];
  const queuedCount = jobs.filter((job) => job.status === "queued").length;
  const runningCount = jobs.filter((job) => job.status === "running").length;
  const dirtyCount = snapshot?.syncSummary?.dirtyCount ?? snapshot?.syncSummary?.dirty_count ?? 0;
  const workerStatus = snapshot?.workerStatus?.status || (snapshot ? "同期済み" : "未同期");
  const failedValidationCount = accounts.reduce(
    (sum, account) => sum + account.slots.filter((slot) => ["suspect", "error"].includes(slot.validationStatus || "")).length,
    0,
  );
  const recentBySlot = useMemo(() => jobs.slice(0, 30), [jobs]);
  const isQueueingJob = activeJobType !== null;
  const failedValidationActionDisabled = isQueueingJob || failedValidationCount === 0;
  const failedValidationActionTitle = failedValidationCount === 0 ? "要確認または検証失敗の投稿文がないため、再作成対象がありません" : undefined;

  function queueLabel(type: JobType, label: string) {
    return activeJobType === type ? "追加中..." : label;
  }

  function failedValidationLabel(label: string) {
    return failedValidationCount ? `${label} (${failedValidationCount})` : `${label} (対象なし)`;
  }

  async function queueJob(type: JobType, payload: Record<string, unknown> = {}) {
    setErrorMessage("");
    setPendingMessage(`${jobLabels[type] || type} をキューに追加しています...`);
    setActiveJobType(type);
    try {
      const response = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, payload: { requestedFrom: "vercel_jmty_gui", ...payload } }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setPendingMessage("");
        setErrorMessage(String(data.error || "ジョブ作成に失敗しました"));
        return;
      }
      setPendingMessage(`${jobLabels[type] || type} をキューに追加しました。Mac workerが処理します。`);
      router.refresh();
    } catch (error) {
      setPendingMessage("");
      setErrorMessage(error instanceof Error ? error.message : "ジョブ作成に失敗しました");
    } finally {
      setActiveJobType(null);
    }
  }

  function queueForm(type: JobType, fixedPayload: Record<string, unknown> = {}) {
    return (form: HTMLFormElement) => {
      const formData = new FormData(form);
      const payload: Record<string, unknown> = { ...fixedPayload };
      formData.forEach((value, key) => {
        payload[key] = String(value);
      });
      void queueJob(type, payload);
    };
  }

  function renderHistoryList(account: JmtyAccountState, slot: JmtySlotState, type: "post" | "image") {
    const key = historyKey(account, slot, type);
    if (expandedHistoryKey !== key) {
      return null;
    }
    const histories = slotHistories(slot, type);
    const restoreType: JobType = type === "post" ? "restore_post_history" : "restore_image_history";
    return (
      <div className="web-history-list">
        {histories.length ? histories.map((entry: JmtyHistoryEntry) => (
          <article className="web-history-item" key={`${key}-${entry.commit}`}>
            <div>
              <strong>{entry.title || entry.subject || (type === "post" ? "投稿文履歴" : "画像履歴")}</strong>
              <p>{formatDate(entry.committedAt)} / {entry.branch} / {entry.shortCommit || entry.commit.slice(0, 12)}</p>
              {entry.preview ? <span>{preview(entry.preview, 120)}</span> : null}
            </div>
            <button
              type="button"
              disabled={isQueueingJob}
              onClick={() => queueJob(restoreType, slotPayload(account, slot, { commit: entry.commit }))}
            >
              復元
            </button>
          </article>
        )) : <div className="web-empty compact">まだ履歴がありません</div>}
      </div>
    );
  }

  function renderSlotCard(account: JmtyAccountState, slot: JmtySlotState, mode: "dashboard" | "image" = "dashboard") {
    const recent = latestSlotJob(recentBySlot, account.accountName, slot.kind);
    const imageHistoryKey = historyKey(account, slot, "image");
    return (
      <article className="web-slot-card" key={`${account.accountName}-${slot.kind}`}>
        <div className="web-slot-head">
          <div>
            <h3>{slotLabels[slot.kind] || slot.label}</h3>
            <p>{slot.region || "地域未取得"} / {slot.salary || "給与未取得"}</p>
          </div>
          <span className={`web-badge ${slot.approved ? "done" : slot.hasPost ? "queued" : "failed"}`}>
            {slot.approved ? "OK" : slot.hasPost ? "作成済み" : "未作成"}
          </span>
        </div>
        {slot.imageThumbnailBase64 ? (
          <img className="web-slot-image" src={slot.imageThumbnailBase64} alt={`${account.accountName} ${slot.label}`} />
        ) : (
          <div className="web-image-empty">画像なし</div>
        )}
        <p className="web-preview">{preview(slot.postText || slot.postPreview, 150)}</p>
        <div className="web-chip-row">
          <span className={`web-badge ${syncTone(slot.postSyncStatus)}`}>スプレッドシート {slot.postSyncStatus || "unknown"}</span>
          <span className={`web-badge ${slot.hasPrompt ? "done" : "queued"}`}>プロンプト {slot.hasPrompt ? "あり" : "なし"}</span>
          <span className={`web-badge ${slot.validationStatus === "ok" ? "done" : "queued"}`}>{slot.validationStatus || "未検証"}</span>
        </div>
        {recent ? <p className="web-job-hint">最新ジョブ: {jobLabels[recent.type] || recent.type} / {statusLabels[recent.status]}</p> : null}
        <div className="web-action-grid">
          <button onClick={() => queueJob("generate_image", slotPayload(account, slot))}>画像生成</button>
          <button type="button" onClick={() => setExpandedHistoryKey(expandedHistoryKey === imageHistoryKey ? "" : imageHistoryKey)}>画像履歴</button>
          <button onClick={() => queueJob("validate_image", slotPayload(account, slot))}>{slot.validationStatus ? "再検証" : "画像検証"}</button>
          {mode === "image" && slot.hasImage ? <button onClick={() => queueJob("cancel_image", slotPayload(account, slot))}>画像登録取消</button> : null}
          {mode === "image" && !slot.approved && slot.hasImage ? <button onClick={() => queueJob("approve_image", slotPayload(account, slot))}>OK</button> : null}
        </div>
        {renderHistoryList(account, slot, "image")}
      </article>
    );
  }

  function renderRulesForm(type: "save_post_rules" | "save_image_rules", title: string, rules?: Record<string, unknown>) {
    return (
      <section className="web-panel">
        <h2>{title}</h2>
        <FieldPayloadForm onSubmit={queueForm(type)}>
          <div className="web-rule-grid">
            <label>全体共通<textarea name="common" defaultValue={String(rules?.common || "")} /></label>
            <label>工場専用<textarea name="factory" defaultValue={String(rules?.factory || "")} /></label>
            <label>在宅専用<textarea name="remote" defaultValue={String(rules?.remote || "")} /></label>
          </div>
          <button className="web-primary">ルールを保存</button>
        </FieldPayloadForm>
      </section>
    );
  }

  function renderSampleGroups(groups: JmtySampleGroup[] | undefined, type: "project" | "style") {
    return (groups || []).map((group) => (
      <section className="web-panel" key={`${type}-${group.category}`}>
        <h2>{group.label}</h2>
        <div className="web-sample-grid">
          {group.files.length ? group.files.map((file) => (
            <FieldPayloadForm
              key={`${group.category}-${file.name}`}
              onSubmit={queueForm(type === "project" ? "save_project_sample" : "save_post_style_sample", {
                category: group.category,
                filename: file.name,
              })}
            >
              <div className="web-sample-card">
                <strong>{file.name}</strong>
                <input type="hidden" name="category" value={group.category} />
                <input type="hidden" name="filename" value={file.name} />
                <textarea name="text" defaultValue={file.text || ""} />
                <div className="web-action-row">
                  <button className="web-primary">保存</button>
                  {type === "style" ? (
                    <button type="button" onClick={() => queueJob("delete_post_style_sample", { category: group.category, filename: file.name })}>削除</button>
                  ) : null}
                </div>
              </div>
            </FieldPayloadForm>
          )) : <div className="web-empty">見本なし</div>}
        </div>
      </section>
    ));
  }

  return (
    <main className="jmty-web-shell">
      <header className="jmty-web-header">
        <div>
          <h1>JMTY GUI</h1>
          <p>{snapshot?.sourceRoot || "Mac workerから状態を取得してください"}</p>
        </div>
        <div className="web-header-actions">
          <span className="web-pill">{user.accountName}</span>
          <span className={`web-badge ${snapshot ? "done" : "failed"}`}>worker {workerStatus}</span>
          <button onClick={() => queueJob("sync_state")}>最新状態取得</button>
          <a className="web-button" href="/logout">ログアウト</a>
        </div>
      </header>

      <section className="web-status-grid">
        <div><strong>{formatDate(snapshot?.syncedAt)}</strong><span>最終同期</span></div>
        <div><strong>{queuedCount}</strong><span>処理待ち</span></div>
        <div><strong>{runningCount}</strong><span>実行中</span></div>
        <div><strong>{dirtyCount}</strong><span>スプレッドシート未反映</span></div>
        <div><strong>{snapshot?.gwsStatus?.label || "未確認"}</strong><span>gws</span></div>
      </section>

      {pendingMessage ? <div className="web-notice">{pendingMessage}</div> : null}
      {errorMessage ? <div className="web-notice error">{errorMessage}</div> : null}

      <nav className="web-tabs" aria-label="JMTY GUI views">
        <select value={activeTab} onChange={(event) => setActiveTab(event.target.value as TabKey)}>
          {tabs.map((tab) => <option key={tab.key} value={tab.key}>{tab.label}</option>)}
        </select>
        <div className="web-tab-buttons">
          {tabs.map((tab) => (
            <button key={tab.key} className={activeTab === tab.key ? "active" : ""} onClick={() => setActiveTab(tab.key)}>
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {activeTab === "dashboard" ? (
        <section className="web-view">
          <div className="web-panel-headline">
            <h2>ダッシュボード</h2>
            <div className="web-action-row">
              <button disabled={isQueueingJob} onClick={() => queueJob("prepare_posts")}>{queueLabel("prepare_posts", "投稿文一括AI再作成")}</button>
              <button disabled={failedValidationActionDisabled} title={failedValidationActionTitle} onClick={() => queueJob("rewrite_failed_validation_posts")}>
                {queueLabel("rewrite_failed_validation_posts", failedValidationLabel("検証NG投稿文AI再作成"))}
              </button>
              <button disabled={isQueueingJob} onClick={() => queueJob("reload_sheet")}>{queueLabel("reload_sheet", "シート読込")}</button>
              <button disabled={isQueueingJob} onClick={() => queueJob("sync_all_dirty_posts_to_sheet")}>{queueLabel("sync_all_dirty_posts_to_sheet", "未反映をスプレッドシートに反映")}</button>
            </div>
          </div>
          {accounts.length ? accounts.map((account) => (
            <section className="web-account" key={account.accountName}>
              <div className="web-account-head"><h2>{account.accountName}</h2><span>{account.slots.filter((slot) => slot.hasPost).length}/3 投稿文</span></div>
              <div className="web-slot-grid">{account.slots.map((slot) => renderSlotCard(account, slot))}</div>
            </section>
          )) : <div className="web-empty">まだ状態が同期されていません。最新状態取得を押してMac workerを実行してください。</div>}
        </section>
      ) : null}

      {activeTab === "posts" ? (
        <section className="web-view">
          {renderRulesForm("save_post_rules", "投稿文作成ルール", snapshot?.postRules)}
          <div className="web-panel-headline">
            <h2>投稿文管理</h2>
            <div className="web-action-row">
              <button disabled={failedValidationActionDisabled} title={failedValidationActionTitle} onClick={() => queueJob("rewrite_failed_validation_posts")}>
                {queueLabel("rewrite_failed_validation_posts", failedValidationLabel("検証NGだけAI再作成"))}
              </button>
              <button disabled={isQueueingJob} onClick={() => queueJob("rewrite_all_posts_with_style")}>{queueLabel("rewrite_all_posts_with_style", "投稿文一括AI再作成")}</button>
            </div>
          </div>
          {accounts.map((account) => (
            <section className="web-account" key={`posts-${account.accountName}`}>
              <div className="web-account-head"><h2>{account.accountName}</h2></div>
              <div className="web-edit-grid">
                {account.slots.map((slot) => (
                  <FieldPayloadForm key={`${account.accountName}-${slot.kind}-post`} onSubmit={queueForm("save_post", slotPayload(account, slot))}>
                    <div className="web-edit-card">
                      <h3>{slotLabels[slot.kind] || slot.label}</h3>
                      <input type="hidden" name="accountName" value={account.accountName} />
                      <input type="hidden" name="slotKind" value={slot.kind} />
                      <textarea name="text" defaultValue={slot.postText || ""} />
                      <div className="web-action-row">
                        <button className="web-primary">アプリに保存</button>
                        <button type="button" disabled={isQueueingJob} onClick={() => queueJob("sync_post_to_sheet", slotPayload(account, slot))}>スプレッドシートに反映</button>
                        <button type="button" disabled={isQueueingJob} onClick={() => queueJob("rewrite_post_with_style", slotPayload(account, slot))}>{queueLabel("rewrite_post_with_style", "AI再作成")}</button>
                        <button
                          type="button"
                          onClick={() => {
                            const key = historyKey(account, slot, "post");
                            setExpandedHistoryKey(expandedHistoryKey === key ? "" : key);
                          }}
                        >
                          投稿文履歴
                        </button>
                      </div>
                      {renderHistoryList(account, slot, "post")}
                    </div>
                  </FieldPayloadForm>
                ))}
              </div>
            </section>
          ))}
        </section>
      ) : null}

      {activeTab === "rotation" ? (
        <section className="web-view web-panel">
          <h2>地域・ローテーション</h2>
          <p>ローテーション確認後、スプレッドシートへの反映と再読込をMac workerへ依頼します。</p>
          <div className="web-action-row">
            <button onClick={() => queueJob("rotate_sheet", { mode: "apply" })}>ローテーションをスプレッドシートに反映</button>
            <button onClick={() => queueJob("reload_sheet")}>シート読込</button>
            <button onClick={() => queueJob("save_sheet_mapping")}>基本情報設定を反映</button>
          </div>
        </section>
      ) : null}

      {activeTab === "images" ? (
        <section className="web-view">
          <div className="web-panel-headline">
            <h2>画像生成</h2>
            <div className="web-action-row">
              <button disabled={failedValidationActionDisabled} title={failedValidationActionTitle} onClick={() => queueJob("rewrite_failed_validation_posts")}>
                {queueLabel("rewrite_failed_validation_posts", failedValidationLabel("NG投稿文再作成"))}
              </button>
              <button disabled={isQueueingJob} onClick={() => queueJob("sync_drive")}>{queueLabel("sync_drive", "Driveへ反映")}</button>
              <button disabled={isQueueingJob} onClick={() => queueJob("sync_sheet")}>{queueLabel("sync_sheet", "スプレッドシートに反映")}</button>
            </div>
          </div>
          {accounts.map((account) => <section className="web-account" key={`images-${account.accountName}`}><div className="web-account-head"><h2>{account.accountName}</h2></div><div className="web-slot-grid">{account.slots.map((slot) => renderSlotCard(account, slot, "image"))}</div></section>)}
        </section>
      ) : null}

      {activeTab === "prompts" ? (
        <section className="web-view">
          {renderRulesForm("save_image_rules", "画像生成ルール", snapshot?.imageRules)}
          {accounts.map((account) => (
            <section className="web-account" key={`prompts-${account.accountName}`}>
              <div className="web-account-head"><h2>{account.accountName}</h2></div>
              <div className="web-edit-grid">
                {account.slots.map((slot) => (
                  <FieldPayloadForm key={`${account.accountName}-${slot.kind}-prompt`} onSubmit={queueForm("save_image_prompt", slotPayload(account, slot))}>
                    <div className="web-edit-card">
                      <h3>{slotLabels[slot.kind] || slot.label}</h3>
                      <textarea name="text" defaultValue={slot.promptText || slot.promptPreview || ""} />
                      <button className="web-primary">画像プロンプトを保存</button>
                    </div>
                  </FieldPayloadForm>
                ))}
              </div>
            </section>
          ))}
        </section>
      ) : null}

      {activeTab === "logs" ? (
        <section className="web-view web-panel">
          <h2>実行ログ</h2>
          <div className="web-job-list">
            {jobs.map((job) => (
              <article className="web-job-card" key={job.id}>
                <div><span className={`web-badge ${jobTone(job.status)}`}>{statusLabels[job.status]}</span> <strong>{jobLabels[job.type] || job.type}</strong></div>
                <code>{job.id}</code>
                <pre>{JSON.stringify({ payload: job.payload, result: job.result, error: job.error, logs: job.logs.slice(-5) }, null, 2)}</pre>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {activeTab === "samples" ? (
        <section className="web-view">
          <section className="web-panel">
            <h2>新規スタイル見本</h2>
            <FieldPayloadForm onSubmit={queueForm("save_post_style_sample")}>
              <div className="web-two-col">
                <label>種別<select name="category" defaultValue="factory"><option value="factory">工場</option><option value="remote">在宅</option></select></label>
                <label>ファイル名<input name="filename" placeholder="factory_style_01.md" /></label>
              </div>
              <textarea name="text" placeholder="投稿文スタイル見本を貼り付けます。" />
              <button className="web-primary">スタイル見本を保存</button>
            </FieldPayloadForm>
          </section>
          <div className="web-panel-headline"><h2>案件素材</h2></div>
          {renderSampleGroups(snapshot?.projectSamples?.groups, "project")}
          <div className="web-panel-headline"><h2>投稿文スタイル見本</h2></div>
          {renderSampleGroups(snapshot?.postStyleSamples?.groups, "style")}
        </section>
      ) : null}
    </main>
  );
}
