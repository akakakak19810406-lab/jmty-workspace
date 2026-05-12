// JMTY control の Next.js 設定です。
// Vercel へそのまま載せる管理画面とAPIを定義し、
// Macワーカーとのジョブ連携を担います。
import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  outputFileTracingRoot: appRoot,
};

export default nextConfig;
