// JMTY Control の案件管理画面です。
// 在宅・工場の案件素材を後から追加し、
// 投稿作成ジョブで参照できる一覧として管理します。
import Link from "next/link";
import { revalidatePath } from "next/cache";
import { createCaseFromForm, listCases, setCaseActive } from "@/lib/cases";
import { requireUser } from "@/lib/auth";

async function createCaseAction(formData: FormData) {
  "use server";
  const user = await requireUser();
  await createCaseFromForm(formData, user);
  revalidatePath("/cases");
  revalidatePath("/");
}

async function toggleCaseAction(formData: FormData) {
  "use server";
  const user = await requireUser();
  await setCaseActive({
    id: String(formData.get("id") ?? ""),
    active: String(formData.get("active") ?? "") === "true",
    actor: user,
  });
  revalidatePath("/cases");
  revalidatePath("/");
}

function kindLabel(kind: string) {
  return kind === "factory" ? "工場" : "在宅";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default async function CasesPage() {
  await requireUser();
  const cases = await listCases();

  return (
    <main className="page">
      <div className="topbar">
        <div>
          <h1>案件管理</h1>
          <p className="subtle">在宅・工場の案件素材を追加し、投稿作成ジョブへ渡せる状態にします。</p>
        </div>
        <nav className="nav">
          <Link className="button secondary" href="/">
            ジョブ管理
          </Link>
        </nav>
      </div>

      <div className="grid">
        <section className="panel">
          <h2>新規案件</h2>
          <form className="form" action={createCaseAction}>
            <div className="field">
              <label htmlFor="kind">種別</label>
              <select id="kind" name="kind" defaultValue="remote">
                <option value="remote">在宅</option>
                <option value="factory">工場</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="title">案件名</label>
              <input id="title" name="title" placeholder="例: 在宅AIライター / 自動車部品の検査スタッフ" required />
            </div>
            <div className="field">
              <label htmlFor="salary">月収・報酬目安</label>
              <input id="salary" name="salary" placeholder="例: 月収35万円目安 / 月収40万円可" />
            </div>
            <div className="field">
              <label htmlFor="workStyle">働き方・勤務時間</label>
              <input id="workStyle" name="workStyle" placeholder="例: 完全在宅 / 2交替 / 土日休み" />
            </div>
            <div className="field">
              <label htmlFor="benefits">訴求ポイント</label>
              <input id="benefits" name="benefits" placeholder="例: 未経験OK、寮費無料、日払いOK" />
            </div>
            <div className="field">
              <label htmlFor="body">案件素材本文</label>
              <textarea id="body" name="body" placeholder="投稿文作成時に使いたい案件内容を入れてください。" />
            </div>
            <div className="field">
              <label htmlFor="notes">内部メモ</label>
              <textarea id="notes" name="notes" placeholder="生成時の注意、NG表現、差し替えルールなど" />
            </div>
            <button className="button" type="submit">
              案件を追加
            </button>
          </form>
        </section>

        <section className="panel">
          <h2>案件素材一覧</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>状態</th>
                  <th>種別</th>
                  <th>案件名</th>
                  <th>条件</th>
                  <th>作成</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <span className={`badge ${item.active ? "done" : "cancelled"}`}>
                        {item.active ? "active" : "archived"}
                      </span>
                    </td>
                    <td>{kindLabel(item.kind)}</td>
                    <td>
                      <strong>{item.title}</strong>
                      <pre className="compact-pre">{item.body || item.notes || ""}</pre>
                    </td>
                    <td>
                      <div>{item.salary}</div>
                      <div className="subtle">{item.workStyle}</div>
                      <div className="subtle">{item.benefits}</div>
                    </td>
                    <td>{formatDate(item.createdAt)}</td>
                    <td>
                      <form action={toggleCaseAction}>
                        <input type="hidden" name="id" value={item.id} />
                        <input type="hidden" name="active" value={String(!item.active)} />
                        <button className="button secondary" type="submit">
                          {item.active ? "停止" : "有効化"}
                        </button>
                      </form>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {cases.length === 0 ? <div className="empty">案件素材はまだありません。</div> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
