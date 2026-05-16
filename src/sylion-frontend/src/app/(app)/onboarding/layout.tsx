"use client";

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="min-h-[calc(100vh-3.5rem)] -m-6 flex flex-col"
      style={{
        backgroundImage:
          "radial-gradient(circle at 15% 0%, rgba(56, 132, 255, 0.10), transparent 45%), radial-gradient(circle at 85% 100%, rgba(255, 191, 71, 0.07), transparent 45%)",
      }}
    >
      {children}
    </div>
  );
}
