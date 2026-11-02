import { apiClient, paginationOf } from "./client";

export const ROLE_OPTIONS: { code: string; title: string }[] = [
  { code: "SYSTEM_ADMIN", title: "مدیر سامانه" },
  { code: "ORG_MANAGER", title: "مدیر سازمان" },
  { code: "RECEPTION", title: "پذیرش" },
  { code: "COUNSELOR", title: "مشاور" },
  { code: "TECHNICAL_SUPERVISOR", title: "مسئول فنی" },
  { code: "APPLICANT", title: "متقاضی" },
];

export function roleTitle(code: string): string {
  return ROLE_OPTIONS.find((r) => r.code === code)?.title ?? code;
}

export interface Me {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  mobile: string | null;
  status: string;
  must_change_password: boolean;
  roles: string[];
  /** فاز ۵۲: دسترسی‌های مؤثر (اجتماع نقش‌ها)؛ * یعنی همه — SYSTEM_ADMIN */
  permissions?: string[];
  /** فاز ۷۱: ماتریس منوها — {menu_key: 'view'|'read'|'edit'}؛ کلیدِ غایب یعنی منو پنهان */
  menu_permissions?: Record<string, string>;
  /** فاز ۷۴: سازمان کاربر (ایزولاسیون دادهٔ سازمانی) — null = بدون محدودیت */
  organization_id?: string | null;
  organization_name?: string | null;
}

/** سطح دسترسی کاربر به یک منو ('view'|'read'|'edit') یا undefined اگر پنهان است */
export function menuLevel(me: Me | null, menuKey: string): string | undefined {
  return me?.menu_permissions?.[menuKey];
}

/** بررسی دسترسی مؤثر کاربر (سمت کلاینت برای گیت منو/دکمه؛ سرور ملاک نهایی است) */
export function hasPerm(me: Me | null, code: string): boolean {
  if (!me) return false;
  const perms = me.permissions ?? [];
  return perms.includes("*") || perms.includes(code);
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  must_change_password: boolean;
}

/** فاز ۷۲ — پراپ بی‌صدای نشست (همیشه 200، بدون 401 کنسول).
 *
 * برای بوت اسپای وقتی توکن محلی و پرچم نشست وجود ندارد: کاربرِ برگشته از مسیر
 * SSO رز هاب فقط کوکی refresh (HttpOnly) دارد؛ پراپ می‌گوید آیا نشست زنده‌ای
 * پشت کوکی هست تا توکن با /auth/refresh بازیابی شود — بدون آنکه برای
 * بازدیدکنندهٔ ناشناس خطایی در کنسول مرورگر بیفتد.
 */
export interface SessionProbe {
  authenticated: boolean;
  must_change_password?: boolean;
}

export async function probeSession(): Promise<SessionProbe> {
  const res = await apiClient.get<SessionProbe>("/auth/session-probe");
  return res.data;
}

export interface UserRow {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  mobile: string | null;
  status: string;
  must_change_password: boolean;
  roles: string[];
  /** فاز ۷۴: سازمان کاربر */
  organization_id: string | null;
  organization_name: string | null;
  last_login_at: string | null;
  created_at: string | null;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await apiClient.post<LoginResponse>("/auth/login", { username, password });
  return res.data;
}

// فاز ۶۴: ورود دو عاملی پیامکی — تا اتصال درگاه پیامک، کد در dev_code برمی‌گردد
export interface OtpRequestResponse {
  status: string;
  expires_in: number;
  dev_code?: string;
  dev_notice?: string;
}

export async function requestOtp(mobile: string): Promise<OtpRequestResponse> {
  const res = await apiClient.post<OtpRequestResponse>("/auth/otp/request", {
    mobile,
    purpose: "login",
  });
  return res.data;
}

export async function verifyOtp(mobile: string, code: string): Promise<LoginResponse> {
  const res = await apiClient.post<LoginResponse>("/auth/otp/verify", {
    mobile,
    code,
    purpose: "login",
  });
  return res.data;
}

export async function fetchMe(): Promise<Me> {
  const res = await apiClient.get<Me>("/auth/me");
  return res.data;
}

export async function logout(): Promise<void> {
  await apiClient.post("/auth/logout", {});
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiClient.post("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function activate(token: string, newPassword: string): Promise<void> {
  await apiClient.post("/auth/activate", { token, new_password: newPassword });
}

export async function fetchUsers(params: { search?: string; page: number; page_size: number }): Promise<{
  items: UserRow[];
  total: number;
  page: number;
  page_size: number;
}> {
  const res = await apiClient.get("/users", { params });
  // فاز ۳۹ (v2): data آرایه + total/page/page_size در meta.pagination
  return { items: res.data, ...paginationOf(res) } as {
    items: UserRow[];
    total: number;
    page: number;
    page_size: number;
  };
}

export async function createUser(payload: {
  username: string;
  display_name: string;
  email?: string;
  mobile?: string;
  roles: string[];
  organization_id?: string | null;
}): Promise<UserRow> {
  const res = await apiClient.post("/users", payload);
  return res.data;
}

export async function updateUserStatus(id: string, status: string): Promise<UserRow> {
  const res = await apiClient.patch(`/users/${id}`, { status });
  return res.data;
}

/** فاز ۷۴: انتساب/تغییر سازمان کاربر توسط مدیر سامانه */
export async function updateUserOrganization(id: string, organizationId: string | null): Promise<UserRow> {
  const res = await apiClient.patch(`/users/${id}`, { organization_id: organizationId ?? "" });
  return res.data;
}

export async function createActivationToken(
  id: string
): Promise<{ token: string; expires_at: string }> {
  const res = await apiClient.post(`/users/${id}/activation-token`);
  return res.data;
}

/** فاز ۵۲: تغییر نقش‌های کاربر از پنل */
export async function setUserRoles(id: string, roles: string[]): Promise<UserRow> {
  const res = await apiClient.put(`/users/${id}/roles`, { roles });
  return res.data;
}

/** فاز ۵۲: بازنشانی رمز توسط مدیر — رمز جدید را همان‌جا تعیین می‌کنیم */
export async function resetUserPassword(
  id: string,
  newPassword: string,
  mustChange = true
): Promise<{ ok: boolean; username: string }> {
  const res = await apiClient.post(`/users/${id}/reset-password`, {
    new_password: newPassword,
    must_change_password: mustChange,
  });
  return res.data;
}

/** فاز ۶۰: ورود مدیر با هویت کاربر (impersonation) — توکن مستقل برای کاربر هدف */
export async function impersonateUser(
  id: string
): Promise<{ access_token: string; token_type: string; expires_in_minutes: number; user: UserRow }> {
  const res = await apiClient.post(`/users/${id}/impersonate`, {});
  return res.data;
}
