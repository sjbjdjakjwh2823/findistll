"use client";

import React from "react";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import { useAuthStore } from "@/store/useAuthStore";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { SparklesCore } from "@/components/ui/sparkles";

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isLoginPage = pathname === "/login";

  useEffect(() => {
    if (!isAuthenticated && !isLoginPage) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoginPage, router]);

  if (isLoginPage) {
    return <>{children}</>;
  }

  if (!isAuthenticated) {
    return null; // or a spinner
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#1a1c1e] relative">
      <div className="absolute inset-0 z-0 pointer-events-none">
        <SparklesCore
          id="tsparticlesfullpage"
          background="transparent"
          minSize={0.6}
          maxSize={1.4}
          particleDensity={30}
          className="w-full h-full"
          particleColor="#2B95D6"
        />
      </div>
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden bg-[#1a1c1e] relative z-10">
        <Header />
        <main className="flex-1 overflow-y-auto bg-[#1a1c1e] p-0">
          {children}
        </main>
      </div>
    </div>
  );
}
