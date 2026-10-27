import type { Metadata } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import { Logo } from "../components/Logo";
import { ButtonLink } from "../components/brand";
import { PostHogProvider } from "./components/PostHogProvider";
import { PostHogPageview } from "./components/PostHogPageview";
import "./globals.css";

// Records change as picks settle, so every page renders per request.
export const dynamic = "force-dynamic";

const barlow = Barlow({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-barlow",
  display: "swap",
});

const barlowCondensed = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-barlow-condensed",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PickReceipts",
  description:
    "Every pick. Every loss. On the record. PickReceipts tracks sports betting creators' publicly posted picks, settles them against final scores, and publishes their records.",
  // Tab icons come from app/favicon.ico, app/icon.png and app/apple-icon.png.
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const year = new Date().getFullYear();

  return (
    <html lang="en" className={`${barlow.variable} ${barlowCondensed.variable}`}>
      <body className="min-h-screen bg-ground font-sans text-fg">
        <PostHogProvider>
          <PostHogPageview />
          <header className="sticky top-0 z-20 border-b border-line bg-ground/90 backdrop-blur-md">
            <div className="mx-auto flex h-[64px] max-w-6xl items-center justify-between gap-4 px-4 sm:h-[72px] sm:px-6">
              <Logo height={38} className="sm:!h-[44px]" />
              <ButtonLink href="/submit" variant="primary" className="!px-3.5 !py-2 text-[14px] sm:!px-[18px] sm:!py-[10px] sm:text-[15px]">
                Submit a pick
              </ButtonLink>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-4 pt-8 sm:px-6 sm:pt-12">{children}</main>
          <footer className="mt-20 border-t border-line">
            <div className="mx-auto max-w-6xl px-4 pb-12 pt-6 text-[13px] leading-relaxed text-fg-3 sm:px-6">
              <p>
                Picks sourced from public social media posts. Picks settle within about 15 minutes
                after the game ends.
              </p>
              <p>For entertainment and transparency purposes only. Not financial advice.</p>
              <p className="mt-3 font-display text-[13px] font-semibold uppercase tracking-[0.08em]">
                PickReceipts · {year}
              </p>
            </div>
          </footer>
        </PostHogProvider>
        <Analytics />
      </body>
    </html>
  );
}
