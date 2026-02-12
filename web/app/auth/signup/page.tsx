"use client";

import Link from "next/link";
import { useActionState } from "react";
import { signupAction } from "../actions";

export default function SignupPage() {
  const [state, formAction] = useActionState(signupAction, null);

  return (
    <main className="min-h-screen bg-[#f7f7f4] text-slate-900">
      <div className="mx-auto flex max-w-xl flex-col gap-6 px-6 py-16">
        <div>
          <div className="text-xs uppercase tracking-[0.3em] text-slate-500">Create Account</div>
          <h1 className="mt-3 text-3xl font-semibold">Preciso 회원가입</h1>
          <p className="mt-2 text-sm text-slate-600">
            비개발자도 바로 시작할 수 있도록 가입 후 Usage Guide를 제공합니다.
          </p>
        </div>

        <form action={formAction} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="space-y-4">
            <div>
              <label className="text-xs text-slate-500">이름</label>
              <input
                name="name"
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="홍길동"
              />
            </div>
            <div>
              <label className="text-xs text-slate-500">이메일</label>
              <input
                name="email"
                type="email"
                required
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="you@company.com"
              />
            </div>
            <div>
              <label className="text-xs text-slate-500">비밀번호</label>
              <input
                name="password"
                type="password"
                required
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="8자 이상"
              />
            </div>
          </div>

          {state?.message && (
            <div className={`mt-4 text-sm ${state.ok ? "text-emerald-600" : "text-rose-600"}`}>
              {state.message}
            </div>
          )}

          <button
            type="submit"
            className="mt-6 inline-flex w-full items-center justify-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
          >
            가입하기
          </button>
        </form>

        <div className="text-sm text-slate-600">
          이미 계정이 있나요?{" "}
          <Link href="/auth/login" className="font-semibold text-slate-900">
            로그인
          </Link>
        </div>
      </div>
    </main>
  );
}
