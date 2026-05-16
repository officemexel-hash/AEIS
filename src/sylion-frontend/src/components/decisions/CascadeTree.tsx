"use client";

import React, { useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  ShieldAlert,
  XCircle,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/*  Types                                                                     */
/* -------------------------------------------------------------------------- */

export interface CascadeNode {
  snapshot_id: string;
  decision_id: string;
  decision_class: string; // D0-D5
  choice_made: string;
  impact_radius: string; // local | module | system | cross-system
  cascade_type?: string; // invalidated | needs_review | warning | auto_adapted
  requires_human?: boolean;
  message?: string;
  children?: CascadeNode[];
}

export interface CascadeTreeProps {
  tree: CascadeNode;
  onNodeClick?: (node: CascadeNode) => void;
  onAcknowledge?: (node: CascadeNode) => void;
  selectedId?: string;
  depth?: number; // max depth to render, default unlimited
}

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                   */
/* -------------------------------------------------------------------------- */

const CASCADE_COLORS: Record<string, { bar: string; badge: string; text: string }> = {
  invalidated: {
    bar: "bg-sylion-red",
    badge: "bg-sylion-red/15 text-sylion-red border-sylion-red/30",
    text: "text-sylion-red",
  },
  needs_review: {
    bar: "bg-sylion-amber",
    badge: "bg-sylion-amber/15 text-sylion-amber border-sylion-amber/30",
    text: "text-sylion-amber",
  },
  warning: {
    bar: "bg-yellow-400",
    badge: "bg-yellow-400/15 text-yellow-400 border-yellow-400/30",
    text: "text-yellow-400",
  },
  auto_adapted: {
    bar: "bg-sylion-green",
    badge: "bg-sylion-green/15 text-sylion-green border-sylion-green/30",
    text: "text-sylion-green",
  },
};

const DEFAULT_CASCADE = {
  bar: "bg-sylion-blue",
  badge: "bg-sylion-blue/15 text-sylion-blue border-sylion-blue/30",
  text: "text-sylion-blue",
};

function getCascadeStyle(type?: string) {
  if (!type) return DEFAULT_CASCADE;
  return CASCADE_COLORS[type] ?? DEFAULT_CASCADE;
}

const RADIUS_STYLES: Record<string, string> = {
  local: "bg-muted/40 text-muted-foreground",
  module: "bg-sylion-blue/10 text-sylion-blue",
  system: "bg-sylion-amber/10 text-sylion-amber",
  "cross-system": "bg-sylion-red/10 text-sylion-red",
};

const DECISION_CLASS_COLORS: Record<string, string> = {
  D0: "text-muted-foreground",
  D1: "text-sylion-blue",
  D2: "text-sylion-blue",
  D3: "text-sylion-amber",
  D4: "text-sylion-amber",
  D5: "text-sylion-red",
};

function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max) + "..." : str;
}

/* -------------------------------------------------------------------------- */
/*  CascadeNodeCard                                                           */
/* -------------------------------------------------------------------------- */

function CascadeNodeCard({
  node,
  isSelected,
  onClick,
  onAcknowledge,
  isRoot,
}: {
  node: CascadeNode;
  isSelected: boolean;
  onClick: () => void;
  onAcknowledge?: (node: CascadeNode) => void;
  isRoot: boolean;
}) {
  const style = getCascadeStyle(node.cascade_type);

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25 }}
      onClick={onClick}
      className={cn(
        "relative flex rounded-lg border cursor-pointer transition-all duration-200",
        "hover:scale-[1.008]",
        isSelected
          ? "border-primary/50 shadow-[0_0_12px_rgba(59,130,246,0.2)]"
          : "border-[rgba(148,163,184,0.08)] hover:border-[rgba(148,163,184,0.16)]"
      )}
      style={{
        background:
          "linear-gradient(145deg, rgba(15,22,41,0.95), rgba(20,27,45,0.9))",
        backdropFilter: "blur(12px)",
      }}
    >
      {/* Left colored bar */}
      <div
        className={cn("w-1 shrink-0 rounded-l-lg", style.bar, isRoot && "w-1.5")}
      />

      <div className="flex-1 p-3 min-w-0">
        {/* Top row: decision class + cascade type + impact radius */}
        <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
          <span
            className={cn(
              "text-[10px] font-bold font-mono tracking-wide",
              DECISION_CLASS_COLORS[node.decision_class] ?? "text-muted-foreground"
            )}
          >
            {node.decision_class}
          </span>

          {node.cascade_type === "invalidated" && (
            <Badge
              variant="outline"
              className="h-4 text-[8px] px-1.5 bg-sylion-red/15 text-sylion-red border-sylion-red/30"
            >
              <XCircle className="w-2.5 h-2.5 mr-0.5" />
              INVALIDATED
            </Badge>
          )}

          {node.cascade_type && node.cascade_type !== "invalidated" && (
            <Badge
              variant="outline"
              className={cn("h-4 text-[8px] px-1.5", style.badge)}
            >
              {node.cascade_type === "needs_review" && (
                <AlertTriangle className="w-2.5 h-2.5 mr-0.5" />
              )}
              {node.cascade_type === "warning" && (
                <AlertTriangle className="w-2.5 h-2.5 mr-0.5" />
              )}
              {node.cascade_type === "auto_adapted" && (
                <CheckCircle2 className="w-2.5 h-2.5 mr-0.5" />
              )}
              {node.cascade_type.replace("_", " ")}
            </Badge>
          )}

          <Badge
            variant="outline"
            className={cn(
              "h-4 text-[8px] px-1.5",
              RADIUS_STYLES[node.impact_radius] ?? RADIUS_STYLES.local
            )}
          >
            {node.impact_radius}
          </Badge>

          {node.requires_human && (
            <Badge
              variant="outline"
              className="h-4 text-[8px] px-1.5 bg-sylion-amber/10 text-sylion-amber border-sylion-amber/30"
            >
              <span className="relative flex h-1.5 w-1.5 mr-1">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sylion-amber opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-sylion-amber" />
              </span>
              Review needed
            </Badge>
          )}
        </div>

        {/* Choice made text */}
        <p className="text-[11px] text-foreground leading-relaxed">
          {truncate(node.choice_made, 60)}
        </p>

        {/* Message */}
        {node.message && (
          <p className="text-[10px] text-muted-foreground mt-1 leading-relaxed">
            {node.message}
          </p>
        )}

        {/* Acknowledge button */}
        {node.requires_human && onAcknowledge && (
          <div className="mt-2">
            <Button
              variant="outline"
              size="xs"
              className="h-5 text-[9px] px-2 border-sylion-amber/30 text-sylion-amber hover:bg-sylion-amber/10"
              onClick={(e: React.MouseEvent) => {
                e.stopPropagation();
                onAcknowledge(node);
              }}
            >
              <Eye className="w-2.5 h-2.5 mr-1" />
              Acknowledge
            </Button>
          </div>
        )}
      </div>
    </motion.div>
  );
}

