// JMTY Control の認証とワーカー認可です。
// ユーザーパスワードは平文保存せずPBKDF2ハッシュで保持し、
// Macワーカー更新APIは共有トークンで保護します。
import crypto from "node:crypto";
import { NextRequest } from "next/server";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { makeId, nowIso, readJson, writeJson } from "@/lib/store";

export function assertWorkerToken(request: NextRequest) {
  const expected = process.env.JMTY_WORKER_TOKEN;
  if (!expected) {
    return;
  }
  const actual = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "");
  if (actual !== expected) {
    throw new Error("Unauthorized");
  }
}

export type User = {
  id: string;
  email: string;
  accountName: string;
  passwordHash: string;
  isAdmin: boolean;
  createdAt: string;
  updatedAt: string;
};

export type Session = {
  id: string;
  userId: string;
  createdAt: string;
  expiresAt: string;
};

export type AuditLog = {
  id: string;
  userId?: string;
  email?: string;
  accountName?: string;
  action: string;
  targetType?: string;
  targetId?: string;
  metadata?: Record<string, unknown>;
  createdAt: string;
};

export type PasswordReset = {
  tokenHash: string;
  userId: string;
  createdAt: string;
  expiresAt: string;
  usedAt?: string;
};

const USERS_KEY = "jmty:users:v1";
const SESSIONS_KEY = "jmty:sessions:v1";
const AUDIT_LOGS_KEY = "jmty:audit_logs:v1";
const PASSWORD_RESETS_KEY = "jmty:password_resets:v1";
const SESSION_COOKIE = "jmty_session";
const SESSION_DAYS = 14;
const RESET_TOKEN_MINUTES = 30;
const PBKDF2_ITERATIONS = 310000;

function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

function normalizeAccountName(accountName: string) {
  return accountName.trim();
}

function hashToken(token: string) {
  return crypto.createHash("sha256").update(token).digest("hex");
}

export function hashPassword(password: string, salt = crypto.randomBytes(16).toString("hex")) {
  const hash = crypto.pbkdf2Sync(password, salt, PBKDF2_ITERATIONS, 32, "sha256").toString("hex");
  return `pbkdf2$sha256$${PBKDF2_ITERATIONS}$${salt}$${hash}`;
}

function verifyPassword(password: string, stored: string) {
  const [scheme, digest, iterationsText, salt, expected] = stored.split("$");
  if (scheme !== "pbkdf2" || digest !== "sha256" || !iterationsText || !salt || !expected) {
    return false;
  }
  const iterations = Number(iterationsText);
  const actual = crypto.pbkdf2Sync(password, salt, iterations, 32, "sha256").toString("hex");
  return crypto.timingSafeEqual(Buffer.from(actual, "hex"), Buffer.from(expected, "hex"));
}

async function readUsers() {
  return readJson<User[]>(USERS_KEY, []);
}

async function writeUsers(users: User[]) {
  await writeJson(USERS_KEY, users);
}

async function readSessions() {
  return readJson<Session[]>(SESSIONS_KEY, []);
}

async function writeSessions(sessions: Session[]) {
  await writeJson(SESSIONS_KEY, sessions);
}

async function readPasswordResets() {
  return readJson<PasswordReset[]>(PASSWORD_RESETS_KEY, []);
}

async function writePasswordResets(resets: PasswordReset[]) {
  await writeJson(PASSWORD_RESETS_KEY, resets);
}

export async function listUsers() {
  const users = await readUsers();
  return users.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

export async function createUser(input: {
  email: string;
  accountName: string;
  password: string;
  isAdmin?: boolean;
}) {
  const email = normalizeEmail(input.email);
  const accountName = normalizeAccountName(input.accountName);
  if (!email.includes("@")) {
    throw new Error("メールアドレスを確認してください");
  }
  if (accountName.length < 2) {
    throw new Error("アカウント名は2文字以上にしてください");
  }
  if (input.password.length < 8) {
    throw new Error("パスワードは8文字以上にしてください");
  }
  const users = await readUsers();
  if (users.some((user) => user.email === email)) {
    throw new Error("このメールアドレスは登録済みです");
  }
  if (users.some((user) => user.accountName.toLowerCase() === accountName.toLowerCase())) {
    throw new Error("このアカウント名は登録済みです");
  }
  const timestamp = nowIso();
  const user: User = {
    id: makeId("user"),
    email,
    accountName,
    passwordHash: hashPassword(input.password),
    isAdmin: Boolean(input.isAdmin),
    createdAt: timestamp,
    updatedAt: timestamp,
  };
  await writeUsers([...users, user]);
  await addAuditLog({
    userId: user.id,
    email: user.email,
    accountName: user.accountName,
    action: "user.registered",
    targetType: "user",
    targetId: user.id,
    metadata: { isAdmin: user.isAdmin },
  });
  return user;
}

export async function authenticateUser(emailInput: string, password: string) {
  const email = normalizeEmail(emailInput);
  const users = await readUsers();
  const user = users.find((item) => item.email === email);
  if (!user || !verifyPassword(password, user.passwordHash)) {
    return null;
  }
  return user;
}

export async function createSession(user: User) {
  const timestamp = nowIso();
  const session: Session = {
    id: makeId("sess"),
    userId: user.id,
    createdAt: timestamp,
    expiresAt: new Date(Date.now() + SESSION_DAYS * 24 * 60 * 60 * 1000).toISOString(),
  };
  const sessions = await readSessions();
  await writeSessions([...sessions.filter((item) => new Date(item.expiresAt).getTime() > Date.now()), session]);
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, session.id, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    expires: new Date(session.expiresAt),
  });
  await addAuditLog({
    userId: user.id,
    email: user.email,
    accountName: user.accountName,
    action: "auth.login",
    targetType: "user",
    targetId: user.id,
  });
}

