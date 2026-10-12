import type { paths } from "./api-schema";

export type BacktestRequest =
  paths["/api/v1/backtests"]["post"]["requestBody"]["content"]["application/json"];
export type BacktestResponse =
  paths["/api/v1/backtests"]["post"]["responses"][200]["content"]["application/json"];
export type SymbolInfo =
  paths["/api/v1/symbols"]["get"]["responses"][200]["content"]["application/json"][number];
export type CurveMetrics = BacktestResponse["strategy"];
export type PaperAccountSummary =
  paths["/api/v1/paper/accounts"]["get"]["responses"][200]["content"]["application/json"][number];
export type PaperAccountDetail =
  paths["/api/v1/paper/accounts/{name}"]["get"]["responses"][200]["content"]["application/json"];
export type PaperDay = PaperAccountDetail["days"][number];

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
      }
    } catch {
      /* keep the status text when the body is not JSON */
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  symbols: () => request<SymbolInfo[]>("/symbols"),
  runBacktest: (body: BacktestRequest) =>
    request<BacktestResponse>("/backtests", { method: "POST", body: JSON.stringify(body) }),
  paperAccounts: () => request<PaperAccountSummary[]>("/paper/accounts"),
  paperAccount: (name: string) => request<PaperAccountDetail>(`/paper/accounts/${encodeURIComponent(name)}`),
};
