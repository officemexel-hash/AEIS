"use client";

import React from "react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  ArrowRight,
  FilePlus2,
  FileX2,
  FilePenLine,
  Plus,
  Minus,
  Package,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/*  Types                                                                     */
/* -------------------------------------------------------------------------- */

export interface SnapshotDiffProps {
  diff: {
    modules_added: string[];
    modules_removed: string[];
    modules_changed: { module_id: string; from: any; to: any }[];
    contracts_added: string[];
    contracts_removed: string[];
  };
}

/* -------------------------------------------------------------------------- */
/*  Sub-components                                                            */
/* -------------------------------------------------------------------------- */

function DiffRow({
  label,
  icon,
  colorClass,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  colorClass: string;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "flex items-center gap-2 px-3 py-1.5 rounded-md border border-[rgba(148,163,184,0.06)]",
        colorClass
      )}
    >
      <span className="shrink-0">{icon}</span>
      <span className="text-[10px] font-medium truncate">{label}</span>
      {children}
    </motion.div>
  );
}

function SectionHeader({
  title,
  icon,
  added,
  removed,
  changed,
}: {
  title: string;
  icon: React.ReactNode;
  added: number;
  removed: number;
  changed: number;
}) {
  const total = added + removed + changed;

  return (
    <div className="flex items-center gap-2 mb-2">
      <span className="text-muted-foreground/60">{icon}</span>
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </span>
      {total > 0 && (
        <span className="text-[9px] text-muted-foreground/50">
          ({added > 0 && (
            <span className="text-sylion-green">+{added}</span>
          )}
          {added > 0 && (removed > 0 || changed > 0) && " "}
          {removed > 0 && (
            <span className="text-sylion-red">-{removed}</span>
          )}
          {removed > 0 && changed > 0 && " "}
          {changed > 0 && (
            <span className="text-sylion-amber">~{changed}</span>
          )}
          )
        </span>
      )}
      {total === 0 && (
        <span className="text-[9px] text-muted-foreground/40">no changes</span>
      )}
    </div>
  );
}

function ValueDisplay({ value }: { value: any }) {
  if (value === null || value === undefined) {
    return <span className="text-[9px] text-muted-foreground/40 italic">null</span>;
  }
  if (typeof value === "object") {
    return (
      <span className="text-[9px] font-mono text-foreground/70">
        {JSON.stringify(value)}
      </span>
    );
  }
  return <span className="text-[9px] font-mono text-foreground/70">{String(value)}</span>;
}

/* -------------------------------------------------------------------------- */
/*  Exported Component                                                        */
/* -------------------------------------------------------------------------- */

export function SnapshotDiffViewer({ diff }: SnapshotDiffProps) {
  const hasModuleChanges =
    diff.modules_added.length > 0 ||
    diff.modules_removed.length > 0 ||
    diff.modules_changed.length > 0;

  const hasContractChanges =
    diff.contracts_added.length > 0 || diff.contracts_removed.length > 0;

  const hasAnyChanges = hasModuleChanges || hasContractChanges;

  if (!hasAnyChanges) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center">
        <Package className="w-6 h-6 text-muted-foreground/30 mb-2" />
        <p className="text-[11px] text-muted-foreground">
          No differences between snapshots
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Modules section */}
      <div>
        <SectionHeader
          title="Modules"
          icon={<Package className="w-3.5 h-3.5" />}
          added={diff.modules_added.length}
          removed={diff.modules_removed.length}
          changed={diff.modules_changed.length}
        />

        {hasModuleChanges ? (
          <div className="space-y-1">
            {/* Added */}
            {diff.modules_added.map((mod) => (
              <DiffRow
                key={`add-${mod}`}
                label={mod}
                icon={<FilePlus2 className="w-3 h-3 text-sylion-green" />}
                colorClass="bg-sylion-green/5"
              >
                <Badge
                  variant="outline"
                  className="h-3.5 text-[7px] px-1 ml-auto bg-sylion-green/10 text-sylion-green border-sylion-green/20"
                >
                  <Plus className="w-2 h-2" />
                  ADD
                </Badge>
              </DiffRow>
            ))}

            {/* Removed */}
            {diff.modules_removed.map((mod) => (
              <DiffRow
                key={`rm-${mod}`}
                label={mod}
                icon={<FileX2 className="w-3 h-3 text-sylion-red" />}
                colorClass="bg-sylion-red/5"
              >
                <Badge
                  variant="outline"
                  className="h-3.5 text-[7px] px-1 ml-auto bg-sylion-red/10 text-sylion-red border-sylion-red/20"
                >
                  <Minus className="w-2 h-2" />
                  DEL
                </Badge>
              </DiffRow>
            ))}

            {/* Changed */}
            {diff.modules_changed.map((change) => (
              <div
                key={`ch-${change.module_id}`}
                className="px-3 py-1.5 rounded-md border border-sylion-amber/10 bg-sylion-amber/5"
              >
                <div className="flex items-center gap-2">
                  <FilePenLine className="w-3 h-3 text-sylion-amber shrink-0" />
                  <span className="text-[10px] font-medium text-foreground">
                    {change.module_id}
                  </span>
                  <Badge
                    variant="outline"
                    className="h-3.5 text-[7px] px-1 ml-auto bg-sylion-amber/10 text-sylion-amber border-sylion-amber/20"
                  >
                    MOD
                  </Badge>
                </div>
                <div className="flex items-center gap-2 mt-1 ml-5">
                  <ValueDisplay value={change.from} />
                  <ArrowRight className="w-3 h-3 text-sylion-amber/60 shrink-0" />
                  <ValueDisplay value={change.to} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[10px] text-muted-foreground/40 pl-1">
            No module changes
          </p>
        )}
      </div>

      {/* Contracts section */}
      <div>
        <SectionHeader
          title="Contracts"
          icon={<Package className="w-3.5 h-3.5" />}
          added={diff.contracts_added.length}
          removed={diff.contracts_removed.length}
          changed={0}
        />

        {hasContractChanges ? (
          <div className="space-y-1">
            {/* Added */}
            {diff.contracts_added.map((contract) => (
              <DiffRow
                key={`ca-${contract}`}
                label={contract}
                icon={<FilePlus2 className="w-3 h-3 text-sylion-green" />}
                colorClass="bg-sylion-green/5"
              >
                <Badge
                  variant="outline"
                  className="h-3.5 text-[7px] px-1 ml-auto bg-sylion-green/10 text-sylion-green border-sylion-green/20"
                >
                  <Plus className="w-2 h-2" />
                  ADD
                </Badge>
              </DiffRow>
            ))}

            {/* Removed */}
            {diff.contracts_removed.map((contract) => (
              <DiffRow
                key={`cr-${contract}`}
                label={contract}
                icon={<FileX2 className="w-3 h-3 text-sylion-red" />}
                colorClass="bg-sylion-red/5"
              >
                <Badge
                  variant="outline"
                  className="h-3.5 text-[7px] px-1 ml-auto bg-sylion-red/10 text-sylion-red border-sylion-red/20"
                >
                  <Minus className="w-2 h-2" />
                  DEL
                </Badge>
              </DiffRow>
            ))}
          </div>
        ) : (
          <p className="text-[10px] text-muted-foreground/40 pl-1">
            No contract changes
          </p>
        )}
      </div>
    </div>
  );
}
