import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { tokenStore } from "../auth/tokenStore";
import { endImpersonation, readImpersonation } from "../auth/impersonation";

/**
 * فاز ۳۹ - مهاجرت فرانت‌اند به قرارداد ADR-03 (/api/v2):
 *
 * سیم (wire) نسخه v2 پاسخ‌ها را در پاکت استاندارد
 *   موفقیت: {"data": ..., "meta": {...}, "errors": null}
 *   خطا:    {"data": null, "meta": {...}, "errors": [{code, message, details?}]}
 * برمی‌گرداند. این ماژول تنها نقطه سازگاری (adapter) بین سیم v2 و شکل مصرف
 * داخلی برنامه است:
 *
 * - interceptor موفقیت، `res.data` را به payload واقعی (data) می‌کاهد و
 *   `meta` پاکت را روی `res.meta` (augmentation تایپ axios) در دسترس می‌گذارد؛
 * - پاسخ‌های صفحه‌بندی‌شده، اطلاعات total/page/... را در `res.meta.pagination`
 *   دارند — helper `paginationOf` برای بازچینی شکل‌های Paged در لایه api؛
 * - پاسخ‌های غیر JSON (دانلود فایل B39، blob قالب import) دست‌نخورده عبور
 *   می‌کنند؛
 * - `errDetail` خطا را از `errors[0].message` پاکت می‌خواند و شکل قدیمی
 *   `{detail}` را هم به‌عنوان fallback پشتیبانی می‌کند.
 */

export interface EnvelopeMeta {
  request_id: string;
  timestamp: string;
  version: string;
  duration_ms: number;
  idempotency_key?: string;
  pagination?: Record<string, unknown>;
}

interface EnvelopeBody {
  data: unknown;
  meta?: EnvelopeMeta;
  errors: unknown;
}

declare module "axios" {
  export interface AxiosResponse<T = any, D = any> {
    /** متادیتای پاکت v2 (ADR-03) — پس از گشودن پاکت در interceptor */
    meta?: EnvelopeMeta;
  }
}

function isEnvelope(x: unknown): x is EnvelopeBody {
  return (
    typeof x === "object" &&
    x !== null &&
    "data" in x &&
    "meta" in x &&
    "errors" in x &&
    typeof (x as EnvelopeBody).meta === "object" &&
    (x as EnvelopeBody).meta !== null &&
    typeof (x as EnvelopeBody).meta!.version === "string"
  );
}

/** اطلاعات صفحه‌بندی پاسخ‌های فهرست v2 ({items,...} → data + meta.pagination) */
export function paginationOf(res: AxiosResponse): Record<string, unknown> {
  return res.meta?.pagination ?? {};
}

/** فاز ۷۰ ب — خواندن اقلام فهرست از پاسخ v2 به شکلی همیشه-درست.
 *
 * پاکت v2 پاسخ‌های «فهرست صفحه‌بندی‌شده» ({items, total/page/...}) را می‌شکند:
 * اقلام → آرایهٔ برهنه در `data` و بقیهٔ کلیدها → `meta.pagination`؛ ولی
 * پاسخ‌های {items:[...]} بدون نشانگر صفحه‌بندی دست‌نخورده می‌مانند.
 * خواندن کورکورانهٔ `data.items` در حالت اول undefined می‌دهد و react-query
 * با «Query data cannot be undefined» صفحه را به «خطای نامشخص رخ داد»
 * می‌برد (عارضهٔ میدانی صفحات فاز ۷۰). این هلپر هر دو شکل را پوشش می‌دهد.
 */
export function itemsOf<T>(res: AxiosResponse): T[] {
  const d = res.data as unknown;
  if (Array.isArray(d)) return d as T[];
  if (d && typeof d === "object" && Array.isArray((d as { items?: unknown }).items)) {
    return (d as { items: T[] }).items;
  }
  return [];
}

function unwrapEnvelope(res: AxiosResponse): AxiosResponse {
  const rt = res.config.responseType;
  if (rt && rt !== "json" && rt !== "text") return res; // blob/arraybuffer — دانلود B39
  if (isEnvelope(res.data)) {
    const envelope = res.data as EnvelopeBody;
    res.data = envelope.data;
    res.meta = envelope.meta;
  }
  return res;
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v2",
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  if (tokenStore.accessToken) {
    config.headers.Authorization = `Bearer ${tokenStore.accessToken}`;
  }
  return config;
});

const NO_REFRESH_PATHS = ["/auth/login", "/auth/refresh", "/auth/activate"];

