// JMTY GUI のログイン画面です。
// メールアドレスとパスワードを検証し、
// 成功したユーザーだけアプリ本体へ入れます。
import Link from "next/link";
import { redirect } from "next/navigation";
import { authenticateUser, createSession } from "@/lib/auth";

async function loginAction(formData: FormData) {
  "use server";
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const user = await authenticateUser(email, password);
  if (!user) {
    redirect("/register?reason=not_found");
  }
  await createSession(user);
  redirect("/");
}

export default function LoginPage() {
  return (
    <main className="auth-page">
      <section className="auth-panel">
        <h1>JMTY GUI</h1>
        <p className="subtle">メールアドレスとパスワードでログインしてください。</p>
        <form className="form" action={loginAction}>
          <div className="field">
            <label htmlFor="email">メールアドレス</label>
            <input id="email" name="email" type="email" autoComplete="email" required />
          </div>
          <div className="field">
            <label htmlFor="password">パスワード</label>
            <input id="password" name="password" type="password" autoComplete="current-password" required />
          </div>
          <button className="button" type="submit">
            ログイン
          </button>
        </form>
        <div className="auth-links">
          <Link href="/register">新規登録</Link>
          <Link href="/forgot-password">パスワードを忘れた</Link>
        </div>
      </section>
    </main>
  );
}
