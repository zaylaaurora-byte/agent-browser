import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  api: {
    proxy: {
      "/api/execute": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
};

export default nextConfig;