/* -------------------------------------------------------------------------- */
/*  TreeEdge                                                                  */
/* -------------------------------------------------------------------------- */

function TreeEdge({
  strength,
  label,
}: {
  strength: "strong" | "weak";
  label?: string;
}) {
  return (
    <div className="flex items-center gap-0 py-0">
      {/* Vertical connector */}
      <div
        className={cn(
          "w-px h-4 ml-4",
          strength === "strong"
            ? "bg-[rgba(148,163,184,0.25)]"
            : "border-l border-dashed border-[rgba(148,163,184,0.15)]"
        )}
      />
      {label && (
        <span className="text-[8px] text-muted-foreground/50 ml-1">{label}</span>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Recursive Tree Renderer                                                   */
/* -------------------------------------------------------------------------- */

function CascadeTreeLevel({
  node,
  onNodeClick,
  onAcknowledge,
  selectedId,
  currentDepth,
  maxDepth,
}: {
  node: CascadeNode;
  onNodeClick?: (node: CascadeNode) => void;
  onAcknowledge?: (node: CascadeNode) => void;
  selectedId?: string;
  currentDepth: number;
  maxDepth: number;
}) {
  const hasChildren = node.children && node.children.length > 0;
  const isWithinDepth = maxDepth === -1 || currentDepth < maxDepth;
  const isSelected = selectedId === node.decision_id;

  const handleClick = useCallback(() => {
    onNodeClick?.(node);
  }, [onNodeClick, node]);

  const edgeStrength: "strong" | "weak" =
    node.cascade_type === "invalidated" || node.cascade_type === "needs_review"
      ? "strong"
      : "weak";

  return (
    <div className="flex flex-col">
      {/* Node card */}
      <CascadeNodeCard
        node={node}
        isSelected={isSelected}
        onClick={handleClick}
        onAcknowledge={onAcknowledge}
        isRoot={currentDepth === 0}
      />

      {/* Children with edge connectors */}
      <AnimatePresence>
        {hasChildren && isWithinDepth && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, delay: 0.05 }}
            className="ml-10 mt-0 space-y-0"
          >
            {node.children!.map((child, idx) => (
              <motion.div
                key={child.decision_id}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: 0.3,
                  delay: (currentDepth + 1) * 0.08 + idx * 0.05,
                }}
              >
                {/* Edge connector before each child */}
                <TreeEdge
                  strength={edgeStrength}
                  label={child.cascade_type?.replace("_", " ")}
                />
                <CascadeTreeLevel
                  node={child}
                  onNodeClick={onNodeClick}
                  onAcknowledge={onAcknowledge}
                  selectedId={selectedId}
                  currentDepth={currentDepth + 1}
                  maxDepth={maxDepth}
                />
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Exported Component                                                        */
/* -------------------------------------------------------------------------- */

export function CascadeTree({
  tree,
  onNodeClick,
  onAcknowledge,
  selectedId,
  depth,
}: CascadeTreeProps) {
  const maxDepth = depth ?? -1; // -1 = unlimited

  const hasChildren = tree.children && tree.children.length > 0;

  if (!hasChildren) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <ShieldAlert className="w-6 h-6 text-muted-foreground/30 mb-2" />
        <p className="text-[11px] text-muted-foreground">
          No cascade impact &mdash; this is a leaf decision
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-0">
      <CascadeTreeLevel
        node={tree}
        onNodeClick={onNodeClick}
        onAcknowledge={onAcknowledge}
        selectedId={selectedId}
        currentDepth={0}
        maxDepth={maxDepth}
      />
    </div>
  );
}
