import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { cn } from "@/lib/utils";
import { AppProviders } from "./providers";

export const metadata: Metadata = {
  title: "RAGTrader",
  description: "Retrieve. Reason. Trade.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={cn(
          "min-h-screen bg-background font-sans antialiased text-foreground",
        )}
      >
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
