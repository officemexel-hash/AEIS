import HeroSection from "@/components/marketing/HeroSection";
import WhatIsAEISSection from "@/components/marketing/WhatIsAEISSection";
import TransformationFlow from "@/components/marketing/TransformationFlow";
import CapabilityGrid from "@/components/marketing/CapabilityGrid";
import ArchitectureSection from "@/components/marketing/ArchitectureSection";
import GovernanceSection from "@/components/marketing/GovernanceSection";
import UseCasesSection from "@/components/marketing/UseCasesSection";
import CTASection from "@/components/marketing/CTASection";
import { HelpTip } from "@/components/common/HelpTip";

export default function LandingPage() {
  return (
    <>
      <div className="fixed right-4 top-20 z-40">
        <HelpTip
          text="Strona startowa prowadzi do konsoli AEIS. Właściwe sterowanie projektem, Human Gate, Księga i testy są dostępne po wejściu do dashboardu."
          side="left"
        />
      </div>
      <HeroSection />

      {/* Divider */}
      <div
        className="h-px mx-auto max-w-7xl"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(47, 107, 255, 0.15), transparent)",
        }}
      />

      <WhatIsAEISSection />

      <div
        className="h-px mx-auto max-w-7xl"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.1), transparent)",
        }}
      />

      <TransformationFlow />

      <div
        className="h-px mx-auto max-w-7xl"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(47, 107, 255, 0.15), transparent)",
        }}
      />

      <CapabilityGrid />

      <div
        className="h-px mx-auto max-w-7xl"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.1), transparent)",
        }}
      />

      <ArchitectureSection />

      <div
        className="h-px mx-auto max-w-7xl"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(245, 158, 11, 0.15), transparent)",
        }}
      />

      <GovernanceSection />

      <div
        className="h-px mx-auto max-w-7xl"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.1), transparent)",
        }}
      />

      <UseCasesSection />

      <div
        className="h-px mx-auto max-w-7xl"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(47, 107, 255, 0.15), transparent)",
        }}
      />

      <CTASection />
    </>
  );
}
