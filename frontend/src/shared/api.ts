let csrfToken = '';
export function setCsrfToken(token: string) { csrfToken = token; }
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
export async function api<T>(path: string, method = 'GET', body?: unknown, key?: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken, ...(key ? { 'Idempotency-Key': key } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ code: 'transport_error', message: 'Сервис временно недоступен' })) as { code: string; message: string };
    throw new ApiError(response.status, error.code, error.message);
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}
