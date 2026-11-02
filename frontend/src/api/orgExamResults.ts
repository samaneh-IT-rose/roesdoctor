// فاز ۷۴ - آزمون‌های برگزارشده سازمانی: فهرست برنامه‌ها + نتایج اعضا
// مدیر سازمان فقط برنامه‌های سازمان خودش را می‌بیند (اسکوپ سمت سرور)
import { apiClient } from "./client";

export type OrgExamResultStatus = "draft" | "active" | "closed";

export interface OrgExamResultSummary {
  id: string;
  organization_id: string;
  organization_name: string | null;
  title: string;
  description: string | null;
  status: OrgExamResultStatus;
  due_date: string | null;
  tests_count: number;
  members_count: number;
  completed_members: number;
  progress_percent: number;
  created_at: string | null;
}

export interface OrgExamResultTest {
  test_id: string;
  slug: string;
  title: string;
  code: string | null;
}

export interface OrgExamResultMemberTest {
  test_id: string;
  title: string;
  done: boolean;
  score: number | null;
  interpretation_label: string | null;
  completed_at: string | null;
}

export interface OrgExamResultMember {
  id: string;
  user_id: string | null;
  username: string | null;
  full_name: string;
  employee_code: string | null;
  unit: string | null;
  done_count: number;
  total_tests: number;
  progress_percent: number;
  tests: OrgExamResultMemberTest[];
}

export interface OrgExamResultDetail extends OrgExamResultSummary {
  tests: OrgExamResultTest[];
  members: OrgExamResultMember[];
}

export async function fetchOrgExamResults(params?: {
  status?: string;
  q?: string;
}): Promise<OrgExamResultSummary[]> {
  const r = await apiClient.get<{ items: OrgExamResultSummary[] }>("/org-exam-results", { params });
  return r.data.items ?? [];
}

export async function fetchOrgExamResultDetail(id: string): Promise<OrgExamResultDetail> {
  const r = await apiClient.get<OrgExamResultDetail>(`/org-exam-results/${id}`);
  return r.data;
}
