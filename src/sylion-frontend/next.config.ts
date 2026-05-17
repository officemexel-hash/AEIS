import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1", "::1"],
  async rewrites() {
    return [
      {
        source: "/health",
        destination: "http://127.0.0.1:8010/health",
      },
      {
        source: "/backend-health",
        destination: "http://127.0.0.1:8010/health",
      },
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8010/api/v1/:path*",
      },
      {
        source: "/api/dashboard/:path*",
        destination: "http://127.0.0.1:8010/api/dashboard/:path*",
      },
      {
        source: "/api/runs/:path*",
        destination: "http://127.0.0.1:8010/api/runs/:path*",
      },
      {
        source: "/api/human-gate/:path*",
        destination: "http://127.0.0.1:8010/api/human-gate/:path*",
      },
    ];
  },
};

export default nextConfig;