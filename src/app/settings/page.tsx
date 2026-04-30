"use client";

import { SettingsForm } from "@/components/settings-form";
import { motion } from "framer-motion";

export default function SettingsPage() {
  return (
    <div className="min-h-screen bg-[#050508] text-zinc-100 pt-14">
      <SettingsForm />
    </div>
  );
}
