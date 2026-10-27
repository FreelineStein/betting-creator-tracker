import type { Metadata } from "next";
import { Oswald, Archivo_Narrow } from "next/font/google";
import Link from "next/link";
import { Analytics } from "@vercel/analytics/react";
import { Logo } from "../components/Logo";
import { PostHogProvider } from "./components/PostHogProvider";
import { PostHogPageview } from "./components/PostHogPageview";
import { formatDatelineET } from "./lib/picks";
import "./globals.css";

// The masthead carries today's date, so every page renders per request.
export const dynamic = "force-dynamic";

const oswald = Oswald({
  subsets: ["latin"],
  weight: ["500", "700"],
  variable: "--font-oswald",
  display: "swap",
});

const archivo = Archivo_Narrow({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-archivo",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PickReceipts",
  description:
    "Every pick. Every loss. On the record. PickReceipts tracks sports betting creators' publicly posted picks, settles them against final scores, and publishes the standings.",
  icons: [
    {
      rel: "icon",
      type: "image/png",
      sizes: "32x32",
      url: "/favicon.png",
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const dateline = formatDatelineET();
  const year = new Date().getFullYear();

  return (
    <html lang="en" className={`${oswald.variable} ${archivo.variable}`}>
      <body className="min-h-screen bg-news font-sans text-ink">
        <PostHogProvider>
          <PostHogPageview />
          <header className="border-b-2 border-ink">
            <div className="mx-auto max-w-6xl px-4 sm:px-6">
              <div className="flex items-end justify-between gap-4 pb-3 pt-5">
                <Logo size={32} />
                <Link
                  href="/submit"
                  className="inline-flex items-center border-2 border-ink px-3 py-[7px] font-display text-[13px] font-medium uppercase leading-none tracking-[0.07em] text-ink transition-colors duration-120 hover:bg-ink hover:text-news"
                >
                  Submit a pick
                </Link>
              </div>
              <div className="flex items-center justify-between gap-4 border-t border-ink py-[6px] text-[11px] uppercase tracking-[0.08em] text-ink-2">
                <span className="text-press">{dateline}</span>
                <span className="sm:hidden">All times Eastern</span>
                <span className="hidden sm:inline">Standings and box scores · All times Eastern</span>
              </div>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-4 pt-8 sm:px-6 sm:pt-10">{children}</main>
          <footer className="mx-auto mt-20 max-w-6xl px-4 pb-12 sm:px-6">
            <div className="border-t-2 border-ink pt-3 text-[12px] leading-relaxed text-ink-3">
              <p>
                Picks sourced from public social media posts. Picks settle within about 15 minutes
                after the game ends.
              </p>
              <p>For entertainment and transparency purposes only. Not financial advice.</p>
              <p className="mt-2 uppercase tracking-[0.08em]">PickReceipts · {year}</p>
            </div>
          </footer>
        </PostHogProvider>
        <Analytics />
      </body>
    </html>
  );
}
