import { authHeaders, proxyBackendJson } from "@/lib/server/priorauth-proxy";

export async function GET(request: Request) {
  return proxyBackendJson(request, "/api/cases", {
    method: "GET",
    headers: authHeaders(request)
  });
}

export async function POST(request: Request) {
  return proxyBackendJson(request, "/api/cases", {
    method: "POST",
    body: await request.text(),
    headers: authHeaders(request, true)
  });
}
