// JMTY GUI の新規登録画面です。
// アカウント名は重複不可、メールアドレスは一意として保存し、
// パスワードはハッシュ化して登録します。
import Link from "next/link";
import { redirect } from "next/navigation";
import { createSession, createUser } from "@/lib/auth";

async function registerAction(formData: FormData) {
  "use server";
  const user = await createUser({
    email: String(formData.get("email") ?? ""),
    accountName: String(formData.get("accountName") ?? ""),
    password: String(formData.get("password") ?? ""),
  });
  await createSession(user);
  redirect("/");
}

export default function RegisterPage() {
  return (
    <main className="auth-page">
      <section className="auth-panel">
        <h1>新規登録</h1>
        <form className="form" action={registerAction}>
          <div className="field">
            <label htmlFor="accountName">アカウント名</label>
            <input id="accountName" name="accountName" autoComplete="username" required />
          </div>
          <div className="field">
            <label htmlFor="email">メールアドレス</label>
            <input id="email" name="email" type="email" autoComplete="email" required />
          </div>
          <div className="field">
            <label htmlFor="password">パスワード</label>
            <input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required />
          </div>
          <button className="button" type="submit">
            登録
          </button>
        </form>
        <div className="auth-links">
          <Link href="/login">ログインへ戻る</Link>
        </div>
      </section>
    </main>
  );
}
