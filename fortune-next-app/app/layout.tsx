import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "四柱推命 鑑定補助アプリ",
  description: "四柱推命の鑑定結果を確認するための本番向けUI移行版",
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
