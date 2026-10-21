import type { NextConfig } from "next";

const LOCAL_API_URL = "http://127.0.0.1:8000";
const RESOLVED_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? LOCAL_API_URL).trim().replace(/\/+$/, "") || LOCAL_API_URL;

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: RESOLVED_API_URL,
  },
};

export default nextConfig;
