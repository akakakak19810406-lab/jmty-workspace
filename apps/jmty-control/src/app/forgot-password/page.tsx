// JMTY GUI のパスワード再設定依頼画面です。
// 登録メールアドレスへ再設定リンクを送るための
// トークンを作成します。
import Link from "next/link";
import { createPasswordReset } from "@/lib/auth";
import { sendPasswordResetEmail } from "@/lib/email";

async function forgotPasswordAction(formData: FormData) {
  "use server";
  const email = String(formData.get("email") ?? "");
  const reset = await createPasswordReset(email);
  if (reset) {
    const baseUrl = process.env.JMTY_CONTROL_PUBLIC_URL ?? "http://localhost:3000";
    await sendPasswordResetEmail({
      to: reset.user.email,
      resetUrl: `${baseUrl}/reset-password?token=${reset.token}`,
    });
  }
}

export default function ForgotPasswordPage() {
  return (
    <main className="auth-page">
      <section className="auth-panel">
        <h1>パスワード再設定</h1>
        <p className="subtle">登録メールアドレスに再設定リンクを送信します。</p>
        <form className="form" action={forgotPasswordAction}>
          <div className="field">
            <label htmlFor="email">メールアドレス</label>
            <input id="email" name="email" type="email" autoComplete="email" required />
          </div>
          <button className="button" type="submit">
            再設定メールを送る
          </button>
        </form>
        <div className="auth-links">
          <Link href="/login">ログインへ戻る</Link>
        </div>
      </section>
    </main>
  );
}
