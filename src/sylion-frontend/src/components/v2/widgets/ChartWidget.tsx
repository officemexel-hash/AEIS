"use client";

/**
 * SYLION AEIS v2 — W16 G1 widget: ChartWidget.
 *
 * Prosty bar/line chart renderowany ręcznie w SVG (Phase 0: brak dep recharts/d3).
 * - Pasy/linie z gap, oś dolna z labelami i kilkoma tickami pionowymi.
 * - Tooltip natywny (`<title>`) per data point.
 * - Empty state gdy `data.length === 0`.
 */

import { Card } from "@/components/ui/card";
import { HelpTip } from "@/components/common/HelpTip";

export interface ChartDatum {
  label: string;
  value: number;
}

export interface ChartWidgetProps {
  title: string;
  data: ChartDatum[];
  type?: "bar" | "line";
  unit?: string;
  height?: number;
  helpText?: string;
}

const PADDING = { top: 12, right: 12, bottom: 28, left: 36 };

export function ChartWidget({
  title,
  data,
  type = "bar",
  unit,
  height = 240,
  helpText,
}: ChartWidgetProps) {
  const width = 480; // viewBox width — SVG scales to container
  const innerW = width - PADDING.left - PADDING.right;
  const innerH = height - PADDING.top - PADDING.bottom;

  const isEmpty = !data || data.length === 0;

  const maxValue = isEmpty ? 0 : Math.max(...data.map((d) => d.value), 0);
  const minValue = isEmpty ? 0 : Math.min(...data.map((d) => d.value), 0);
  const range = maxValue - minValue || 1;

  function yFor(v: number): number {
    return PADDING.top + innerH - ((v - minValue) / range) * innerH;
  }

  function xFor(i: number): number {
    if (data.length <= 1) return PADDING.left + innerW / 2;
    return PADDING.left + (i / (data.length - 1)) * innerW;
  }

  const ticks = 4;
  const tickValues = Array.from({ length: ticks + 1 }, (_, i) =>
    minValue + (range * i) / ticks,
  );

  return (
    <Card className="overflow-hidden">
      <header className="flex items-center justify-between border-b border-foreground/10 px-4 py-2">
        <h3 className="text-sm font-semibold">
          {title}
          {helpText && <HelpTip text={helpText} />}
        </h3>
        {unit && <span className="text-[10px] text-muted-foreground">[{unit}]</span>}
      </header>

      {isEmpty ? (
        <div className="flex items-center justify-center px-4 py-12 text-xs text-muted-foreground">
          Brak danych
        </div>
      ) : (
        <div className="px-2 py-2">
          <svg
            role="img"
            aria-label={`${title} — ${type}`}
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="none"
            className="h-auto w-full"
          >
            {/* Y axis ticks + grid */}
            {tickValues.map((tv, i) => {
              const y = yFor(tv);
              return (
                <g key={i}>
                  <line
                    x1={PADDING.left}
                    x2={width - PADDING.right}
                    y1={y}
                    y2={y}
                    stroke="currentColor"
                    strokeOpacity={0.08}
                    strokeWidth={1}
                  />
                  <text
                    x={PADDING.left - 4}
                    y={y + 3}
                    fontSize={10}
                    textAnchor="end"
                    className="fill-muted-foreground"
                  >
                    {Number.isInteger(tv) ? tv : tv.toFixed(1)}
                  </text>
                </g>
              );
            })}

            {/* X axis baseline */}
            <line
              x1={PADDING.left}
              x2={width - PADDING.right}
              y1={yFor(Math.max(0, minValue))}
              y2={yFor(Math.max(0, minValue))}
              stroke="currentColor"
              strokeOpacity={0.2}
            />

            {/* Bars */}
            {type === "bar" &&
              data.map((d, i) => {
                const slotW = innerW / data.length;
                const barW = Math.max(2, slotW * 0.7);
                const x = PADDING.left + i * slotW + (slotW - barW) / 2;
                const y0 = yFor(Math.max(0, minValue));
                const y1 = yFor(d.value);
                return (
                  <rect
                    key={`${d.label}-${i}`}
                    x={x}
                    y={Math.min(y0, y1)}
                    width={barW}
                    height={Math.abs(y1 - y0)}
                    className="fill-sylion-blue/70"
                    rx={2}
                  >
                    <title>{`${d.label}: ${d.value}${unit ? ` ${unit}` : ""}`}</title>
                  </rect>
                );
              })}

            {/* Line */}
            {type === "line" && (
              <>
                <polyline
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.5}
                  className="text-sylion-blue"
                  points={data.map((d, i) => `${xFor(i)},${yFor(d.value)}`).join(" ")}
                />
                {data.map((d, i) => (
                  <circle
                    key={`${d.label}-${i}`}
                    cx={xFor(i)}
                    cy={yFor(d.value)}
                    r={2.5}
                    className="fill-sylion-blue"
                  >
                    <title>{`${d.label}: ${d.value}${unit ? ` ${unit}` : ""}`}</title>
                  </circle>
                ))}
              </>
            )}

            {/* X labels */}
            {data.map((d, i) => {
              const x =
                type === "bar"
                  ? PADDING.left + (i + 0.5) * (innerW / data.length)
                  : xFor(i);
              return (
                <text
                  key={`lbl-${i}`}
                  x={x}
                  y={height - PADDING.bottom + 14}
                  fontSize={10}
                  textAnchor="middle"
                  className="fill-muted-foreground"
                >
                  {d.label}
                </text>
              );
            })}
          </svg>
        </div>
      )}
    </Card>
  );
}
