/**
 * SYLION AEIS v2 — W16 G1+G2 widget barrel.
 *
 * Skeleton dla W16 Apps Builder (PDF §4.2 / docs/v2/charters/W16_apps_builder.md).
 * Operator (Robert) używa tych widgetów deklaratywnie w app manifests.
 *
 * G1 (5): ObjectListView, ObjectFormEditor, KpiCard, ChartWidget, AdvisorCardFeed.
 * G2 (5): DateRangePicker, JsonViewer, TabsWidget, AlertBanner, CommandButton.
 */

export { ObjectListView } from "./ObjectListView";
export type { ObjectListViewProps } from "./ObjectListView";

export { ObjectFormEditor } from "./ObjectFormEditor";
export type { ObjectFormEditorProps } from "./ObjectFormEditor";

export { KpiCard } from "./KpiCard";
export type { KpiCardProps, KpiTrend } from "./KpiCard";

export { ChartWidget } from "./ChartWidget";
export type { ChartWidgetProps, ChartDatum } from "./ChartWidget";

export { AdvisorCardFeed } from "./AdvisorCardFeed";
export type { AdvisorCardFeedProps } from "./AdvisorCardFeed";

export { DateRangePicker } from "./DateRangePicker";
export type { DateRangePickerProps, DateRangePreset } from "./DateRangePicker";

export { JsonViewer } from "./JsonViewer";
export type { JsonViewerProps } from "./JsonViewer";

export { TabsWidget } from "./TabsWidget";
export type { TabsWidgetProps, TabDef } from "./TabsWidget";

export { AlertBanner } from "./AlertBanner";
export type { AlertBannerProps, AlertVariant, AlertAction } from "./AlertBanner";

export { CommandButton } from "./CommandButton";
export type { CommandButtonProps } from "./CommandButton";
