// فاز ۳۳/۳۴ - B21 + B21-plus: سازمان‌ها/قراردادها + صورتحساب دوره‌ای و تسویه مطالبات
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControl,
  InputLabel, ListItemText, MenuItem, OutlinedInput, Paper, Select, Snackbar, Stack, Switch,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useMemo, useRef, useState } from "react";
import { errDetail } from "../api/client";
import JalaliDateField from "../components/JalaliDateField";
import { formatJalali } from "../utils/jalali";
import { fetchAllServices } from "../api/branches";
import { fetchPsychTests, type PsychTest } from "../api/psych";
import {
  Contract, Organization, ReceivablesReport, createContract, createOrganization,
  createStatement, deleteOrgLogo, fetchContracts, fetchOrganizations, fetchReceivables,
  settleStatement, updateContract, updateOrganization, uploadOrgLogo,
} from "../api/organizations";

const fa = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : typeof n === "number" ? n.toLocaleString("fa-IR") : n;

const C_STATUS: Record<string, { label: string; color: "success" | "warning" | "default" }> = {
  active: { label: "فعال", color: "success" },
  draft: { label: "پیش‌نویس", color: "warning" },
  terminated: { label: "ملغی", color: "default" },
};

export default function OrganizationsPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [createOrgOpen, setCreateOrgOpen] = useState(false);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [newContractFor, setNewContractFor] = useState<Organization | null>(null);
  const [receivablesOrg, setReceivablesOrg] = useState<Organization | null>(null);
  // فاز ۷۵ — برندینگ آزمون سازمانی (عنوان/پیام صفحه ورودی + لوگو)
  const [brandingOrg, setBrandingOrg] = useState<Organization | null>(null);

  const orgs = useQuery({ queryKey: ["organizations"], queryFn: fetchOrganizations });
  const contracts = useQuery({
    queryKey: ["contracts", selectedOrg?.id],
    queryFn: () => fetchContracts(selectedOrg!.id),
    enabled: !!selectedOrg,
  });
  const services = useQuery({ queryKey: ["all-services"], queryFn: fetchAllServices });
  // فاز ۶۲: فهرست آزمون‌ها برای انتخاب «آزمون‌های باز سازمان» در قرارداد
  const psychTests = useQuery({ queryKey: ["psych-tests"], queryFn: () => fetchPsychTests() });
  const publishedTests = useMemo(
    () => (psychTests.data ?? []).filter((t) => t.status === "published"),
    [psychTests.data],
  );
  const receivables = useQuery({
    queryKey: ["receivables", receivablesOrg?.id],
    queryFn: () => fetchReceivables(receivablesOrg!.id),
    enabled: !!receivablesOrg,
  });

  const createOrgMut = useMutation({
    mutationFn: createOrganization,
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setCreateOrgOpen(false);
      setOkMsg(`سازمان «${o.name}» ایجاد شد`);
    },
    onError: (e) => setError(errDetail(e)),
  });
  const toggleOrgMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateOrganization(id, { is_active }),
    onSuccess: (o) => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setOkMsg(o.is_active ? "سازمان فعال شد" : "سازمان غیرفعال شد");
    },
    onError: (e) => setError(errDetail(e)),
  });
  const createContractMut = useMutation({
    mutationFn: ({ orgId, payload }: { orgId: string; payload: Record<string, unknown> }) =>
      createContract(orgId, payload),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setNewContractFor(null);
      setOkMsg(`قرارداد «${c.title}» ثبت شد (پیش‌نویس — پس از کنترل، فعال کنید)`);
    },
    onError: (e) => setError(errDetail(e)),
  });
  const setContractStatusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateContract(id, { status }),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["contracts"] });
      qc.invalidateQueries({ queryKey: ["organizations"] });
      setOkMsg(
        c.status === "active"
          ? "قرارداد فعال شد — سفارش‌های جدید با تقسیم سهم سازمان ساخته می‌شوند"
          : c.status === "terminated"
            ? "قرارداد ملغی شد — در سفارش‌های جدید اعمال نمی‌شود"
            : "وضعیت قرارداد تغییر کرد",
      );
    },
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>سازمان‌ها و قراردادها (B21)</Typography>
        <Box flexGrow={1} />
        <Button variant="contained" onClick={() => setCreateOrgOpen(true)}>سازمان جدید</Button>
      </Box>
      <Alert severity="info">
        قرارداد سازمان درصد سهم پرداخت سازمان را تعیین می‌کند؛ سهم در لحظه ساخت سفارش
        snapshot می‌شود و با تغییر قرارداد تغییر نمی‌کند. قرارداد و کد تخفیف هم‌زمان قابل
        استفاده نیستند. قرارداد منقضی/پیش‌نویس/ملغی اعمال نمی‌شود.
      </Alert>
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>سازمان</TableCell>
              <TableCell>slug</TableCell>
              <TableCell>شناسه ملی</TableCell>
              <TableCell>تلفن</TableCell>
              <TableCell>قرارداد فعال</TableCell>
              <TableCell>تعداد قرارداد</TableCell>
              <TableCell>فعال</TableCell>
              <TableCell align="left">عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(orgs.data ?? []).map((o) => (
              <TableRow
                key={o.id}
                hover
                selected={selectedOrg?.id === o.id}
                onClick={() => setSelectedOrg(o)}
                sx={{ cursor: "pointer", opacity: o.is_active ? 1 : 0.55 }}
              >
                <TableCell>{o.name}</TableCell>
                <TableCell dir="ltr" sx={{ fontFamily: "monospace", fontSize: 12 }}>{o.slug}</TableCell>
                <TableCell dir="ltr">{o.national_id ?? "—"}</TableCell>
                <TableCell dir="ltr">{o.phone ?? "—"}</TableCell>
                <TableCell>
                  {o.active_contract ? (
                    <Stack spacing={0.5}>
                      <Chip size="small" color="success" variant="outlined"
                            label={`${o.active_contract.title} — ${fa(o.active_contract.coverage_percent)}٪`} />
                      {/* فاز ۶۲: آزمون‌های باز این سازمان از قرارداد فعال */}
                      <Typography variant="caption" color="text.secondary">
                        {o.open_tests == null
                          ? "آزمون‌های باز: —"
                          : o.open_tests.length === 0
                            ? "آزمون‌های باز: همه آزمون‌ها"
                            : `آزمون‌های باز: ${fa(o.open_tests.length)} آزمون مشخص`}
                      </Typography>
                    </Stack>
                  ) : (
                    <Chip size="small" label="بدون قرارداد فعال" />
                  )}
                </TableCell>
                <TableCell>{fa(o.contract_count)}</TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Switch
                    size="small" checked={o.is_active}
                    onChange={(e) => toggleOrgMut.mutate({ id: o.id, is_active: e.target.checked })}
                  />
                </TableCell>
                <TableCell align="left" onClick={(e) => e.stopPropagation()}>
                  <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                    <Button size="small" onClick={() => setBrandingOrg(o)}>برندینگ آزمون</Button>
                    <Button size="small" onClick={() => setNewContractFor(o)}>قرارداد جدید</Button>
                    <Button size="small" onClick={() => setReceivablesOrg(o)}>مطالبات</Button>
                    <Button size="small" onClick={() => toggleOrgMut.mutate({ id: o.id, is_active: !o.is_active })}>
                      {o.is_active ? "غیرفعال" : "فعال"}
                    </Button>
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
            {(orgs.data ?? []).length === 0 && (
              <TableRow><TableCell colSpan={8} align="center" sx={{ py: 4, color: "text.secondary" }}>
                سازمانی ثبت نشده است.
              </TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {selectedOrg && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography fontWeight={700} mb={1}>
            قراردادهای «{selectedOrg.name}»
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>عنوان</TableCell>
                  <TableCell>سهم سازمان</TableCell>
                  <TableCell>سقف هر سفارش</TableCell>
                  <TableCell>اعتبار</TableCell>
                  <TableCell>دامنه خدمات</TableCell>
                  <TableCell>آزمون‌های باز</TableCell>
                  <TableCell>وضعیت</TableCell>
                  <TableCell align="left">عملیات</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(contracts.data ?? []).map((c) => (
                  <ContractRow key={c.id} c={c}
                               onStatus={(s) => setContractStatusMut.mutate({ id: c.id, status: s })} />
                ))}
                {(contracts.data ?? []).length === 0 && (
                  <TableRow><TableCell colSpan={8} align="center" sx={{ py: 3, color: "text.secondary" }}>
                    قراردادی ثبت نشده است.
                  </TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      <CreateOrgDialog
        open={createOrgOpen}
        loading={createOrgMut.isPending}
        onClose={() => setCreateOrgOpen(false)}
        onSubmit={(payload) => createOrgMut.mutate(payload)}
      />
      {/* فاز ۷۵ — برندینگ آزمون سازمانی */}
      <OrgBrandingDialog
        org={brandingOrg}
        onClose={() => setBrandingOrg(null)}
        onSaved={(m) => { setOkMsg(m); setBrandingOrg(null); }}
        onError={(e) => setError(e)}
      />
      <CreateContractDialog
        org={newContractFor}
        services={services.data ?? []}
        tests={publishedTests}
        loading={createContractMut.isPending}
        onClose={() => setNewContractFor(null)}
        onSubmit={(payload) => newContractFor && createContractMut.mutate({ orgId: newContractFor.id, payload })}
      />
      <ReceivablesDialog
        orgId={receivablesOrg?.id ?? ""}
        report={receivables.data ?? null}
        orgName={receivablesOrg?.name ?? ""}
        loading={receivables.isLoading}
        onClose={() => setReceivablesOrg(null)}
        onChanged={(m) => { setOkMsg(m); void qc.invalidateQueries({ queryKey: ["receivables"] }); }}
        onError={(e) => setError(errDetail(e))}
      />

      <Snackbar open={!!okMsg} autoHideDuration={4000} onClose={() => setOkMsg(null)}
                anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        <Alert severity="success" variant="filled">{okMsg}</Alert>
      </Snackbar>
    </Stack>
  );
}

function ContractRow({ c, onStatus }: { c: Contract; onStatus: (s: string) => void }) {
  const st = C_STATUS[c.status] ?? C_STATUS.draft;
  const scope = c.services.length === 0 ? "همه خدمات" : `${c.services.length} خدمت مشخص`;
  // فاز ۶۲: نمایش آزمون‌های باز قرارداد (خالی = همه)
  const testScope = c.tests.length === 0 ? "همه آزمون‌ها" : c.tests.map((t) => t.title).join("، ");
  return (
    <TableRow sx={{ opacity: c.status === "terminated" ? 0.55 : 1 }}>
      <TableCell>{c.title}</TableCell>
      <TableCell>{fa(c.coverage_percent)}٪</TableCell>
      <TableCell>{c.coverage_cap_amount ? fa(c.coverage_cap_amount) : "—"}</TableCell>
      {/* فاز ۵۹: نمایش شمسی بازهٔ اعتبار قرارداد */}
      <TableCell sx={{ fontSize: 12 }}>
        {formatJalali(c.valid_from)} ← {c.valid_to ? formatJalali(c.valid_to) : "∞"}
      </TableCell>
      <TableCell>{scope}</TableCell>
      <TableCell sx={{ maxWidth: 260 }}>
        {c.tests.length === 0 ? (
          <Typography variant="body2">همه آزمون‌ها</Typography>
        ) : (
          <Tooltip title={testScope} placement="top">
            <Chip size="small" variant="outlined" color="secondary"
                  label={`${fa(c.tests.length)} آزمون مشخص`} />
          </Tooltip>
        )}
      </TableCell>
      <TableCell><Chip size="small" color={st.color} label={st.label} /></TableCell>
      <TableCell align="left">
        <Stack direction="row" spacing={0.5} justifyContent="flex-end">
          {c.status === "draft" && (
            <Button size="small" color="success" onClick={() => onStatus("active")}>فعال‌سازی</Button>
          )}
          {c.status !== "terminated" && (
            <Button size="small" color="error" onClick={() => onStatus("terminated")}>لغو</Button>
          )}
        </Stack>
      </TableCell>
    </TableRow>
  );
}

function CreateOrgDialog({ open, loading, onClose, onSubmit }: {
  open: boolean; loading: boolean; onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      name, slug,
      national_id: nationalId || null,
      phone: phone || null, email: email || null, address: address || null,
    });
    setName(""); setSlug(""); setNationalId(""); setPhone(""); setEmail(""); setAddress("");
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>سازمان جدید (B21)</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField label="نام سازمان" required value={name} onChange={(e) => setName(e.target.value)} />
            <TextField label="slug (لاتین کوچک)" required dir="ltr" value={slug}
                       helperText="مثال: tehran-steel-co" onChange={(e) => setSlug(e.target.value)} />
            <TextField label="شناسه ملی (اختیاری، یکتا)" dir="ltr" value={nationalId}
                       onChange={(e) => setNationalId(e.target.value)} />
            <TextField label="تلفن" dir="ltr" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <TextField label="ایمیل" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} />
            <TextField label="نشانی" multiline minRows={2} value={address}
                       onChange={(e) => setAddress(e.target.value)} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ایجاد</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function CreateContractDialog({ org, services, tests, loading, onClose, onSubmit }: {
  org: Organization | null;
  services: { id: string; title: string; status: string }[];
  tests: PsychTest[];
  loading: boolean;
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  const [title, setTitle] = useState("");
  const [percent, setPercent] = useState(30);
  const [cap, setCap] = useState("");
  const [validFrom, setValidFrom] = useState(new Date().toISOString().slice(0, 10));
  const [validTo, setValidTo] = useState("");
  const [serviceIds, setServiceIds] = useState<string[]>([]);
  const [testIds, setTestIds] = useState<string[]>([]);
  if (!org) return null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({
      title, coverage_percent: percent,
      coverage_cap_amount: cap ? Number(cap) : null,
      valid_from: validFrom,
      valid_to: validTo || null,
      service_ids: serviceIds,
      // فاز ۶۲: خالی = همه آزمون‌ها برای سازمان باز باشد
      test_ids: testIds,
    });
    setTitle(""); setPercent(30); setCap(""); setServiceIds([]); setTestIds([]);
  };
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>قرارداد جدید برای «{org.name}»</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={1}>
            <TextField label="عنوان قرارداد" required value={title}
                       onChange={(e) => setTitle(e.target.value)} />
            <TextField label="درصد سهم سازمان (۱ تا ۱۰۰)" type="number" required value={percent}
                       inputProps={{ min: 1, max: 100 }}
                       helperText="سهم سازمان از هر سفارش؛ باقیمانده بر عهده متقاضی"
                       onChange={(e) => setPercent(Number(e.target.value))} />
            <TextField label="سقف سهم به‌ازای هر سفارش (اختیاری)" type="number" dir="ltr"
                       value={cap} onChange={(e) => setCap(e.target.value)} />
            {/* فاز ۵۹: تقویم شمسی به‌جای ورودی میلادی */}
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <JalaliDateField label="شروع اعتبار" required value={validFrom}
                               onChange={(iso) => setValidFrom(iso ?? "")} />
              <JalaliDateField label="پایان اعتبار (اختیاری)" value={validTo}
                               onChange={(iso) => setValidTo(iso ?? "")} />
            </Stack>
            <FormControl size="small">
              <InputLabel>دامنه خدمات (خالی = همه خدمات)</InputLabel>
              <Select multiple value={serviceIds}
                      onChange={(e) => setServiceIds(e.target.value as string[])}
                      input={<OutlinedInput label="دامنه خدمات (خالی = همه خدمات)" />}
                      renderValue={(sel) => (sel as string[])
                        .map((id) => services.find((s) => s.id === id)?.title ?? "؟").join("، ")}>
                {services.map((s) => (
                  <MenuItem key={s.id} value={s.id} disabled={s.status !== "active"}>
                    <ListItemText primary={s.title} />
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            {/* فاز ۶۲: کدام آزمون‌ها برای این سازمان باز باشد */}
            <FormControl size="small">
              <InputLabel>آزمون‌های باز برای سازمان (خالی = همه آزمون‌ها)</InputLabel>
              <Select multiple value={testIds}
                      onChange={(e) => setTestIds(e.target.value as string[])}
                      input={<OutlinedInput label="آزمون‌های باز برای سازمان (خالی = همه آزمون‌ها)" />}
                      renderValue={(sel) => (sel as string[]).length === 0
                        ? "همه آزمون‌ها"
                        : (sel as string[])
                          .map((id) => tests.find((t) => t.id === id)?.title ?? "؟").join("، ")}>
                {tests.map((t) => (
                  <MenuItem key={t.id} value={t.id}>
                    <ListItemText
                      primary={t.title}
                      secondary={t.code ? `کد: ${t.code}` : undefined}
                    />
                  </MenuItem>
                ))}
                {tests.length === 0 && (
                  <MenuItem disabled>آزمون منتشرشده‌ای یافت نشد</MenuItem>
                )}
              </Select>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
                اگر آزمونی انتخاب کنید، فقط همان آزمون‌ها برای اعضای این سازمان باز می‌شود.
              </Typography>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={loading}>ثبت قرارداد</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function ReceivablesDialog({ orgId, report, orgName, loading, onClose, onChanged, onError }: {
  orgId: string;
  report: ReceivablesReport | null;
  orgName: string;
  loading: boolean;
  onClose: () => void;
  onChanged: (msg: string) => void;
  onError: (e: unknown) => void;
}) {
  // فاز ۳۴ - B21-plus: صورتحساب دوره‌ای + تسویه مطالبات با سند ۱۱۰۴
  const [stFrom, setStFrom] = useState(new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10));
  const [stTo, setStTo] = useState(new Date().toISOString().slice(0, 10));
  const createStMut = useMutation({
    mutationFn: () => createStatement(orgId, { period_from: stFrom, period_to: stTo }),
    onSuccess: (st) => onChanged(`صورتحساب ${st.statement_no} صادر شد (${st.orders_count} سفارش — ${fa(st.org_share_total)} ریال)`),
    onError,
  });
  const settleMut = useMutation({
    mutationFn: (id: string) => settleStatement(id),
    onSuccess: (st) => onChanged(`صورتحساب ${st.statement_no} تسویه شد — سند Dr 1101 / Cr 1104 ثبت شد`),
    onError,
  });
  if (!report && !loading) return null;
  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>مطالبه از سازمان «{orgName}»</DialogTitle>
      <DialogContent>
        {loading && <Typography>در حال بارگذاری…</Typography>}
        {report && (
          <Stack spacing={2}>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <Paper variant="outlined" sx={{ p: 1.5, minWidth: 170 }}>
                <Typography variant="caption">سفارش پرداخت‌شده با سهم سازمان</Typography>
                <Typography fontWeight={800}>{fa(report.paid_orders_with_share)}</Typography>
              </Paper>
              <Paper variant="outlined" sx={{ p: 1.5, minWidth: 170 }}>
                <Typography variant="caption">مطالبه از سازمان (B21)</Typography>
                <Typography fontWeight={800} color="warning.main">{fa(report.org_share_total)}</Typography>
              </Paper>
              <Paper variant="outlined" sx={{ p: 1.5, minWidth: 170 }}>
                <Typography variant="caption">تسویه‌شده با سند ۱۱۰۴</Typography>
                <Typography fontWeight={800} color="success.main">{fa(report.settled_total)}</Typography>
              </Paper>
              <Paper variant="outlined" sx={{ p: 1.5, minWidth: 170 }}>
                <Typography variant="caption">مانده مطالبات</Typography>
                <Typography fontWeight={800} color="error.main">{fa(report.outstanding_total)}</Typography>
              </Paper>
            </Stack>
            <Paper variant="outlined" sx={{ p: 1.5 }}>
              <Typography variant="subtitle2" fontWeight={700} mb={1}>
                صورتحساب دوره‌ای سازمان (B21-plus) — تسویه سند می‌زند: بانک ۱۱۰۱ / دریافتنی سازمان ۱۱۰۴
              </Typography>
              {/* فاز ۵۹: بازهٔ صورتحساب با تقویم شمسی */}
              <Stack direction="row" spacing={1} mb={1} alignItems="flex-start">
                <JalaliDateField label="از تاریخ" value={stFrom}
                  onChange={(iso) => setStFrom(iso ?? stFrom)} />
                <JalaliDateField label="تا تاریخ" value={stTo}
                  onChange={(iso) => setStTo(iso ?? stTo)} />
                <Button variant="contained" onClick={() => createStMut.mutate()}
                  disabled={createStMut.isPending}>صدور صورتحساب</Button>
              </Stack>
              {report.statements.length > 0 && (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>شماره</TableCell><TableCell>بازه</TableCell>
                        <TableCell>سفارش‌ها</TableCell><TableCell>مبلغ</TableCell>
                        <TableCell>وضعیت</TableCell><TableCell> </TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {report.statements.map((st) => (
                        <TableRow key={st.id}>
                          <TableCell dir="ltr"><code>{st.statement_no}</code></TableCell>
                          <TableCell dir="ltr" sx={{ fontSize: 12 }}>{st.period_from} ← {st.period_to}</TableCell>
                          <TableCell>{fa(st.orders_count)}</TableCell>
                          <TableCell>{fa(st.org_share_total)}</TableCell>
                          <TableCell>
                            <Chip size="small" variant="outlined"
                              color={st.status === "settled" ? "success" : "warning"}
                              label={st.status === "settled" ? "تسویه‌شده" : "صادرشده"} />
                          </TableCell>
                          <TableCell>
                            {st.status === "issued" && (
                              <Button size="small" color="success"
                                onClick={() => settleMut.mutate(st.id)} disabled={settleMut.isPending}>
                                تسویه
                              </Button>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Paper>
            {report.items.length > 0 && (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>سفارش</TableCell>
                      <TableCell>مبلغ کل</TableCell>
                      <TableCell>درصد</TableCell>
                      <TableCell>سهم سازمان</TableCell>
                      <TableCell>سهم متقاضی</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {report.items.map((it) => (
                      <TableRow key={it.order_id}>
                        <TableCell>{it.order_number}</TableCell>
                        <TableCell>{fa(it.amount)}</TableCell>
                        <TableCell>{it.coverage_percent ? `${fa(it.coverage_percent)}٪` : "—"}</TableCell>
                        <TableCell>{fa(it.org_share_amount)}</TableCell>
                        <TableCell>{fa(it.applicant_share_amount)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions><Button onClick={onClose}>بستن</Button></DialogActions>
    </Dialog>
  );
}

/* ================= فاز ۷۵ — برندینگ آزمون سازمانی ================= */
function OrgBrandingDialog({
  org, onClose, onSaved, onError,
}: {
  org: Organization | null;
  onClose: () => void;
  onSaved: (msg: string) => void;
  onError: (msg: string) => void;
}) {
  const qc = useQueryClient();
  const [brandName, setBrandName] = useState("");
  const [entryTitle, setEntryTitle] = useState("");
  const [entryNote, setEntryNote] = useState("");
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // مقداردهی اولیه هنگام باز شدن دیالوگ برای هر سازمان
  if (org && loadedFor !== org.id) {
    setLoadedFor(org.id);
    setBrandName(org.brand_name ?? "");
    setEntryTitle(org.entry_title ?? "");
    setEntryNote(org.entry_note ?? "");
  }
  if (!org && loadedFor !== null) {
    setLoadedFor(null);
  }

  const saveMut = useMutation({
    mutationFn: () =>
      updateOrganization(org!.id, {
        brand_name: brandName,
        entry_title: entryTitle,
        entry_note: entryNote,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      onSaved("برندینگ آزمون سازمان ذخیره شد");
    },
    onError: (e) => onError(errDetail(e)),
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => uploadOrgLogo(org!.id, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      onSaved("لوگوی سازمان آپلود شد");
    },
    onError: (e) => onError(errDetail(e)),
  });

  const removeMut = useMutation({
    mutationFn: () => deleteOrgLogo(org!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organizations"] });
      onSaved("لوگو حذف شد");
    },
    onError: (e) => onError(errDetail(e)),
  });

  const pickFile = (f: File | null | undefined) => {
    if (!f) return;
    if (f.size > 2 * 1024 * 1024) {
      onError("حجم لوگو حداکثر ۲ مگابایت است");
      return;
    }
    uploadMut.mutate(f);
  };

  return (
    <Dialog open={!!org} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>برندینگ آزمون سازمانی — {org?.name ?? ""}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <Alert severity="info" variant="outlined" sx={{ py: 0.75 }}>
            این موارد در <b>صفحه ورودی آزمون‌های سازمانی</b> (کارتابل برنامه ← شروع آزمون) برای
            کارکنان سازمان نمایش داده می‌شود؛ عنوان نمایشی هر آزمون هم از کارتابل همان برنامه قابل تنظیم است.
          </Alert>
          <Stack direction="row" spacing={2} alignItems="center">
            <Box
              sx={{
                width: 140, height: 76, borderRadius: 2, border: "1px dashed", borderColor: "divider",
                display: "flex", alignItems: "center", justifyContent: "center", bgcolor: "action.hover", overflow: "hidden",
              }}
            >
              {org?.brand_logo_url ? (
                <Box component="img" src={org.brand_logo_url} alt="لوگو" sx={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
              ) : (
                <Typography variant="caption" color="text.secondary">بدون لوگو</Typography>
              )}
            </Box>
            <Stack spacing={0.75}>
              <input
                ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" hidden
                onChange={(e) => { pickFile(e.target.files?.[0]); e.target.value = ""; }}
              />
              <Button size="small" variant="outlined" disabled={uploadMut.isPending} onClick={() => fileRef.current?.click()}>
                {uploadMut.isPending ? "در حال آپلود…" : "آپلود لوگو (PNG/JPG/WEBP تا ۲MB)"}
              </Button>
              {org?.brand_logo_url && (
                <Button size="small" color="error" disabled={removeMut.isPending} onClick={() => removeMut.mutate()}>
                  حذف لوگو
                </Button>
              )}
            </Stack>
          </Stack>
          <TextField
            size="small" label="نام برند سازمان (مثلاً پتروپارس)"
            value={brandName} onChange={(e) => setBrandName(e.target.value)}
          />
          <TextField
            size="small" label="عنوان صفحه ورودی آزمون (خالی = عنوان آزمون)"
            value={entryTitle} onChange={(e) => setEntryTitle(e.target.value)}
            placeholder="مثلاً: ارزیابی سلامت شغلی پتروپارس"
          />
          <TextField
            size="small" label="پیام/توضیح صفحه ورودی (خالی = توضیح آزمون)"
            multiline minRows={3} value={entryNote} onChange={(e) => setEntryNote(e.target.value)}
            placeholder="مثلاً: این ارزیابی به همکاری شرکت نفت پارس و با رعایت کامل محرمانگی انجام می‌شود."
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={saveMut.isPending} onClick={() => saveMut.mutate()}>
          ذخیره
        </Button>
      </DialogActions>
    </Dialog>
  );
}
