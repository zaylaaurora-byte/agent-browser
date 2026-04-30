import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/navbar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Agent Browser — AI-Powered Browser Automation",
  description: "Autonomous browser agent powered by AI with stealth anti-detection",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased bg-[#050508] text-zinc-100`}>
        <Navbar />
        {children}
      </body>
    </html>
  );
}
