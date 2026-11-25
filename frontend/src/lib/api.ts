import { env } from './env';

/** Error body of the Bee4You API: { "error": { "code", "message", "details" } }. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type ApiRequest = {
  method?: 'GET' | 'POST';
  body?: unknown;
  token: string;
  timeoutMs?: number;
};

/** Raw call to the API. Returns the Response so callers can decide per status code. */
export async function apiRequest(path: string, req: ApiRequest): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), req.timeoutMs ?? 30_000);
  try {
    return await fetch(`${env.apiUrl}${path}`, {
      method: req.method ?? 'GET',
      headers: {
        Authorization: `Bearer ${req.token}`,
        ...(req.body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: req.body === undefined ? undefined : JSON.stringify(req.body),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

/** Call the API and parse JSON; non-2xx becomes ApiError. */
export async function apiJson<T>(path: string, req: ApiRequest): Promise<T> {
  const res = await apiRequest(path, req);
  const text = await res.text();
  if (!res.ok) {
    let code = 'http_error';
    let message = text.slice(0, 300) || `HTTP ${res.status}`;
    try {
      const parsed = JSON.parse(text) as { error?: { code?: string; message?: string } };
      code = parsed.error?.code ?? code;
      message = parsed.error?.message ?? message;
    } catch {
      // not JSON: keep the raw text
    }
    throw new ApiError(res.status, code, message);
  }
  return JSON.parse(text) as T;
}
