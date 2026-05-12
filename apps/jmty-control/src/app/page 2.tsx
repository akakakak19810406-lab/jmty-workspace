// JMTY control の管理画面です。
// ジョブ作成フォームと状態一覧を表示し、
// Macワーカーとの疎通を最小操作で確認できます。
import Link from "next/link";
import { revalidatePath } from "next/cache";
import { createJob, JOB_TYPES, listJobs } from "@/lib/jobs";
import { listCases } from "@/lib/cases";
import { getCurrentUser } from "@/lib/auth";

async function createJobAction(formData: FormData) {
  "use server";
  const type = formData.get("type");
  const payloadText = String(formData.get("payload") ?? "{}").trim() || "{}";
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(payloadText) as Record<string, unknown>;
  } catch {
    payload = { text: payloadText };
  }
  const caseId = String(formData.get("caseId") ?? "");
  if (caseId) {
    payload.caseId = caseId;
  }
  const user = await getCurrentUser();
  await createJob({ type, payload, actor: user ?? undefined });
  revalidatePath("/");
}

function formatDate(value?: string) {
  if (!value) {
    return "";
  }
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export default async function Home() {
  const jobs = await listJobs();
  const cases = await listCases({ activeOnly: true });

  return (
    <main className="page">
      <div className="topbar">
        <div>
          <h1>JMTY Control</h1>
          <p className="subtle">Vercelでジョブを作成し、このMacのワーカーが処理します。</p>
        </div>
        <div className="nav">
          <Link className="button secondary" href="/cases">
            案件管理
          </Link>
          <form action={async () => {
            "use server";
            revalidatePath("/");
          }}>
            <button className="button secondary" type="submit">
              更新
            </button>
          </form>
        </div>
      </div>

      <div className="grid">
        <section className="panel">
          <h2>ジョブ作成</h2>
          <form className="form" action={createJobAction}>
            <div className="field">
              <label htmlFor="type">種別</label>
              <select id="type" name="type" defaultValue="test">
                {JOB_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="payload">Payload JSON</label>
              <textarea
                id="payload"
                name="payload"
                defaultValue={JSON.stringify({ message: "hello from vercel queue" }, null, 2)}
              />
            </div>
            <div className="field">
              <label htmlFor="caseId">案件素材</label>
              <select id="caseId" name="caseId" defaultValue="">
                <option value="">指定なし</option>
                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.kind === "factory" ? "工場" : "在宅"}: {item.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="actions">
              <button className="button" type="submit">
                キューに追加
              </button>
              <span className="subtle">まずは test で疎通確認します。</span>
            </div>
          </form>
        </section>

        <section className="panel">
          <h2>ジョブ一覧</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>状態</th>
                  <th>種別</th>
                  <th>ID</th>
                  <th>Worker</th>
                  <th>作成</th>
                  <th>結果</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>
                      <span className={`badge ${job.status}`}>{job.status}</span>
                    </td>
                    <td>{job.type}</td>
                    <td>
                      <code>{job.id}</code>
                    </td>
                    <td>{job.workerId ?? ""}</td>
                    <td>{formatDate(job.createdAt)}</td>
                    <td>
                      <pre>
                        {JSON.stringify(
                          {
                            payload: job.payload,
                            result: job.result,
                            error: job.error,
                            logs: job.logs.slice(-4),
                          },
                          null,
                          2,
                        )}
                      </pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {jobs.length === 0 ? <div className="empty">ジョブはまだありません。</div> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