async function getUserBySessionId(sessionId?: string) {
  if (!sessionId) {
    return null;
  }
  const sessions = await readSessions();
  const session = sessions.find((item) => item.id === sessionId);
  if (!session || new Date(session.expiresAt).getTime() <= Date.now()) {
    return null;
  }
  const users = await readUsers();
  return users.find((user) => user.id === session.userId) ?? null;
}

export async function getCurrentUser() {
  const cookieStore = await cookies();
  return getUserBySessionId(cookieStore.get(SESSION_COOKIE)?.value);
}

export async function getCurrentUserFromRequest(request: NextRequest) {
  return getUserBySessionId(request.cookies.get(SESSION_COOKIE)?.value);
}

export async function requireUser() {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }
  return user;
}

export async function requireAdmin() {
  const user = await requireUser();
  if (!user.isAdmin) {
    redirect("/");
  }
  return user;
}

export async function logoutCurrentUser() {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(SESSION_COOKIE)?.value;
  if (sessionId) {
    const sessions = await readSessions();
    await writeSessions(sessions.filter((session) => session.id !== sessionId));
  }
  cookieStore.delete(SESSION_COOKIE);
}

export async function addAuditLog(input: Omit<AuditLog, "id" | "createdAt">) {
  const logs = await readJson<AuditLog[]>(AUDIT_LOGS_KEY, []);
  const log: AuditLog = {
    id: makeId("log"),
    createdAt: nowIso(),
    ...input,
  };
  await writeJson(AUDIT_LOGS_KEY, [log, ...logs].slice(0, 2000));
  return log;
}

export async function listAuditLogs(filter?: { userId?: string }) {
  const logs = await readJson<AuditLog[]>(AUDIT_LOGS_KEY, []);
  return filter?.userId ? logs.filter((log) => log.userId === filter.userId) : logs;
}

export async function setUserAdmin(input: { targetUserId: string; isAdmin: boolean; actor: User }) {
  const users = await readUsers();
  const target = users.find((user) => user.id === input.targetUserId);
  if (!target) {
    throw new Error("ユーザーが見つかりません");
  }
  target.isAdmin = input.isAdmin;
  target.updatedAt = nowIso();
  await writeUsers(users);
  await addAuditLog({
    userId: input.actor.id,
    email: input.actor.email,
    accountName: input.actor.accountName,
    action: input.isAdmin ? "admin.granted" : "admin.revoked",
    targetType: "user",
    targetId: target.id,
    metadata: { targetEmail: target.email, targetAccountName: target.accountName },
  });
}

export async function createPasswordReset(emailInput: string) {
  const email = normalizeEmail(emailInput);
  const users = await readUsers();
  const user = users.find((item) => item.email === email);
  if (!user) {
    return null;
  }
  const token = crypto.randomBytes(32).toString("hex");
  const reset: PasswordReset = {
    tokenHash: hashToken(token),
    userId: user.id,
    createdAt: nowIso(),
    expiresAt: new Date(Date.now() + RESET_TOKEN_MINUTES * 60 * 1000).toISOString(),
  };
  const resets = await readPasswordResets();
  await writePasswordResets([...resets.filter((item) => !item.usedAt), reset]);
  await addAuditLog({
    userId: user.id,
    email: user.email,
    accountName: user.accountName,
    action: "auth.password_reset_requested",
    targetType: "user",
    targetId: user.id,
  });
  return { user, token };
}

export async function resetPassword(token: string, password: string) {
  if (password.length < 8) {
    throw new Error("パスワードは8文字以上にしてください");
  }
  const resets = await readPasswordResets();
  const tokenHash = hashToken(token);
  const reset = resets.find((item) => item.tokenHash === tokenHash && !item.usedAt);
  if (!reset || new Date(reset.expiresAt).getTime() <= Date.now()) {
    throw new Error("リセットリンクが無効または期限切れです");
  }
  const users = await readUsers();
  const user = users.find((item) => item.id === reset.userId);
  if (!user) {
    throw new Error("ユーザーが見つかりません");
  }
  user.passwordHash = hashPassword(password);
  user.updatedAt = nowIso();
  reset.usedAt = nowIso();
  await writeUsers(users);
  await writePasswordResets(resets);
  await addAuditLog({
    userId: user.id,
    email: user.email,
    accountName: user.accountName,
    action: "auth.password_reset_completed",
    targetType: "user",
    targetId: user.id,
  });
  return user;
}
