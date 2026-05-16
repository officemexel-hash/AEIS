"use client";

import { useState, useMemo } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useBackboneHealth, useBackboneCatalog, useBackboneEvents, useHealth } from "@/lib/api/hooks";
import { cn, fmtDateTime } from "@/lib/utils";
import { Activity, Radio, List, Server, Wifi, Database } from "lucide-react";

const backendIcon = (mode: string) => {
  if (mode === "nats") return <Radio className="w-4 h-4" />;
  if (mode === "redis") return <Database className="w-4 h-4" />;
  return <Server className="w-4 h-4" />;
};

export default function EventsPage() {
  const { data: health } = useHealth();
  const { data: bbHealth } = useBackboneHealth();
  const { data: catalogData } = useBackboneCatalog();
  const { data: eventsData, refresh: refreshEvents } = useBackboneEvents();

  const backendLive = health?.status === "ok";
  const events = eventsData?.events ?? [];
  const topics = catalogData?.topics ?? [];
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  const filteredEvents = useMemo(() => {
    if (!selectedTopic) return events;
    return events.filter((e: any) => e.topic === selectedTopic);
  }, [events, selectedTopic]);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
            <Activity className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Event Backbone</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Pub/sub health, catalog & event stream</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {backendLive && (
            <Badge variant="outline" className="text-[10px] border-sylion-green/30 text-sylion-green">
              <span className="w-1.5 h-1.5 rounded-full bg-sylion-green mr-1.5 pulse-glow-green" />
              LIVE
            </Badge>
          )}
          <Button size="sm" variant="outline" onClick={refreshEvents}>
            <Activity className="w-3.5 h-3.5 mr-1" /> Refresh
          </Button>
        </div>
      </div>

      {/* Backbone health */}
      <div className="grid grid-cols-4 gap-3">
        <Card className="p-4 bg-card border-sylion-border">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Backend</p>
          <div className="flex items-center gap-2 mt-1">
            {backendIcon(bbHealth?.backend || "local")}
            <p className="text-lg font-semibold capitalize">{bbHealth?.backend || "local"}</p>
          </div>
        </Card>
        <Card className="p-4 bg-card border-sylion-border">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Status</p>
          <p className={cn("text-lg font-semibold mt-1", bbHealth?.status === "ok" ? "text-sylion-green" : "text-sylion-red")}>
            {bbHealth?.status || "unknown"}
          </p>
        </Card>
        <Card className="p-4 bg-card border-sylion-border">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Published</p>
          <p className="text-lg font-semibold mt-1">{bbHealth?.published ?? 0}</p>
        </Card>
        <Card className="p-4 bg-card border-sylion-border">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Topics</p>
          <p className="text-lg font-semibold mt-1">{topics.length}</p>
        </Card>
      </div>

      {/* Topics */}
      {topics.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">Topic Catalog</h3>
          <div className="flex flex-wrap gap-2">
            <Badge
              variant={selectedTopic === null ? "default" : "outline"}
              className="cursor-pointer text-[10px]"
              onClick={() => setSelectedTopic(null)}
            >
              All
            </Badge>
            {topics.map((t: string) => (
              <Badge
                key={t}
                variant={selectedTopic === t ? "default" : "outline"}
                className="cursor-pointer text-[10px]"
                onClick={() => setSelectedTopic(t)}
              >
                {t}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Events stream */}
      <div>
        <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-2">
          Event Stream {selectedTopic && <span className="text-primary">({selectedTopic})</span>}
        </h3>
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {filteredEvents.length === 0 && (
            <Card className="p-4 bg-card border-sylion-border text-center text-sm text-muted-foreground">
              No events recorded yet.
            </Card>
          )}
          {filteredEvents.map((evt: any, idx: number) => (
            <Card key={idx} className="p-3 bg-card border-sylion-border">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Wifi className="w-3 h-3 text-primary" />
                  <span className="text-xs font-mono">{evt.topic}</span>
                </div>
                <span className="text-[10px] text-muted-foreground">{fmtDateTime(evt.timestamp || evt.created_at)}</span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-1 truncate">
                {JSON.stringify(evt.payload || evt).slice(0, 120)}
              </p>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
