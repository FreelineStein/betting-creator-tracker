import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pick Receipts - Betting Creator Leaderboard",
  description: "Transparent W/L records for sports betting creators. No cherrypicking.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <nav className="border-b border-gray-800 px-6 py-4">
          <div className="max-w-5xl mx-auto flex items-center gap-2">
            <span className="text-blue-400 font-bold text-lg">🧾 Pick Receipts</span>
          </div>
        </nav>
        <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
