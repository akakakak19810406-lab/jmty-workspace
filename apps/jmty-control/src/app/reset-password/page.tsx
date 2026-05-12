// JMTY GUI のパスワード再設定画面です。
// メールで受け取ったトークンを使い、
// 新しいパスワードのハッシュへ更新します。
import { redirect } from "next/navigation";
import { resetPassword } from "@/lib/auth";

async function resetPasswordAction(formData: FormData) {
  "use server";
  await resetPassword(String(formData.get("token") ?? ""), String(formData.get("password") ?? ""));
  redirect("/login");
}

export default function ResetPasswordPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  return (
    <main className="auth-page">
      <section className="auth-panel">
        <h1>新しいパスワード</h1>
        <form className="form" action={resetPasswordAction}>
          <TokenInput searchParams={searchParams} />
          <div className="field">
            <label htmlFor="password">新しいパスワード</label>
            <input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required />
          </div>
          <button className="button" type="submit">
            更新
          </button>
        </form>
      </section>
    </main>
  );
}

async function TokenInput({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const params = await searchParams;
  return <input type="hidden" name="token" value={params.token ?? ""} />;
}
