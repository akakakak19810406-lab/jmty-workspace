// JMTY Control のメール送信補助です。
// RESEND_API_KEY がある場合はResendで送信し、
// 未設定の開発環境では送信予定内容を返します。
export async function sendPasswordResetEmail(input: { to: string; resetUrl: string }) {
  const subject = "JMTY GUI パスワード再設定";
  const text = `JMTY GUIのパスワード再設定リンクです。\n\n${input.resetUrl}\n\nこのリンクに心当たりがない場合は破棄してください。`;

  if (!process.env.RESEND_API_KEY || !process.env.RESEND_FROM_EMAIL) {
    return { sent: false, subject, text };
  }

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: process.env.RESEND_FROM_EMAIL,
      to: input.to,
      subject,
      text,
    }),
  });

  if (!response.ok) {
    throw new Error(`メール送信に失敗しました: ${response.status}`);
  }

  return { sent: true, subject, text };
}
