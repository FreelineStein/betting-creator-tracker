import type { Metadata } from "next";
import { Barlow, Barlow_Condensed, IBM_Plex_Mono } from "next/font/google";
import { Logo } from "../components/Logo";
import "./globals.css";

const barlow = Barlow({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-barlow",
  display: "swap",
});

const barlowCondensed = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["700", "900"],
  variable: "--font-barlow-condensed",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
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
      className={`${barlow.variable} ${barlowCondensed.variable} ${plexMono.variable}`}
    >
      <body className="bg-pitch text-white min-h-screen font-sans">
        <nav className="border-b border-ink-800 bg-pitch">
          <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
            <Logo height={48} icon={false} />
            <span className="font-mono text-[10px] uppercase tracking-label text-ink-400 hidden sm:inline">
              Real records · No excuses
            </span>
          </div>
        </nav>
        <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
