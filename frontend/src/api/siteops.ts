import { apiClient, paginationOf } from "./client";

export interface ConsultationRow {
  id: string;
  full_name: string;
  mobile: string;
  topic: string;
  preferred_date: string | null;
  preferred_slot: string | null;
  message: string | null;
  status: string;
  created_at: string | null;
  handled_by_name: string | null;
  reception_note: string | null;
  contact_attempts: number;
  city: string | null;
  referral_source: string | null;
  preferred_counselor_id: string | null;
  preferred_start_at: string | null;
  /** فاز ۶۹: وضعیت پرداخت آنلاین رزرو (زرین‌پال) */
  payment_status: string;
  paid_at: string | null;
}

export const CONSULT_PAYMENT_META: Record<string, { label: string; color: "success" | "warning" | "error" | "default" }> = {
  not_required: { label: "بدون پرداخت آنلاین", color: "default" },
  pending: { label: "در انتظار پرداخت", color: "warning" },
  paid: { label: "پرداخت شده ✓", color: "success" },
  failed: { label: "پرداخت ناموفق", color: "error" },
};

export const CONSULT_STATUS_META: Record<string, { label: string; color: "success" | "warning" | "info" | "default" }> = {
  new: { label: "جدید", color: "warning" },
  in_review: { label: "در حال بررسی", color: "info" },
  converted: { label: "تبدیل به متقاضی", color: "success" },
  archived: { label: "بایگانی", color: "default" },
};

export async function fetchConsultationRequests(params: {
  status?: string;
  page: number;
}): Promise<{ items: ConsultationRow[]; total: number }> {
  // فاز ۳۹ (v2): data آرایه + total در meta.pagination
  const r = await apiClient.get("/consultation-requests", { params: { ...params, page_size: 20 } });
  return { items: r.data, total: Number(paginationOf(r).total ?? 0) };
}

export async function updateConsultationRequest(
  id: string,
  payload: { status: string; reception_note?: string; add_contact_attempt?: boolean }
): Promise<void> {
  await apiClient.patch(`/consultation-requests/${id}`, payload);
}

export async function createManualConsultationRequest(payload: {
  full_name: string;
  mobile: string;
  topic: string;
  preferred_date?: string;
  preferred_slot?: string;
  city?: string;
  referral_source?: string;
  message?: string;
  reception_note?: string;
}): Promise<{ id: string }> {
  return (await apiClient.post("/consultation-requests", payload)).data;
}

export async function uploadCounselorPhoto(id: string, file: File): Promise<void> {
  const fd = new FormData();
  fd.append("file", file);
  await apiClient.post(`/counselors/${id}/photo`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export async function fetchIntake(crId: string): Promise<{
  exists: boolean;
  status: string | null;
  data: Record<string, string | undefined>;
  filled_by_name: string | null;
  updated_at: string | null;
}> {
  return (await apiClient.get(`/consultation-requests/${crId}/intake`)).data;
}

export async function saveIntake(crId: string, data: Record<string, unknown>): Promise<unknown> {
  return (await apiClient.post(`/consultation-requests/${crId}/intake`, { data })).data;
}

export async function finalizeIntake(crId: string): Promise<unknown> {
  return (await apiClient.post(`/consultation-requests/${crId}/intake/finalize`, {})).data;
}