// JMTY Control の軽量ストア層です。
// 本番ではNeon/PostgresのJSONBテーブルを優先し、
// 未設定時はUpstash Redis、ローカルJSONファイルへフォールバックします。
import { promises as fs } from "node:fs";
import path from "node:path";
import { randomBytes } from "node:crypto";
import { neon } from "@neondatabase/serverless";

const LOCAL_STORE_DIR = process.env.JMTY_CONTROL_STORE_DIR ?? "/tmp/jmty-control-store";
type SqlClient = ReturnType<typeof neon>;

let dbClient: SqlClient | null | undefined;
let dbReady: Promise<void> | null = null;

export function nowIso() {
  return new Date().toISOString();
}

export function makeId(prefix: string) {
  return `${prefix}_${Date.now().toString(36)}_${randomBytes(4).toString("hex")}`;
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

async function ensureDatabase(sql: SqlClient) {
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

async function readDatabaseJson<T>(key: string, fallback: T): Promise<T> {
  const sql = getDbClient();
  if (!sql) {
    return fallback;
  }

  await ensureDatabase(sql);
  const rows = (await sql`
    SELECT value
    FROM jmty_control_store
    WHERE store_key = ${key}
    LIMIT 1
  `) as Array<{ value: T | string | null }>;
  const value = rows[0]?.value;
  if (value == null) {
    return fallback;
  }
  return typeof value === "string" ? (JSON.parse(value) as T) : (value as T);
}

async function writeDatabaseJson<T>(key: string, value: T) {
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

async function redisCommand<T>(command: unknown[]): Promise<T> {
  const response = await fetch(`${process.env.UPSTASH_REDIS_REST_URL}/pipeline`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.UPSTASH_REDIS_REST_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify([command]),
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Redis command failed: ${response.status}`);
  }

  const [data] = (await response.json()) as [{ result: T; error?: string }];
  if (data.error) {
    throw new Error(data.error);
  }
  return data.result;
}

function localPathForKey(key: string) {
  return path.join(LOCAL_STORE_DIR, `${key.replace(/[^a-zA-Z0-9_-]/g, "_")}.json`);
}

export async function readJson<T>(key: string, fallback: T): Promise<T> {
  if (getDbClient()) {
    return readDatabaseJson(key, fallback);
  }

  if (hasRedisEnv()) {
    const raw = await redisCommand<string | null>(["GET", key]);
    return raw ? (JSON.parse(raw) as T) : fallback;
  }

  try {
    const raw = await fs.readFile(localPathForKey(key), "utf8");
    return JSON.parse(raw) as T;
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "ENOENT") {
      return fallback;
    }
    throw error;
  }
}

export async function writeJson<T>(key: string, value: T) {
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
