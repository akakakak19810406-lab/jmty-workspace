// JMTY GUI の個人履歴画面です。
// ログイン中のユーザーに紐づく操作ログだけを表示します。
import Link from "next/link";
import { listAuditLogs, requireUser } from "@/lib/auth";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export default async function HistoryPage() {
  const user = await requireUser();
  const logs = await listAuditLogs({ userId: user.id });

  return (
    <main className="page">
      <div className="topbar">
        <div>
          <h1>自分の実行ログ</h1>
          <p className="subtle">{user.accountName} の操作履歴です。</p>
        </div>
        <Link className="button secondary" href="/">
          JMTY GUI
        </Link>
      </div>
      <section className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>日時</th>
                <th>操作</th>
                <th>対象</th>
                <th>詳細</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td>{formatDate(log.createdAt)}</td>
                  <td>{log.action}</td>
                  <td>{log.targetType} {log.targetId}</td>
                  <td><pre className="compact-pre">{JSON.stringify(log.metadata ?? {}, null, 2)}</pre></td>
                </tr>
              ))}
            </tbody>
          </table>
          {logs.length === 0 ? <div className="empty">履歴はまだありません。</div> : null}
        </div>
      </section>
    </main>
  );
}
