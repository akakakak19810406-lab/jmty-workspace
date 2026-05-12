// JMTY control の全画面レイアウトです。
// 管理画面に共通のHTML骨格とグローバルCSSを読み込み、
// Vercel公開時のメタデータを定義します。
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "JMTY Control",
  description: "JMTY job control panel for a Mac worker",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
