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
    ];
  },
};

export default nextConfig;
