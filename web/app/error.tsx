"use client";

import { useEffect } from "react";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="shell">
      <section className="errorPage card" role="alert">
        <span className="eyebrow">UNEXPECTED ERROR</span>
        <h1>页面遇到了问题</h1>
        <p>你的已保存项目不会受到影响。可以重试；如果仍然失败，请刷新页面。</p>
        <button className="primaryButton" onClick={reset}>重新尝试</button>
      </section>
    </main>
  );
}
