// JMTY Control の案件素材ストアです。
// 在宅・工場の案件を後から追加できるようにし、
// 投稿作成ジョブのpayloadから参照できる形で保存します。
import { addAuditLog, type User } from "@/lib/auth";
import { makeId, nowIso, readJson, writeJson } from "@/lib/store";

export const CASE_KINDS = ["remote", "factory"] as const;

export type CaseKind = (typeof CASE_KINDS)[number];

export type CaseMaterial = {
  id: string;
  kind: CaseKind;
  title: string;
  salary: string;
  workStyle: string;
  benefits: string;
  body: string;
  notes: string;
  active: boolean;
  createdBy?: string;
  createdByEmail?: string;
  createdByAccountName?: string;
  createdAt: string;
  updatedAt: string;
};

const CASES_KEY = "jmty:case_materials:v1";

function isCaseKind(value: unknown): value is CaseKind {
  return typeof value === "string" && CASE_KINDS.includes(value as CaseKind);
}

function text(value: FormDataEntryValue | null) {
  return String(value ?? "").trim();
}

async function readCases() {
  return readJson<CaseMaterial[]>(CASES_KEY, []);
}

async function writeCases(cases: CaseMaterial[]) {
  await writeJson(CASES_KEY, cases);
}

export async function listCases(filter?: { kind?: CaseKind; activeOnly?: boolean }) {
  const cases = await readCases();
  return cases
    .filter((item) => (filter?.kind ? item.kind === filter.kind : true))
    .filter((item) => (filter?.activeOnly ? item.active : true))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function createCaseFromForm(formData: FormData, actor?: User | null) {
  const kindRaw = formData.get("kind");
  if (!isCaseKind(kindRaw)) {
    throw new Error("案件種別を選択してください");
  }

  const title = text(formData.get("title"));
  if (!title) {
    throw new Error("案件名を入力してください");
  }

  const timestamp = nowIso();
  const material: CaseMaterial = {
    id: makeId("case"),
    kind: kindRaw,
    title,
    salary: text(formData.get("salary")),
    workStyle: text(formData.get("workStyle")),
    benefits: text(formData.get("benefits")),
    body: text(formData.get("body")),
    notes: text(formData.get("notes")),
    active: true,
    createdBy: actor?.id,
    createdByEmail: actor?.email,
    createdByAccountName: actor?.accountName,
    createdAt: timestamp,
    updatedAt: timestamp,
  };

  const cases = await readCases();
  await writeCases([material, ...cases]);
  await addAuditLog({
    userId: actor?.id,
    email: actor?.email,
    accountName: actor?.accountName,
    action: "case.created",
    targetType: "case",
    targetId: material.id,
    metadata: { kind: material.kind, title: material.title },
  });
  return material;
}

export async function setCaseActive(input: { id: string; active: boolean; actor?: User | null }) {
  const cases = await readCases();
  const target = cases.find((item) => item.id === input.id);
  if (!target) {
    throw new Error("案件素材が見つかりません");
  }
  target.active = input.active;
  target.updatedAt = nowIso();
  await writeCases(cases);
  await addAuditLog({
    userId: input.actor?.id,
    email: input.actor?.email,
    accountName: input.actor?.accountName,
    action: input.active ? "case.activated" : "case.archived",
    targetType: "case",
    targetId: target.id,
    metadata: { kind: target.kind, title: target.title },
  });
}
