"use client";

import { motion } from "framer-motion";
import { InteractiveCursorGlow } from "@/components/ui/cursor-glow";
import { NavBar } from "@/components/sections/NavBar";
import { HeroSection } from "@/components/sections/HeroSection";
import { StatsSection } from "@/components/sections/StatsSection";
import { FeaturesSection } from "@/components/sections/FeaturesSection";
import { HowItWorksSection } from "@/components/sections/HowItWorksSection";
import { ArchitectureSection } from "@/components/sections/ArchitectureSection";
import { SocialProofSection } from "@/components/sections/SocialProofSection";
import { DemoSection } from "@/components/sections/DemoSection";
import { CTASection } from "@/components/sections/CTASection";
import { FooterSection } from "@/components/sections/FooterSection";

export default function Home() {
  return (
    <main>
      <InteractiveCursorGlow />

      <NavBar />

      <div className="relative z-10 agente agente-col items-center">
        <HeroSection />
        <StatsSection />
        <DemoSection />
        <FeaturesSection />
        <HowItWorksSection />
        <ArchitectureSection />
        <SocialProofSection />
        <CTASection />
        <FooterSection />
      </div>
    </main>
  );
}
