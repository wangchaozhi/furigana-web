import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Furigana Studio",
  description: "Japanese Kanji furigana annotation and native Word Ruby export",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
