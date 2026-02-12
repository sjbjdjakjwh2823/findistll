import type { Metadata } from "next";
import { Space_Grotesk, Fraunces, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-sans",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-display",
  subsets: ["latin"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-mono",
  weight: ["400", "500"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Preciso | Financial-Grade AI Intelligence",
  description:
    "Preciso builds financial-grade AI workflows for institutional analysis, auditability, and decision support.",
  openGraph: {
    title: "Preciso | Financial-Grade AI Intelligence",
    description:
      "Financial-grade AI workflows for institutional analysis, auditability, and decision support.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Preciso | Financial-Grade AI Intelligence",
    description:
      "Financial-grade AI workflows for institutional analysis, auditability, and decision support.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${spaceGrotesk.variable} ${fraunces.variable} ${plexMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
