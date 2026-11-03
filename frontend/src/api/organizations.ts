// فاز ۳۳ - B21 سند جامع: سازمان‌ها، قراردادها و سهم پرداخت
import { apiClient } from "./client";

export interface ActiveContractRef {
  id: string;
  title: string;
  coverage_percent: number;
  valid_from: string;
  valid_to: string | null;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  national_id: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  note: string | null;
  is_active: boolean;
  /** فاز ۷۵ — برندینگ آزمون سازمانی */
  brand_name: string | null;
  brand_logo_url: string | null;
  entry_title: string | null;
  entry_note: string | null;
  contract_count: number;
  active_contract: ActiveContractRef | null;
  /** فاز ۶۲: null = قرارداد فعال ندارد؛ [] = همه آزمون‌ها باز؛ لیست = فقط همین‌ها */
  open_tests: ContractTestRef[] | null;
  created_at: string | null;
}

export interface ContractServiceRef {
  id: string;
  title: string;
}

// فاز ۶۲: آزمون‌های باز قرارداد/سازمان
export interface ContractTestRef {
  id: string;
  title: string;
}

export interface Contract {
  id: string;
  organization_id: string;
  organization_name: string | null;
  title: string;
  coverage_percent: number;
  coverage_cap_amount: number | null;
  valid_from: string;
  valid_to: string | null;
  status: "draft" | "active" | "terminated";
  notes: string | null;
  services: ContractServiceRef[];
  /** فاز ۶۲: آزمون‌های باز این قرارداد؛ خالی = همه آزمون‌ها */
  tests: ContractTestRef[];
  created_at: string | null;
}

export interface ReceivableRow {
  order_id: string;
  order_number: string;
  title: string;
  amount: number;
  coverage_percent: number | null;
  org_share_amount: number;
  applicant_share_amount: number;
  status: string;
  created_at: string | null;
}

export interface OrgStatementRef {
  id: string;
  statement_no: string;
  period_from: string;
  period_to: string;
  status: "issued" | "settled";
  orders_count: number;
  org_share_total: number;
  created_at: string | null;
}

export interface ReceivablesReport {
  organization_id: string;
  organization_name: string;
  paid_orders_with_share: number;
  total_amount: number;
  org_share_total: number;
  applicant_share_total: number;
  settled_total: number;
  issued_unsettled_total: number;
  outstanding_total: number;
  statements: OrgStatementRef[];
  items: ReceivableRow[];
}

export async function fetchOrganizations(): Promise<Organization[]> {
  const r = await apiClient.get<{ items: Organization[] }>("/organizations");
  return r.data.items;
}

export async function createOrganization(payload: Record<string, unknown>): Promise<Organization> {
  const r = await apiClient.post<Organization>("/organizations", payload);
  return r.data;
}

export async function updateOrganization(id: string, payload: Record<string, unknown>): Promise<Organization> {
  const r = await apiClient.patch<Organization>(`/organizations/${id}`, payload);
  return r.data;
}

/** فاز ۷۵ — آپلود لوگوی سازمان (PNG/JPG/WEBP، حداکثر ۲MB) */
export async function uploadOrgLogo(id: string, file: File): Promise<Organization> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await apiClient.post<Organization>(`/organizations/${id}/logo`, fd);
  return r.data;
}

export async function deleteOrgLogo(id: string): Promise<void> {
  await apiClient.delete(`/organizations/${id}/logo`);
}

export async function fetchContracts(orgId: string): Promise<Contract[]> {
  const r = await apiClient.get<{ items: Contract[] }>(`/organizations/${orgId}/contracts`);
  return r.data.items;
}

export async function createContract(orgId: string, payload: Record<string, unknown>): Promise<Contract> {
  const r = await apiClient.post<Contract>(`/organizations/${orgId}/contracts`, payload);
  return r.data;
}

export async function updateContract(id: string, payload: Record<string, unknown>): Promise<Contract> {
  const r = await apiClient.patch<Contract>(`/contracts/${id}`, payload);
  return r.data;
}

export async function fetchReceivables(orgId: string): Promise<ReceivablesReport> {
  const r = await apiClient.get<ReceivablesReport>(`/organizations/${orgId}/receivables`);
  return r.data;
}

// ---------------------------------------------------------------- فاز ۳۴ - B21-plus: صورتحساب دوره‌ای
export interface StatementItem {
  order_id: string;
  order_number: string;
  amount: number;
  org_share_amount: number;
  applicant_share_amount: number;
  coverage_percent: number | null;
}

export interface OrgStatement {
  id: string;
  statement_no: string;
  organization_id: string;
  period_from: string;
  period_to: string;
  status: "issued" | "settled";
  orders_count: number;
  total_amount: number;
  org_share_total: number;
  applicant_share_total: number;
  currency: string;
  journal_entry_id: string | null;
  note: string | null;
  settled_at: string | null;
  created_at: string | null;
  items: StatementItem[];
}

export async function fetchStatements(orgId: string): Promise<OrgStatement[]> {
  const r = await apiClient.get<{ items: OrgStatement[] }>(`/organizations/${orgId}/statements`);
  return r.data.items;
}

export async function createStatement(
  orgId: string,
  payload: { period_from: string; period_to: string; note?: string },
): Promise<OrgStatement> {
  const r = await apiClient.post<OrgStatement>(`/organizations/${orgId}/statements`, payload);
  return r.data;
}

export async function settleStatement(statementId: string): Promise<OrgStatement> {
  const r = await apiClient.post<OrgStatement>(`/statements/${statementId}/settle`, {});
  return r.data;
}
