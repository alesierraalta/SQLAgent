import type { Metadata } from "next";
import { Toaster } from "sonner";

import "./globals.css";

import { Navbar } from "@/components/navbar";

export const metadata: Metadata = {
  title: "LLM DW",
  description: "WebApp de consultas (FastAPI + Next.js)"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body>
        <div className="min-h-screen">
          <Navbar />
          <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
        </div>
        <Toaster theme="dark" position="bottom-right" />
      </body>
    </html>
  );
}

