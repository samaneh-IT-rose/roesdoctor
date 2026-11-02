import { apiClient } from "./client";

/** فاز ۵۲ - RBAC گرافیکی: کاتالوگ دسترسی‌ها + نقش‌ها + ماتریس */

export interface PermissionItem {
  code: string;
  title: string;
}

export interface PermissionSection {
  section: string;
  permissions: PermissionItem[];
}

export interface RoleRow {
  code: string;
  title: string;
  data_scope: string;
  data_scope_title: string;
  permissions: string[];
  is_system: boolean;
  member_count?: number;
}

export async function fetchPermissionCatalog(): Promise<PermissionSection[]> {
  const res = await apiClient.get<{ sections: PermissionSection[]; total: number }>("/rbac/permissions");
  return res.data.sections;
}

export async function fetchRoles(): Promise<RoleRow[]> {
  const res = await apiClient.get<{ items: RoleRow[] }>("/rbac/roles");
  return res.data.items;
}

export async function saveRolePermissions(
  code: string,
  payload: { title: string; data_scope: string; permissions: string[] },
): Promise<RoleRow> {
  const res = await apiClient.put<RoleRow>(`/rbac/roles/${encodeURIComponent(code)}`, payload);
  return res.data;
}

export async function createRole(
  code: string,
  payload: { title: string; data_scope: string; permissions: string[] },
): Promise<RoleRow> {
  const res = await apiClient.post<RoleRow>(`/rbac/roles/${encodeURIComponent(code)}`, payload);
  return res.data;
}

export async function deleteRole(code: string): Promise<void> {
  await apiClient.delete(`/rbac/roles/${encodeURIComponent(code)}`);
}

export const DATA_SCOPE_OPTIONS: { value: string; title: string; hint: string }[] = [
  { value: "all", title: "همهٔ داده‌ها", hint: "کاربر همهٔ رکوردهای سامانه را می‌بیند" },
  { value: "assigned", title: "داده‌های تخصیص‌یافته", hint: "فقط پرونده‌ها/نوبت‌های واگذارشده به کاربر" },
  { value: "own", title: "فقط داده‌های خودم", hint: "فقط رکوردهای ثبت‌شده توسط خود کاربر" },
];

export function dataScopeTitle(scope: string): string {
  return DATA_SCOPE_OPTIONS.find((o) => o.value === scope)?.title ?? scope;
}

// ---------------------------------------------------------------------------
// فاز ۷۱ — ماتریس منوها و زیرمنوها (دیدن / خواندن / ویرایش) برای هر نقش
// ---------------------------------------------------------------------------
export type MenuLevel = "view" | "read" | "edit";

export interface MenuItemDef {
  key: string;
  title: string;
  path: string;
  /** داده‌های شخصی خود کاربر است — ماتریس فقط «نمایش منو» را کنترل می‌کند */
  self_service: boolean;
}

export interface MenuGroupDef {
  key: string;
  title: string;
  items: MenuItemDef[];
}

export interface MenuCatalog {
  groups: MenuGroupDef[];
  levels: { value: MenuLevel; title: string }[];
  total: number;
}

export interface RoleMenus {
  role_code: string;
  menus: Record<string, MenuLevel>;
  locked: boolean;
  changed?: string[];
}

export async function fetchMenuCatalog(): Promise<MenuCatalog> {
  const res = await apiClient.get<MenuCatalog>("/rbac/menu-catalog");
  return res.data;
}

export async function fetchRoleMenus(code: string): Promise<RoleMenus> {
  const res = await apiClient.get<RoleMenus>(`/rbac/roles/${encodeURIComponent(code)}/menus`);
  return res.data;
}

export async function saveRoleMenus(code: string, menus: Record<string, MenuLevel | null>): Promise<RoleMenus> {
  const res = await apiClient.put<RoleMenus>(`/rbac/roles/${encodeURIComponent(code)}/menus`, { menus });
  return res.data;
}

/** برچسب فارسی سطوح — ترتیب ستون‌های ماتریس گرافیکی */
export const MENU_LEVEL_OPTIONS: { value: MenuLevel | "none"; title: string; hint: string }[] = [
  { value: "none", title: "هیچ", hint: "منو پنهان و دسترسی API بخش مسدود است" },
  { value: "view", title: "دیدن", hint: "منو دیده می‌شود و فهرست/صفحهٔ اصلی بخش باز است" },
  { value: "read", title: "فقط خواندن", hint: "جزئیات رکوردها هم قابل مشاهده است؛ بدون تغییر" },
  { value: "edit", title: "ویرایش", hint: "ثبت/ویرایش/حذف در آن بخش (شامل سطح‌های پایین‌تر)" },
];

export const MENU_LEVEL_TITLES: Record<string, string> = {
  view: "دیدن",
  read: "فقط خواندن",
  edit: "ویرایش",
};
