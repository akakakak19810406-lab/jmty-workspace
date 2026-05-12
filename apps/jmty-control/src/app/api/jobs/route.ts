// JMTY job queue の一覧取得と作成APIです。
// 管理画面からジョブを積み、Macワーカーが後続APIで拾える
// 永続キューへ保存します。
import { NextRequest, NextResponse } from "next/server";
import { createJob, listJobs } from "@/lib/jobs";
import { getCurrentUserFromRequest } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const user = await getCurrentUserFromRequest(request);
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  return NextResponse.json({ jobs: await listJobs() });
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const user = await getCurrentUserFromRequest(request);
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const job = await createJob({ type: body.type, payload: body.payload, actor: user });
    return NextResponse.json({ job }, { status: 201 });
  } catch (error) {
    return NextResponse.json({ error: (error as Error).message }, { status: 400 });
  }
}
