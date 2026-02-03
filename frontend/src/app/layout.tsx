import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";

// Configure fonts as requested
const inter = Inter({ 
  subsets: ["latin"], 
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({ 
  subsets: ["latin"], 
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Preciso | Sovereign Financial Intelligence",
  description: "Advanced B2B Financial Data Refinement and Decision Intelligence Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans bg-[#1a1c1e] text-foreground antialiased bp5-dark">
        <div className="flex h-screen overflow-hidden bg-[#1a1c1e]">
          <Sidebar />
          <div className="flex-1 flex flex-col overflow-hidden bg-[#1a1c1e]">
            <Header />
            <main className="flex-1 overflow-y-auto bg-[#1a1c1e] p-0">
              {children}
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
