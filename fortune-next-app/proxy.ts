import { NextRequest, NextResponse } from "next/server";
export function proxy(request: NextRequest) {
  if (process.env.FORTUNE_UI_SURFACE !== "teacher") return NextResponse.next();
  let path = request.nextUrl.pathname;
  try { path = decodeURIComponent(path); } catch { return new NextResponse(null, { status: 404 }); }
  if (path === "/_next/image" || path.startsWith("/_next/image/")) {
    return new NextResponse(null, { status: 404, headers: { "Cache-Control": "no-store" } });
  }
  const retired = /^\/(history|mypage|member|teacher|b2b|operations|product)(\/|$)/.test(path);
  const response = retired ? NextResponse.redirect(new URL("/", request.url)) : NextResponse.next();
  response.headers.set("Cache-Control", "no-store");
  return response;
}
export const config = { matcher: ["/_next/image/:path*", "/((?!_next/static|_next/image|favicon.ico|api/).*)"] };
