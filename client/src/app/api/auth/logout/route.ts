import { NextResponse } from "next/server";

import { AUTH_COOKIE_NAME, authCookieOptions, rejectCrossOriginMutation } from "@/lib/server/priorauth-proxy";

export async function POST(request: Request) {
  const crossOriginResponse = rejectCrossOriginMutation(request);
  if (crossOriginResponse) return crossOriginResponse;

  const response = NextResponse.json({ ok: true });
  response.cookies.set(AUTH_COOKIE_NAME, "", authCookieOptions(0));
  return response;
}
