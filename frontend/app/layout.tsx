import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Betting Creator Tracker",
  description: "Transparent W/L records for sports betting creators.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <nav className="border-b border-gray-800 px-6 py-4">
          <div className="max-w-5xl mx-auto flex items-center gap-2">
            <span className="text-green-400 font-bold text-lg">📊 PickTrack</span>
            <span className="text-gray-500 text-sm ml-2">Betting Creator Tracker</span>
          </div>
        </nav>
        <main className="max-w-5xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
