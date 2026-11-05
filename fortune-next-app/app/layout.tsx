import type { Metadata } from "next";
import "./globals.css";
import { FortuneStateProvider } from "./fortune-state";
import { AuthProvider } from "./auth";
import { TeacherThemeProvider } from "./teacher-theme";
import { ReadingModeProvider } from "./reading-mode";
import { readingBootstrap } from "./reading-bootstrap";
import { selectedTheme, themeStyle } from "./theme-tokens";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "四柱推命 鑑定補助アプリ",
  description: "四柱推命の鑑定結果を確認するための本番向けUI移行版",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const bootstrap = await readingBootstrap();
  const theme = bootstrap ? selectedTheme(bootstrap.branding, bootstrap.default_theme) : null;
  return (
    <html lang="ja" data-reading-only={bootstrap ? "true" : undefined} data-teacher-theme={theme?.key} style={theme ? themeStyle(theme) : undefined}>
      <body><ReadingModeProvider bootstrap={bootstrap}><FortuneStateProvider><AuthProvider initialUser={bootstrap?.user}><TeacherThemeProvider>{children}</TeacherThemeProvider></AuthProvider></FortuneStateProvider></ReadingModeProvider></body>
    </html>
  );
}
