#!/usr/bin/env node
// JMTY Control の初期管理者をDBへ直接作成するCLIです。
// メールアドレスとパスワードは環境変数から受け取り、
// パスワードはPBKDF2ハッシュとして保存します。
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { neon } from "@neondatabase/serverless";

const USERS_KEY = "jmty:users:v1";
const AUDIT_LOGS_KEY = "jmty:audit_logs:v1";
const LOCAL_STORE_DIR = process.env.JMTY_CONTROL_STORE_DIR ?? "/tmp/jmty-control-store";
const PBKDF2_ITERATIONS = 310000;
let dbClient;
let dbReady = null;

function required(name) {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function nowIso() {
  return new Date().toISOString();
}

function makeId(prefix) {
  return `${prefix}_${Date.now().toString(36)}_${crypto.randomBytes(4).toString("hex")}`;
}

function normalizeEmail(email) {
  return email.trim().toLowerCase();
}

function hashPassword(password, salt = crypto.randomBytes(16).toString("hex")) {
  const hash = crypto.pbkdf2Sync(password, salt, PBKDF2_ITERATIONS, 32, "sha256").toString("hex");
  return `pbkdf2$sha256$${PBKDF2_ITERATIONS}$${salt}$${hash}`;
}

function hasRedisEnv() {
  return Boolean(process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN);
}

function databaseUrl() {
  return (
    process.env.NEON_DATABASE_URL?.trim() ||
    process.env.DATABASE_URL?.trim() ||
    process.env.POSTGRES_URL?.trim() ||
    ""
  );
}

function getDbClient() {
  if (dbClient !== undefined) {
    return dbClient;
  }
  const url = databaseUrl();
  dbClient = url ? neon(url) : null;
  return dbClient;
}

async function ensureDatabase(sql) {
  if (!dbReady) {
    dbReady = sql`
      CREATE TABLE IF NOT EXISTS jmty_control_store (
        store_key text PRIMARY KEY,
        value jsonb NOT NULL,
        updated_at timestamptz NOT NULL DEFAULT now()
      )
    `.then(() => undefined);
  }
  return dbReady;
}

async function readDatabaseJson(key, fallback) {
  const sql = getDbClient();
  if (!sql) {
    return fallback;
  }
  await ensureDatabase(sql);
  const rows = await sql`
    SELECT value
    FROM jmty_control_store
    WHERE store_key = ${key}
    LIMIT 1
  `;
  const value = rows[0]?.value;
  if (value == null) {
    return fallback;
  }
  return typeof value === "string" ? JSON.parse(value) : value;
}

async function writeDatabaseJson(key, value) {
  const sql = getDbClient();
  if (!sql) {
    return false;
  }
  await ensureDatabase(sql);
  await sql`
    INSERT INTO jmty_control_store (store_key, value, updated_at)
    VALUES (${key}, ${JSON.stringify(value)}::jsonb, now())
    ON CONFLICT (store_key)
    DO UPDATE SET value = EXCLUDED.value, updated_at = now()
  `;
  return true;
}

async function redisCommand(command) {
  const response = await fetch(`${process.env.UPSTASH_REDIS_REST_URL}/pipeline`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.UPSTASH_REDIS_REST_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify([command]),
  });
  if (!response.ok) {
    throw new Error(`Redis command failed: ${response.status}`);
  }
  const [data] = await response.json();
  if (data.error) {
    throw new Error(data.error);
  }
  return data.result;
}

function localPathForKey(key) {
  return path.join(LOCAL_STORE_DIR, `${key.replace(/[^a-zA-Z0-9_-]/g, "_")}.json`);
}

async function readJson(key, fallback) {
  if (getDbClient()) {
    return readDatabaseJson(key, fallback);
  }

  if (hasRedisEnv()) {
    const raw = await redisCommand(["GET", key]);
    return raw ? JSON.parse(raw) : fallback;
  }
  try {
    return JSON.parse(await fs.readFile(localPathForKey(key), "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") {
      return fallback;
    }
    throw error;
  }
}

async function writeJson(key, value) {
  if (await writeDatabaseJson(key, value)) {
    return;
  }

  if (hasRedisEnv()) {
    await redisCommand(["SET", key, JSON.stringify(value)]);
    return;
  }
  const target = localPathForKey(key);
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.writeFile(target, JSON.stringify(value, null, 2));
}

async function main() {
  const email = normalizeEmail(required("ADMIN_EMAIL"));
  const password = required("ADMIN_PASSWORD");
  const accountName = required("ADMIN_ACCOUNT_NAME");

  if (!email.includes("@")) {
    throw new Error("ADMIN_EMAIL must be an email address");
  }
  if (password.length < 8) {
    throw new Error("ADMIN_PASSWORD must be at least 8 characters");
  }
  if (accountName.length < 2) {
    throw new Error("ADMIN_ACCOUNT_NAME must be at least 2 characters");
  }

  const users = await readJson(USERS_KEY, []);
  const existing = users.find((user) => user.email === email);
  const timestamp = nowIso();

  if (existing) {
    existing.accountName = accountName;
    existing.passwordHash = hashPassword(password);
    existing.isAdmin = true;
    existing.updatedAt = timestamp;
    await writeJson(USERS_KEY, users);
    console.log(`Updated admin user: ${email}`);
    return;
  }

  if (users.some((user) => user.accountName.toLowerCase() === accountName.toLowerCase())) {
    throw new Error("ADMIN_ACCOUNT_NAME is already used by another user");
  }

  const user = {
    id: makeId("user"),
    email,
    accountName,
    passwordHash: hashPassword(password),
    isAdmin: true,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
  await writeJson(USERS_KEY, [...users, user]);

  const logs = await readJson(AUDIT_LOGS_KEY, []);
  await writeJson(AUDIT_LOGS_KEY, [
    {
      id: makeId("log"),
      userId: user.id,
      email: user.email,
      accountName: user.accountName,
      action: "admin.seeded",
      targetType: "user",
      targetId: user.id,
      metadata: { source: "create-admin-cli" },
      createdAt: timestamp,
    },
    ...logs,
  ]);

  console.log(`Created admin user: ${email}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
