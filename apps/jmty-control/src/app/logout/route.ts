// JMTY GUI のログアウトRouteです。
// 現在のセッションCookieを削除し、ログイン画面へ戻します。
import { redirect } from "next/navigation";
import { logoutCurrentUser } from "@/lib/auth";

export async function GET() {
  await logoutCurrentUser();
  redirect("/login");
}
