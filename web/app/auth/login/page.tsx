"use client";

import { useEffect, useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<Record<string, boolean> | null>(null);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetch("/api/auth/health", { cache: "no-store" });
        if (res.ok) setHealth(await res.json());
      } catch {
        // ignore
      }
    };
    run();
  }, []);

  const handleCredentials = async () => {
    setError(null);
    setLoading(true);
    const res = await signIn("credentials", {
      redirect: false,
      email,
      password,
      callbackUrl: "/ops-console",
    });
    setLoading(false);
    if (res?.error) {
      setError("이메일 또는 비밀번호가 올바르지 않습니다.");
    } else if (res?.url) {
      window.location.href = res.url;
    }
  };

  return (
    <main className="min-h-screen bg-[#f7f7f4] text-slate-900">
      <div className="mx-auto flex max-w-xl flex-col gap-6 px-6 py-16">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Sign In</div>
          <h1 className="mt-3 text-3xl font-semibold">Preciso 로그인</h1>
          <p className="mt-2 text-sm text-slate-600">
            Google, GitHub 또는 이메일로 로그인하세요.
          </p>
        </div>

        <div className="grid gap-3">
          <button
            onClick={() => signIn("google", { callbackUrl: "/ops-console" })}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            Google로 로그인
          </button>
          <button
            onClick={() => signIn("github", { callbackUrl: "/ops-console" })}
            className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-300"
          >
            GitHub로 로그인
          </button>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="text-xs text-slate-500">Email Login</div>
          <div className="mt-4 space-y-3">
            <input
              type="email"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <input
              type="password"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="비밀번호"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && <div className="text-sm text-rose-600">{error}</div>}
            <button
              onClick={handleCredentials}
              disabled={loading}
              className="inline-flex w-full items-center justify-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
            >
              {loading ? "로그인 중..." : "이메일로 로그인"}
            </button>
          </div>
        </div>

        <div className="text-sm text-slate-600">
          계정이 없나요?{" "}
          <Link href="/auth/signup" className="font-semibold text-slate-900">
            회원가입
          </Link>
        </div>

        {health && (
          <div className="rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600">
            <div className="text-xs font-semibold text-slate-500">Auth/Email Status</div>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <div>Google: {health.google_configured ? "ready" : "missing"}</div>
              <div>GitHub: {health.github_configured ? "ready" : "missing"}</div>
              <div>Resend: {health.resend_configured ? "ready" : "missing"}</div>
              <div>Welcome From: {health.welcome_from_set ? "ready" : "missing"}</div>
              <div>Database: {health.database_url ? "ready" : "missing"}</div>
              <div>NextAuth Secret: {health.nextauth_secret ? "ready" : "missing"}</div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
