// JMTY job queue の型と保存処理です。
// Vercel側で作られた操作依頼を保持し、
// Macワーカーがclaimして結果を返すための状態遷移を扱います。
import { makeId, nowIso, readJson, writeJson } from "@/lib/store";
import { addAuditLog } from "@/lib/auth";

export const JOB_TYPES = [
  "test",
  "sync_state",
  "generate_image",
  "validate_image",
  "sync_drive",
  "sync_sheet",
  "rotate_sheet",
  "prepare_posts",
  "save_post",
  "sync_post_to_sheet",
  "sync_all_dirty_posts_to_sheet",
  "rewrite_post_with_style",
  "rewrite_all_posts_with_style",
  "rewrite_failed_validation_posts",
  "save_image_prompt",
  "cancel_image",
  "approve_image",
  "save_project_sample",
  "save_post_style_sample",
  "delete_post_style_sample",
  "save_post_rules",
  "save_image_rules",
  "reload_sheet",
  "save_sheet_mapping",
] as const;

export const JOB_STATUSES = ["queued", "running", "done", "failed", "cancelled"] as const;

export type JobType = (typeof JOB_TYPES)[number];
export type JobStatus = (typeof JOB_STATUSES)[number];

export type Job = {
  id: string;
  type: JobType;
  status: JobStatus;
  payload: Record<string, unknown>;
  createdBy?: string;
  createdByEmail?: string;
  createdByAccountName?: string;
  result?: Record<string, unknown>;
  error?: string;
  logs: string[];
  retryCount: number;
  workerId?: string;
  lockedAt?: string;
  createdAt: string;
  updatedAt: string;
  finishedAt?: string;
};

const REDIS_KEY = "jmty:jobs:v1";
const RUNNING_TIMEOUT_MS = Number(process.env.JMTY_RUNNING_TIMEOUT_MS ?? 30 * 60 * 1000);

function isJobType(value: unknown): value is JobType {
  return typeof value === "string" && JOB_TYPES.includes(value as JobType);
}

async function readJobs(): Promise<Job[]> {
  return readJson<Job[]>(REDIS_KEY, []);
}

async function writeJobs(jobs: Job[]) {
  await writeJson(REDIS_KEY, jobs);
}

function recoverTimedOutJobs(jobs: Job[]) {
  const now = Date.now();
  let changed = false;
  const recovered = jobs.map((job) => {
    if (job.status !== "running" || !job.lockedAt) {
      return job;
    }
    const lockedAt = new Date(job.lockedAt).getTime();
    if (Number.isNaN(lockedAt) || now - lockedAt < RUNNING_TIMEOUT_MS) {
      return job;
    }
    changed = true;
    return {
      ...job,
      status: "queued" as const,
      workerId: undefined,
      lockedAt: undefined,
      retryCount: job.retryCount + 1,
      updatedAt: nowIso(),
      logs: [...job.logs, `Recovered from timed-out running state at ${nowIso()}`],
    };
  });
  return { jobs: recovered, changed };
}

export async function listJobs() {
  const jobs = await readJobs();
  const recovered = recoverTimedOutJobs(jobs);
  if (recovered.changed) {
    await writeJobs(recovered.jobs);
  }
  return recovered.jobs.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function createJob(input: {
  type: unknown;
  payload?: unknown;
  actor?: { id: string; email: string; accountName: string };
}) {
  if (!isJobType(input.type)) {
    throw new Error("Unsupported job type");
  }
  const payload =
    input.payload && typeof input.payload === "object" && !Array.isArray(input.payload)
      ? (input.payload as Record<string, unknown>)
      : {};
  const timestamp = nowIso();
  const job: Job = {
    id: makeId("job"),
    type: input.type,
    status: "queued",
    payload,
    createdBy: input.actor?.id,
    createdByEmail: input.actor?.email,
    createdByAccountName: input.actor?.accountName,
    logs: [`Queued at ${timestamp}`],
    retryCount: 0,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
  const jobs = await readJobs();
  await writeJobs([job, ...jobs]);
  await addAuditLog({
    userId: input.actor?.id,
    email: input.actor?.email,
    accountName: input.actor?.accountName,
    action: "job.created",
    targetType: "job",
    targetId: job.id,
    metadata: { type: job.type, payload: job.payload },
  });
  return job;
}

export async function claimNextJob(workerId: string) {
  const jobs = await readJobs();
  const recovered = recoverTimedOutJobs(jobs);
  const index = recovered.jobs.findIndex((job) => job.status === "queued");
  if (index === -1) {
    if (recovered.changed) {
      await writeJobs(recovered.jobs);
    }
    return null;
  }
  const timestamp = nowIso();
  const job = recovered.jobs[index];
  const claimed: Job = {
    ...job,
    status: "running",
    workerId,
    lockedAt: timestamp,
    updatedAt: timestamp,
    logs: [...job.logs, `Claimed by ${workerId} at ${timestamp}`],
  };
  recovered.jobs[index] = claimed;
  await writeJobs(recovered.jobs);
  return claimed;
}

export async function completeJob(input: {
  id: string;
  workerId: string;
  status: "done" | "failed";
  result?: unknown;
  error?: unknown;
  logs?: unknown;
}) {
  const jobs = await readJobs();
  const index = jobs.findIndex((job) => job.id === input.id);
  if (index === -1) {
    throw new Error("Job not found");
  }
  const job = jobs[index];
  if (job.status !== "running" || job.workerId !== input.workerId) {
    throw new Error("Job is not claimed by this worker");
  }
  const timestamp = nowIso();
  const result =
    input.result && typeof input.result === "object" && !Array.isArray(input.result)
      ? (input.result as Record<string, unknown>)
      : undefined;
  const extraLogs = Array.isArray(input.logs) ? input.logs.filter((item) => typeof item === "string") : [];
  const updated: Job = {
    ...job,
    status: input.status,
    result,
    error: typeof input.error === "string" ? input.error : undefined,
    updatedAt: timestamp,
    finishedAt: timestamp,
    logs: [...job.logs, ...extraLogs, `${input.status} at ${timestamp}`],
  };
  jobs[index] = updated;
  await writeJobs(jobs);
  return updated;
}
