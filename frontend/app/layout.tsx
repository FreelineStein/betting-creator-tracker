import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Betting Creator Tracker",
  description: "Track sports betting creators — transparent W/L records, tail/fade signals.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
