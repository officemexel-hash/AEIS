"use client";

import React, { useCallback, useRef, useState, type ReactNode } from "react";

interface SplitViewProps {
  left: ReactNode;
  right: ReactNode;
  defaultSplit?: number;
  minLeft?: number;
  maxLeft?: number;
}

export function SplitView({
  left,
  right,
  defaultSplit = 0.45,
  minLeft = 0.2,
  maxLeft = 0.7,
}: SplitViewProps) {
  const [split, setSplit] = useState(defaultSplit);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const ratio = (ev.clientX - rect.left) / rect.width;
      setSplit(Math.min(maxLeft, Math.max(minLeft, ratio)));
    };

    const onMouseUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [minLeft, maxLeft]);

  return (
    <div ref={containerRef} className="flex h-full w-full overflow-hidden">
      <div style={{ width: `${split * 100}%` }} className="overflow-y-auto">
        {left}
      </div>
      <div
        onMouseDown={onMouseDown}
        className="w-1 shrink-0 cursor-col-resize bg-[rgba(148,163,184,0.08)] hover:bg-primary/30 transition-colors"
      />
      <div style={{ width: `${(1 - split) * 100}%` }} className="overflow-y-auto">
        {right}
      </div>
    </div>
  );
}
