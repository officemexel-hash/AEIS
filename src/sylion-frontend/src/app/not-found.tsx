import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-6xl font-semibold tracking-tight">404</h1>
      <p className="text-lg text-muted-foreground">Strona nie została znaleziona.</p>
      <p className="text-sm text-muted-foreground">Sprawdź adres URL lub wróć do panelu.</p>
      <Link
        href="/overview"
        className="mt-4 inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
      >
        Wróć do Overview
      </Link>
    </main>
  );
}
