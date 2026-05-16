"use client";

import { useAdvisorMode } from "./useAdvisorMode";
import { UserCog, Wrench } from "lucide-react";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

export function ModeBadge() {
  const { mode } = useAdvisorMode();
  const config = mode === "operator"
    ? {
        Icon: UserCog,
        label: "Operator",
        bgClass: "bg-blue-500/15 text-blue-300 border-blue-500/30",
        tooltip: "Tryb operatora — uproszczony interfejs dla codziennej pracy",
      }
    : {
        Icon: Wrench,
        label: "Techniczny",
        bgClass: "bg-amber-500/15 text-amber-300 border-amber-500/30",
        tooltip: "Tryb techniczny — pełen dostęp dla deweloperów",
      };

  return (
    <Tooltip>
      <TooltipTrigger>
        <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-all duration-300 cursor-default ${config.bgClass}`}>
          <config.Icon className="size-3.5" />
          <span>{config.label}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent side="bottom">{config.tooltip}</TooltipContent>
    </Tooltip>
  );
}
