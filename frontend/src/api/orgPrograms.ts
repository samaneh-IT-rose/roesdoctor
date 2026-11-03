// فاز ۵۸ - پنل آزمون‌های سازمانی: برنامهٔ ارزیابی سازمان + کارتابل
import { apiClient } from "./client";

export type OrgProgramStatus = "draft" | "active" | "closed";

export interface OrgProgramSummary {
  id: string;
  organization_id: string;
  organization_name: string | null;
  organization_slug: string | null;
  title: string;
  description: string | null;
  status: OrgProgramStatus;
  due_date: string | null;
  tests_count: number;
  members_count: number;
  counselors_count: number;
  faq_count: number;
  progress_percent: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface OrgProgramTestItem {
  id: string;
  test_id: string;
  slug: string;
  title: string;
  /** فاز ۷۵ — عنوان نمایشی برای شرکت‌کنندگان برنامه */
  display_title: string | null;
  /** فاز ۷۵ — عنوان مؤثر (display_title یا title) */
  effective_title?: string | null;
  code: string | null;
  description: string | null;
  topic_name: string | null;
  accent_color: string | null;
  estimated_minutes: number | null;
  is_required: boolean;
  sort_order: number;
}

export interface OrgProgramCounselorItem {
  id: string;
  user_id: string;
  display_name: string | null;
  username: string | null;
  role_in_project: string;
}

export interface OrgProgramMemberItem {
  id: string;
  user_id: string | null;
  username: string | null;
  full_name: string;
  employee_code: string | null;
  mobile: string | null;
  unit: string | null;
  note: string | null;
  done_count: number;
  total_tests: number;
  progress_percent: number;
  created_at: string | null;
}

export interface OrgProgramFaqItem {
  id: string;
  question: string;
  answer: string;
  sort_order: number;
}

/** کارتابل برنامهٔ سازمانی — همهٔ اجزا یک‌جا */
export interface OrgProgramWorkdesk {
  id: string;
  organization_id: string;
  organization_name: string | null;
  organization_slug: string | null;
  title: string;
  description: string | null;
  guide_text: string | null;
  status: OrgProgramStatus;
  due_date: string | null;
  tests_count: number;
  members_count: number;
  counselors_count: number;
  faq_count: number;
  progress_percent: number;
  tests: OrgProgramTestItem[];
  counselors: OrgProgramCounselorItem[];
  members: OrgProgramMemberItem[];
  faqs: OrgProgramFaqItem[];
  created_at: string | null;
  updated_at: string | null;
}

export async function fetchOrgPrograms(params?: {
  organization_id?: string;
  status?: string;
  q?: string;
}): Promise<OrgProgramSummary[]> {
  const r = await apiClient.get<{ items: OrgProgramSummary[] }>("/org-programs", { params });
  return r.data.items;
}

export async function fetchOrgProgramWorkdesk(id: string): Promise<OrgProgramWorkdesk> {
  const r = await apiClient.get<OrgProgramWorkdesk>(`/org-programs/${id}`);
  return r.data;
}

export async function createOrgProgram(payload: Record<string, unknown>): Promise<OrgProgramSummary> {
  const r = await apiClient.post<OrgProgramSummary>("/org-programs", payload);
  return r.data;
}

export async function updateOrgProgram(id: string, payload: Record<string, unknown>): Promise<OrgProgramSummary> {
  const r = await apiClient.patch<OrgProgramSummary>(`/org-programs/${id}`, payload);
  return r.data;
}

export async function deleteOrgProgram(id: string): Promise<void> {
  await apiClient.delete(`/org-programs/${id}`);
}

export async function setOrgProgramTests(
  id: string,
  testIds: string[],
  items?: { test_id: string; display_title: string | null }[],
): Promise<void> {
  // فاز ۷۵ — در حالت items عنوان نمایشی هر آزمون هم ذخیره می‌شود
  await apiClient.put(`/org-programs/${id}/tests`,
    items ? { items } : { test_ids: testIds });
}

export async function addOrgProgramMember(
  id: string,
  payload: { full_name: string; employee_code?: string; mobile?: string; unit?: string; note?: string; user_id?: string },
): Promise<OrgProgramMemberItem> {
  const r = await apiClient.post<OrgProgramMemberItem>(`/org-programs/${id}/members`, payload);
  return r.data;
}

export async function removeOrgProgramMember(id: string, memberId: string): Promise<void> {
  await apiClient.delete(`/org-programs/${id}/members/${memberId}`);
}

export async function addOrgProgramCounselor(
  id: string,
  payload: { user_id: string; role_in_project?: string },
): Promise<OrgProgramCounselorItem> {
  const r = await apiClient.post<OrgProgramCounselorItem>(`/org-programs/${id}/counselors`, payload);
  return r.data;
}

export async function removeOrgProgramCounselor(id: string, counselorId: string): Promise<void> {
  await apiClient.delete(`/org-programs/${id}/counselors/${counselorId}`);
}

export async function setOrgProgramFaq(
  id: string,
  items: { question: string; answer: string }[],
): Promise<void> {
  await apiClient.put(`/org-programs/${id}/faq`, { items });
}
