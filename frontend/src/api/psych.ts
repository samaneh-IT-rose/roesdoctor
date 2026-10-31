// فاز ۳۵ - B37 سند جامع: تست روان‌شناسی و تفسیر (D08: ناظر علمی)
import { apiClient } from "./client";

export interface PsychTest {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  topic_id: string | null;
  topic_name: string | null;
  // فاز ۵۰ - متادیتای کاتالوگ مرجع
  code?: string | null;
  age_range?: string | null;
  estimated_minutes?: number | null;
  accent_color?: string | null;
  sort_order?: number;
  status: "draft" | "pending_review" | "published" | "rejected";
  review_note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  question_count?: number;
  interpretation_count?: number;
  attempt_count?: number;
  created_at: string | null;
}

export interface PsychQuestion {
  id: string;
  test_id: string;
  prompt: string;
  options: { label: string; score: number }[];
  subscale?: string | null;
  image_url?: string | null;
  sort_order: number;
}

export interface PsychInterpretation {
  id: string;
  test_id: string;
  score_min: number;
  score_max: number;
  label: string;
  guidance: string | null;
  sort_order: number;
}

export interface PsychAttempt {
  id: string;
  test_id: string;
  user_id: string;
  score: number;
  interpretation_label: string;
  interpretation_guidance: string | null;
  subscale_scores?: Record<string, number> | null;
  demographics?: Record<string, string> | null;
  // فاز ۶۳ - گزارش تحلیلی چندلایه (snapshot)
  result_payload?: ReportPayload | null;
  test_title?: string | null;
  // فاز ۷۰ - نتیجهٔ دیده‌شده + پروندهٔ متصل
  viewed_at?: string | null;
  case_id?: string | null;
  // فاز ۷۰ - فهرست سراسری کارکنان (psych-attempts)
  test_slug?: string | null;
  user_display_name?: string | null;
  user_username?: string | null;
  user_mobile?: string | null;
  case_number?: string | null;
  created_at: string | null;
}

// فاز ۶۳ - ساختار گزارش تحلیلی (مدل مرجع ای‌سنج)
export interface ReportScale {
  key: string;
  title: string;
  description?: string | null;
  color?: string | null;
  direction: "higher_worse" | "higher_better" | "balanced";
  score: number;
  max: number;
  percent: number;
  level: { label: string; text: string | null; guidance: string | null } | null;
  children: ReportScale[] | null;
}

export interface ReportPayload {
  version: number;
  total: { score: number; max: number; label: string | null; guidance: string | null };
  dominant: { key: string; title: string; percent: number } | null;
  scales: ReportScale[];
}

// فاز ۵۰ - مشخصات اولیه برگزارکننده (فرم مرجع)
export interface TestDemographics {
  gender?: string;
  age?: string;
  education?: string;
  marital?: string;
}

// فاز ۴۷ - مرکز آزمون: کاتالوگ عمومی + برگه پرسش‌نامه + اجرا
export interface PublicPsychTest {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  topic_name: string | null;
  code?: string | null;
  age_range?: string | null;
  estimated_minutes?: number | null;
  accent_color?: string | null;
  sort_order?: number;
  question_count: number;
}

export interface PublicPaper {
  test: {
    id: string; slug: string; title: string; description: string | null;
    code?: string | null; age_range?: string | null; estimated_minutes?: number | null; accent_color?: string | null;
  };
  questions: {
    id: string; prompt: string; subscale?: string | null; options: string[];
    image_url?: string | null; sort_order: number;
  }[];
}

export interface AttemptResult {
  attempt: PsychAttempt;
  disclaimer: string;
}

export async function fetchPublicPsychTests(): Promise<PublicPsychTest[]> {
  const r = await apiClient.get<{ items: PublicPsychTest[] }>("/public/psych-tests");
  return r.data.items;
}

export async function fetchPublicPaper(slug: string): Promise<PublicPaper> {
  const r = await apiClient.get<PublicPaper>(`/public/psych-tests/${slug}/paper`);
  return r.data;
}

