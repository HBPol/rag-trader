import type { ReactNode } from "react";

import { AppProviders } from "@/app/providers";

export default function DashboardLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return <AppProviders>{children}</AppProviders>;
}