// فاز ۴۵: base پنل (Docker: /panel؛ dev: /) — ریدایرکت ۴۰۱ باید داخل خود پنل بماند؛
// ریدایرکت به "/login" مطلق، صفحه index سایت را در /login سرو می‌کرد و router سایت
// (fallback to /) کاربر را به صفحه اصلی سایت پرت می‌کرد — باگ «خروج فوری از پنل».
const ROUTER_BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

let refreshPromise: Promise<string | null> | null = null;

async function callRefresh(): Promise<string | null> {
  try {
    const res = await axios.post(`${apiClient.defaults.baseURL}/auth/refresh`, {}, { withCredentials: true });
    const payload = isEnvelope(res.data) ? res.data.data : res.data;
    return (payload as { access_token?: string })?.access_token ?? null;
  } catch {
    return null;
  }
}

/** فاز ۵۲: توضمن وجود access token (برای WebSocket چت) — در صورت نبود، refresh می‌زند */
export async function ensureAccessToken(): Promise<string | null> {
  if (!tokenStore.accessToken) {
    // فاز ۶۰: بازگردانی توکن مشاهده (impersonation) پس از reload ماژول
    const imp = readImpersonation();
    if (imp) tokenStore.accessToken = imp.token;
  }
  if (tokenStore.accessToken) return tokenStore.accessToken;
  // فاز ۶۰: در حالت مشاهده هرگز refresh نمی‌زنیم — کوکی refresh متعلق به
  // مدیر است و refresh زدن ناخواسته مدیر را به داخل نشست مشاهده می‌آورد.
  if (readImpersonation()) return null;
  const fresh = await callRefresh();
  if (fresh) tokenStore.accessToken = fresh;
  return fresh;
}

/** فاز ۶۰: خروج خودکار از حالت مشاهده در 401 (انقضای توکن/تغییر حساس حساب) */
function exitImpersonationAndReload(): void {
  const info = readImpersonation();
  endImpersonation();
  tokenStore.accessToken = null;
  window.location.href = info?.returnPath ?? `${ROUTER_BASE}/users`;
}

apiClient.interceptors.response.use(unwrapEnvelope, async (error: AxiosError) => {
  const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
  const url = original?.url ?? "";

  // فاز ۶۰: در حالت مشاهده (impersonation) با 401 هرگز refresh نمی‌زنیم —
  // کوکی refresh متعلق به مدیر است؛ خروج تمیز از حالت مشاهده به حساب مدیر.
  const impersonating = !!readImpersonation();
  if (error.response?.status === 401 && impersonating) {
    exitImpersonationAndReload();
    return Promise.reject(error);
  }

  const shouldTryRefresh =
    error.response?.status === 401 &&
    original &&
    !original._retry &&
    !NO_REFRESH_PATHS.some((p) => url.includes(p));

  if (shouldTryRefresh) {
    original!._retry = true;
    refreshPromise = refreshPromise ?? callRefresh();
    const newToken = await refreshPromise;
    refreshPromise = null;
    if (newToken) {
      tokenStore.accessToken = newToken;
      return apiClient(original!);
    }
    tokenStore.accessToken = null;
    if (!window.location.pathname.startsWith(`${ROUTER_BASE}/login`)) {
      window.location.href = `${ROUTER_BASE}/login`;
    }
  }
  return Promise.reject(error);
});

export function errDetail(e: unknown): string {
  const anyE = e as { response?: { data?: unknown } };
  const body = anyE?.response?.data;

  // پاکت v2: errors: [{code, message, details?}]
  if (body && typeof body === "object" && Array.isArray((body as EnvelopeBody).errors)) {
    const errs = ((body as EnvelopeBody).errors ?? []) as { code?: string; message?: string }[];
    const msg = errs
      .map((x) => x.message || x.code || "")
      .filter(Boolean)
      .join(" — ");
    if (msg) return msg;
  }

  // قرارداد v1 (fallback) و پاسخ‌های بدون پاکت
  const d = (body as { detail?: unknown } | undefined)?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") {
    const obj = d as { message?: string; errors?: { label?: string; error?: string }[] };
    const errs = (obj.errors ?? [])
      .map((x) => `${x.label ?? ""}: ${x.error ?? ""}`.trim())
      .filter(Boolean);
    return [obj.message, ...errs].filter(Boolean).join(" — ");
  }
  // فاز ۷۰ ب — هیچ detail قابل نمایشی نبود: حداقل کد وضعیت HTTP را نشان بده
  // تا «خطای نامشخص» قابل تفکیک شود (۵۰۰ سرور، ۵۰۳ اسکیما، قطع شبکه، …).
  const status = (anyE as { response?: { status?: number } })?.response?.status;
  if (typeof body === "string" && body.trim()) {
    return `${body.trim()} (HTTP ${status ?? "?"})`;
  }
  return `خطای نامشخص رخ داد${status ? ` (HTTP ${status})` : ""}`;
}
