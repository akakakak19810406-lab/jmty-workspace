// Macワーカーがジョブ結果を返すAPIです。
// running状態のジョブだけをdone/failedへ確定し、
// 実行ログと結果JSONを管理画面へ反映します。
import { NextRequest, NextResponse } from "next/server";
import { assertWorkerToken } from "@/lib/auth";
import { completeJob } from "@/lib/jobs";
import { saveJmtySnapshot } from "@/lib/jmty-state";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  try {
    assertWorkerToken(request);
    const params = await context.params;
    const body = await request.json();
    const status = body.status === "failed" ? "failed" : "done";
    const workerId = typeof body.workerId === "string" ? body.workerId : "";
    const job = await completeJob({
      id: params.id,
      workerId,
      status,
      result: body.result,
      error: body.error,
      logs: body.logs,
    });
    if (status === "done" && body.result?.snapshot) {
      await saveJmtySnapshot(body.result.snapshot);
    }
    return NextResponse.json({ job });
  } catch (error) {
    const message = (error as Error).message;
    return NextResponse.json({ error: message }, { status: message === "Unauthorized" ? 401 : 400 });
  }
}
