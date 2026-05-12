// JMTY GUI Web版のトップ画面です。
// ログイン済みユーザー向けにMac workerのsnapshotとjob履歴を読み込み、
// 実操作はクライアントUIからVercel job queueへ投入します。
import { listJobs } from "@/lib/jobs";
import { requireUser } from "@/lib/auth";
import { getJmtySnapshot } from "@/lib/jmty-state";
import JmtyDashboardClient from "./jmty-dashboard-client";

export const dynamic = "force-dynamic";

export default async function Home() {
  const user = await requireUser();
  const [snapshot, jobs] = await Promise.all([getJmtySnapshot(), listJobs()]);

  return (
    <JmtyDashboardClient
      snapshot={snapshot}
      jobs={jobs.slice(0, 80)}
      user={{ accountName: user.accountName, isAdmin: user.isAdmin }}
    />
  );
}
