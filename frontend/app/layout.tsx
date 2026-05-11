import type { Metadata } from "next";
import { Manrope, IBM_Plex_Mono } from "next/font/google";
import Link from "next/link";
import { Analytics } from "@vercel/analytics/react";
import { Logo } from "../components/Logo";
import { PostHogProvider } from "./components/PostHogProvider";
import { PostHogPageview } from "./components/PostHogPageview";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-manrope",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PickReceipts",
  description:
    "Every pick. Every loss. On the record. PickReceipts tracks sports betting influencers across their public channels and holds them accountable with verified win/loss records.",
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
  return (
    <html
      lang="en"
      className={`${manrope.variable} ${plexMono.variable}`}
    >
      <body className="bg-paper text-ink min-h-screen font-sans">
        <PostHogProvider>
          <PostHogPageview />
          <nav className="border-b border-rule bg-paper">
            <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
              <Logo height={40} />
              <div className="flex items-center gap-5">
                <Link
                  href="/submit"
                  className="inline-flex items-center rounded-full border border-amber-deep/40 bg-amber-dim px-4 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-label-x text-amber-deep hover:bg-amber-deep hover:text-paper hover:border-amber-deep transition-colors"
                >
                  Submit a pick →
                </Link>
              </div>
            </div>
          </nav>
          <main className="max-w-5xl mx-auto px-6 py-10">{children}</main>
        </PostHogProvider>
        <Analytics />
      </body>
    </html>
  );
}
