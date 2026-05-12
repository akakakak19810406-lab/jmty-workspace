// Macワーカーが次の待機ジョブを取得するAPIです。
// 取得時にrunningへ遷移させ、workerIdとlockedAtで
// 二重実行やタイムアウト復旧を扱えるようにします。
import { NextRequest, NextResponse } from "next/server";
import { assertWorkerToken } from "@/lib/auth";
import { claimNextJob } from "@/lib/jobs";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    assertWorkerToken(request);
    const body = await request.json();
    const workerId = typeof body.workerId === "string" ? body.workerId : "unknown-worker";
    const job = await claimNextJob(workerId);
    return NextResponse.json({ job });
  } catch (error) {
    const message = (error as Error).message;
    return NextResponse.json({ error: message }, { status: message === "Unauthorized" ? 401 : 400 });
  }
}
