// فاز ۷۰ - پروندهٔ مشاورهٔ کاربر — تاریخچهٔ آزمون‌ها و مشاوره‌ها با زمان
import { apiClient } from "./client";

export interface CounselingFileItem {
  kind: "psych_test" | "consultation" | "appointment";
  id: string;
  title: string;
  at: string | null;
  score?: number;
  interpretation_label?: string;
  viewed?: boolean;
  case_id?: string | null;
  test_slug?: string | null;
  status?: string;
  payment_status?: string;
  preferred_start_at?: string | null;
  case_number?: string | null;
  location?: string | null;
}

export interface CounselingFileOut {
  file: {
    id: string;
    file_code: string;
    staff_note: string | null;
    created_at: string | null;
    last_activity_at: string | null;
  };
  user: {
    id: string;
    display_name: string;
    username: string;
    mobile: string | null;
  };
  counts: { psych_tests: number; consultations: number; appointments: number };
  items: CounselingFileItem[];
}

export interface CounselingFileRow {
  user_id: string;
  file_code: string;
  display_name: string;
  username: string;
  mobile: string | null;
  attempt_count: number;
  last_activity_at: string | null;
  created_at: string | null;
  staff_note: string | null;
}

/** پروندهٔ مشاورهٔ خودِ کاربر (هر حساب واردشده). */
export async function fetchMyCounselingFile(): Promise<CounselingFileOut> {
  const r = await apiClient.get<CounselingFileOut>("/me/counseling-file");
  return r.data;
}

/** فهرست پرونده‌های کاربران (کارکنان). */
export async function fetchCounselingFiles(q = ""): Promise<CounselingFileRow[]> {
  const r = await apiClient.get<{ items: CounselingFileRow[] }>("/counseling-files", {
    params: q ? { q } : {},
  });
  return r.data.items;
}

/** جزئیات پروندهٔ یک کاربر (کارکنان). */
export async function fetchCounselingFileDetail(userId: string): Promise<CounselingFileOut> {
  const r = await apiClient.get<CounselingFileOut>(`/counseling-files/${userId}`);
  return r.data;
}
