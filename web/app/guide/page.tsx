"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, ClipboardList, ShieldCheck, Activity } from "lucide-react";

const STEPS = [
  { title: "1) Setup", body: "DB/Redis 연결 후 Preflight 체크를 통과합니다.", href: "/setup" },
  { title: "2) Ingest", body: "문서/파트너 API로 데이터를 입력합니다.", href: "/dataforge" },
  { title: "3) Review", body: "HITL 승인으로 품질 게이트를 통과시킵니다.", href: "/dataforge" },
  { title: "4) Train", body: "자동 학습 또는 배치 학습을 실행합니다.", href: "/mlops" },
  { title: "5) Serve", body: "운영 모델을 선택하고 RAG/LLM을 서빙합니다.", href: "/mlops" },
  { title: "6) Monitor", body: "로그/감사/지표를 확인합니다.", href: "/logs" },
];

const ROLES = [
  { title: "Admin", body: "설정/권한/키 발급/정책 관리", href: "/settings" },
  { title: "Reviewer", body: "증거 검증과 승인, 품질 보강", href: "/dataforge" },
  { title: "Analyst", body: "RAG 질의와 리포트 생성", href: "/console" },
];

const COMMON = [
  { title: "Partner SDK 연결", body: "외부 데이터 소스 등록과 인입 테스트", href: "/sdkui" },
  { title: "Lakehouse 운영", body: "Delta/Spark/MLflow 상태 확인", href: "/lakehouse" },
  { title: "협업/공유", body: "팀/공간/전송 관리", href: "/collab" },
  { title: "감사 로그", body: "모든 승인/전송/학습 기록 확인", href: "/logs" },
];

export default function GuidePage() {
  return (
    <div className="min-h-screen bg-[#f7f7f4] text-slate-900">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-white">
              <ClipboardList className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold">Preciso Usage Guide</div>
              <div className="text-xs text-slate-500">Non-technical friendly onboarding</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/ops-console"
              className="rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300"
            >
              Ops Console
            </Link>
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
            >
              Dashboard
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-10 md:grid-cols-[1.2fr_0.8fr]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">
              30분 온보딩 가이드
            </div>
            <h1 className="mt-6 text-4xl font-semibold leading-tight md:text-5xl">
              Preciso를
              <span className="block text-slate-700">누구나 쉽게 운영하는 방법</span>
            </h1>
            <p className="mt-4 text-base text-slate-600">
              비개발자도 바로 사용할 수 있도록 단계별 흐름과 버튼을 단순화했습니다.
              아래 순서대로 진행하면 모든 파이프라인을 완성할 수 있습니다.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              Success Criteria
            </div>
            <div className="mt-3 text-sm text-slate-600">
              1) 데이터 인입 성공<br />
              2) 승인 1회 완료<br />
              3) 모델 서빙까지 정상 작동
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="mb-8 text-xs uppercase tracking-[0.3em] text-slate-500">Quick Start</div>
        <div className="grid gap-4 md:grid-cols-3">
          {STEPS.map((step) => (
            <Link
              key={step.title}
              href={step.href}
              className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
            >
              <div className="text-sm font-semibold text-slate-900">{step.title}</div>
              <div className="mt-2 text-sm text-slate-600">{step.body}</div>
              <div className="mt-6 inline-flex items-center gap-2 text-xs font-semibold text-slate-900">
                Open
                <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="mb-8 text-xs uppercase tracking-[0.3em] text-slate-500">Roles</div>
        <div className="grid gap-4 md:grid-cols-3">
          {ROLES.map((role) => (
            <Link
              key={role.title}
              href={role.href}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-slate-700" />
                <div className="text-sm font-semibold text-slate-900">{role.title}</div>
              </div>
              <div className="mt-2 text-sm text-slate-600">{role.body}</div>
            </Link>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-20">
        <div className="mb-8 text-xs uppercase tracking-[0.3em] text-slate-500">Common Actions</div>
        <div className="grid gap-4 md:grid-cols-2">
          {COMMON.map((item) => (
            <Link
              key={item.title}
              href={item.href}
              className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div>
                <div className="text-sm font-semibold text-slate-900">{item.title}</div>
                <div className="mt-2 text-sm text-slate-600">{item.body}</div>
              </div>
              <Activity className="h-5 w-5 text-slate-400" />
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