export async function submitPsychAttempt(
  slug: string,
  answers: number[],
  demographics?: TestDemographics | null,
): Promise<AttemptResult> {
  const r = await apiClient.post<AttemptResult>(`/public/psych-tests/${slug}/attempts`, {
    answers,
    demographics: demographics && Object.keys(demographics).length ? demographics : null,
  });
  return r.data;
}

export async function fetchPsychTests(): Promise<PsychTest[]> {
  const r = await apiClient.get<{ items: PsychTest[] }>("/psych-tests");
  return r.data.items;
}

export async function createPsychTest(payload: Record<string, unknown>): Promise<PsychTest> {
  const r = await apiClient.post<PsychTest>("/psych-tests", payload);
  return r.data;
}

export async function updatePsychTest(id: string, payload: Record<string, unknown>): Promise<PsychTest> {
  const r = await apiClient.patch<PsychTest>(`/psych-tests/${id}`, payload);
  return r.data;
}

export async function submitPsychTestForReview(id: string): Promise<PsychTest> {
  const r = await apiClient.post<PsychTest>(`/psych-tests/${id}/submit-review`, {});
  return r.data;
}

export async function reviewPsychTest(
  id: string,
  payload: { approve: boolean; note?: string },
): Promise<PsychTest> {
  const r = await apiClient.post<PsychTest>(`/psych-tests/${id}/review`, payload);
  return r.data;
}

export async function fetchPsychQuestions(testId: string): Promise<PsychQuestion[]> {
  const r = await apiClient.get<{ items: PsychQuestion[] }>(`/psych-tests/${testId}/questions`);
  return r.data.items;
}

export async function addPsychQuestion(
  testId: string,
  payload: { prompt: string; options: { label: string; score: number }[]; subscale?: string | null },
): Promise<PsychQuestion> {
  const r = await apiClient.post<PsychQuestion>(`/psych-tests/${testId}/questions`, payload);
  return r.data;
}

export async function fetchInterpretations(testId: string): Promise<PsychInterpretation[]> {
  const r = await apiClient.get<{ items: PsychInterpretation[] }>(`/psych-tests/${testId}/interpretations`);
  return r.data.items;
}

export async function addInterpretation(
  testId: string,
  payload: { score_min: number; score_max: number; label: string; guidance?: string },
): Promise<PsychInterpretation> {
  const r = await apiClient.post<PsychInterpretation>(`/psych-tests/${testId}/interpretations`, payload);
  return r.data;
}

export async function fetchPsychAttempts(testId: string): Promise<PsychAttempt[]> {
  const r = await apiClient.get<{ items: PsychAttempt[] }>(`/psych-tests/${testId}/attempts`);
  return r.data.items;
}

export async function fetchMyPsychResults(): Promise<PsychAttempt[]> {
  const r = await apiClient.get<{ items: PsychAttempt[] }>("/my/psych-results");
  return r.data.items;
}

// ====================================================== فاز ۷۰
/** ثبت «دیده‌شدن» نتیجهٔ آزمون توسط خود کاربر (زمان اولین بازدید می‌ماند). */
export async function markAttemptViewed(attemptId: string): Promise<void> {
  await apiClient.post(`/my/psych-results/${attemptId}/viewed`, {});
}

/** فهرست سراسری «آزمون‌های برگزارشده» برای کارکنان (فیلتر اختیاری). */
export async function fetchPsychAttemptsAll(params?: { test_id?: string; q?: string }): Promise<PsychAttempt[]> {
  const r = await apiClient.get<{ items: PsychAttempt[] }>("/psych-attempts", { params });
  return r.data.items;
}

/** ایجاد پرونده برای آزمون‌دهنده از روی اجرای آزمون. */
export async function createCaseFromAttempt(attemptId: string): Promise<{
  case_id: string; case_number: string; case_created: boolean;
  applicant_id: string; applicant_created: boolean; linked_attempts: number;
}> {
  const r = await apiClient.post(`/psych-attempts/${attemptId}/create-case`, {});
  return r.data;
}

/** نتایج آزمون‌های متصل به یک پرونده (تب «نتایج آزمون»). */
export async function fetchCasePsychAttempts(caseId: string): Promise<PsychAttempt[]> {
  const r = await apiClient.get<{ items: PsychAttempt[] }>(`/cases/${caseId}/psych-attempts`);
  return r.data.items;
}
