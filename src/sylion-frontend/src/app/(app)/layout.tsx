"use client";

import { usePathname } from "next/navigation";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { TopCommandBar } from "@/components/layout/TopCommandBar";
import { SidebarProvider, useSidebar } from "@/components/layout/SidebarContext";
import { AdvisorBubble } from "@/components/advisor/AdvisorBubble";
import { AuthFetchBridge } from "@/components/auth/AuthFetchBridge";
import { FirstRunBanner } from "@/components/onboarding/FirstRunBanner";
import { useAdvisorMode } from "@/components/layout/useAdvisorMode";
import { BackendOfflineGuard } from "@/components/system/BackendOfflineGuard";
import { cn } from "@/lib/utils";

function AppShell({ children }: { children: React.ReactNode }) {
  const { collapsed } = useSidebar();
  const pathname = usePathname();
  const { mode } = useAdvisorMode();
  const sidebarWidth = collapsed ? 64 : 256;

  return (
    <div
      className={cn(
        "min-h-screen transition-colors duration-300",
        mode === "operator" ? "operator-mode" : "technical-mode"
      )}
      style={{ backgroundColor: "#050816" }}
    >
      <AppSidebar />
      <TopCommandBar />
      <main
        className="min-h-screen pt-14 transition-all duration-250 ease-[cubic-bezier(0.4,0,0.2,1)]"
        style={{ marginLeft: sidebarWidth }}
      >
        <FirstRunBanner pathname={pathname} />
        <div className="p-6">{children}</div>
      </main>
      <AdvisorBubble />
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <BackendOfflineGuard>
      <AuthFetchBridge />
      <SidebarProvider>
        <AppShell>{children}</AppShell>
      </SidebarProvider>
    </BackendOfflineGuard>
  );
}
