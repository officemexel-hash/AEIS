"use client";

/**
 * SYLION AEIS v2 — W16 G2 widget: TabsWidget.
 *
 * Wrapper na shadcn/Tabs sterowany manifestem (operator deklaratywnie podaje
 * tablicę tabów). Domyślnie horizontal; vertical = lewy sidebar 180px + content.
 */

import { useEffect, useState, type ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { HelpTip } from "@/components/common/HelpTip";
import { cn } from "@/lib/utils";

export interface TabDef {
  id: string;
  label_pl: string;
  label_en?: string;
  icon?: ReactNode;
  content: ReactNode;
  disabled?: boolean;
  badge?: string | number;
}

export interface TabsWidgetProps {
  tabs: TabDef[];
  defaultTabId?: string;
  onChange?: (tabId: string) => void;
  variant?: "horizontal" | "vertical";
  helpText?: string;
}

export function TabsWidget({
  tabs,
  defaultTabId,
  onChange,
  variant = "horizontal",
  helpText,
}: TabsWidgetProps) {
  const initial =
    defaultTabId && tabs.some((t) => t.id === defaultTabId)
      ? defaultTabId
      : tabs.find((t) => !t.disabled)?.id ?? tabs[0]?.id ?? "";

  const [active, setActive] = useState<string>(initial);

  useEffect(() => {
    if (defaultTabId && defaultTabId !== active) {
      if (tabs.some((t) => t.id === defaultTabId)) setActive(defaultTabId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultTabId]);

  function handleChange(next: string | number): void {
    const id = String(next);
    setActive(id);
    onChange?.(id);
  }

  if (tabs.length === 0) {
    return (
      <div className="px-3 py-4 text-xs text-muted-foreground">Brak zakładek</div>
    );
  }

  if (variant === "vertical") {
    return (
      <Tabs
        value={active}
        onValueChange={handleChange}
        orientation="vertical"
        className="flex !flex-row gap-3"
        data-slot="tabs-widget-vertical"
      >
        <TabsList className="h-auto w-[180px] shrink-0 flex-col bg-muted/30 p-1">
          {helpText && (
            <div className="self-end px-1 pb-1">
              <HelpTip text={helpText} />
            </div>
          )}
          {tabs.map((t) => (
            <TabsTrigger
              key={t.id}
              value={t.id}
              disabled={t.disabled}
              className="w-full justify-start gap-1.5 text-xs"
            >
              {t.icon}
              <span className="truncate">{t.label_pl}</span>
              {t.badge !== undefined && (
                <Badge variant="secondary" className="ml-auto h-4 text-[9px]">
                  {t.badge}
                </Badge>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
        <div className="flex-1 min-w-0">
          {tabs.map((t) => (
            <TabsContent key={t.id} value={t.id}>
              {t.content}
            </TabsContent>
          ))}
        </div>
      </Tabs>
    );
  }

  return (
    <Tabs
      value={active}
      onValueChange={handleChange}
      data-slot="tabs-widget-horizontal"
    >
      <TabsList variant="line" className={cn("h-auto flex-wrap")}>
        {helpText && (
          <span className="px-1">
            <HelpTip text={helpText} />
          </span>
        )}
        {tabs.map((t) => (
          <TabsTrigger
            key={t.id}
            value={t.id}
            disabled={t.disabled}
            className="flex items-center gap-1.5 text-xs"
          >
            {t.icon}
            {t.label_pl}
            {t.badge !== undefined && (
              <Badge variant="secondary" className="ml-1 h-4 text-[9px]">
                {t.badge}
              </Badge>
            )}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((t) => (
        <TabsContent key={t.id} value={t.id} className="mt-3">
          {t.content}
        </TabsContent>
      ))}
    </Tabs>
  );
}
