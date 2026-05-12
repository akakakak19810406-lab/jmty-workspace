// JMTY GUI の管理者画面です。
// 管理権限を持つユーザーだけがユーザー一覧、
// 権限付与、全実行ログを確認できます。
import Link from "next/link";
import { revalidatePath } from "next/cache";
import { listAuditLogs, listUsers, requireAdmin, setUserAdmin } from "@/lib/auth";

async function setAdminAction(formData: FormData) {
  "use server";
  const actor = await requireAdmin();
  await setUserAdmin({
    actor,
    targetUserId: String(formData.get("userId") ?? ""),
    isAdmin: String(formData.get("isAdmin") ?? "") === "true",
  });
  revalidatePath("/admin");
}

function shortHash(hash: string) {
  return `${hash.slice(0, 22)}...${hash.slice(-10)}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export default async function AdminPage() {
  await requireAdmin();
  const [users, logs] = await Promise.all([listUsers(), listAuditLogs()]);

  return (
    <main className="page wide-page">
      <div className="topbar">
        <div>
          <h1>管理者画面</h1>
          <p className="subtle">ユーザー、管理権限、全実行ログを確認します。</p>
        </div>
        <Link className="button secondary" href="/">
          JMTY GUI
        </Link>
      </div>

      <section className="panel admin-section">
        <h2>ユーザー一覧</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>アカウント名</th>
                <th>メールアドレス</th>
                <th>管理者</th>
                <th>パスワードハッシュ</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.accountName}</td>
                  <td>{user.email}</td>
                  <td>{user.isAdmin ? "あり" : "なし"}</td>
                  <td><code>{shortHash(user.passwordHash)}</code></td>
                  <td>
                    <form action={setAdminAction}>
                      <input type="hidden" name="userId" value={user.id} />
                      <input type="hidden" name="isAdmin" value={String(!user.isAdmin)} />
                      <button className="button secondary" type="submit">
                        {user.isAdmin ? "権限を外す" : "管理者にする"}
                      </button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel admin-section">
        <h2>全実行ログ</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>日時</th>
                <th>ユーザー</th>
                <th>メール</th>
                <th>操作</th>
                <th>詳細</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td>{formatDate(log.createdAt)}</td>
                  <td>{log.accountName ?? ""}</td>
                  <td>{log.email ?? ""}</td>
                  <td>{log.action}</td>
                  <td><pre className="compact-pre">{JSON.stringify(log.metadata ?? {}, null, 2)}</pre></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
