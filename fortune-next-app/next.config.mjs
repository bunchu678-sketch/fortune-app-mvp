import { lstatSync, readFileSync } from "node:fs";
import { apiOrigin, teacherUiEnabled, TEACHER_SURFACE } from "./api-origin.mjs";

const marker = new URL("./.mari-reading-release", import.meta.url);
const markerInfo = lstatSync(marker, { throwIfNoEntry: false });
const marked = Boolean(markerInfo);
if (marked && (markerInfo.isSymbolicLink() || !markerInfo.isFile() || readFileSync(marker, "utf8") !== TEACHER_SURFACE + "\n")) {
  throw new Error("Dedicated release marker is invalid.");
}
const teacher = marked || teacherUiEnabled();
const origin = apiOrigin(process.env, teacher);
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: { FORTUNE_READING_BUILD_MODE: teacher ? TEACHER_SURFACE : "" },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${origin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
