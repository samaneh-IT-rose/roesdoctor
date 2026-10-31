import {
  Alert, Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, FormControlLabel, InputLabel, MenuItem,
  Paper, Select, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TablePagination, TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useState } from "react";
import { errDetail } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import {
  CONSULT_PAYMENT_META, CONSULT_STATUS_META, createManualConsultationRequest,
  fetchConsultationRequests, updateConsultationRequest,
} from "../api/siteops";
import type { ConsultationRow } from "../api/siteops";
import { convertConsultationRequest } from "../api/referrals";
import { fetchCounselorOptions } from "../api/cases";
import type { OptionRow } from "../api/cases";
import { fetchServiceLocations } from "../api/people";
import IntakeDialog from "../components/IntakeDialog";
import { useNavigate } from "react-router-dom";
import JalaliDateField from "../components/JalaliDateField";
import { formatJalaliDateTime } from "../utils/jalali";

const TOPICS = ["مشاوره فردی", "زوج‌درمانی", "مشاوره کودک و نوجوان", "درمان گروهی", "نوروفیدبک", "سایر"];
const SLOTS = ["صبح", "عصر", "هر زمان"];

export default function ConsultationRequestsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const canCreate =
    roles.includes("ORG_MANAGER") || roles.includes("RECEPTION") || roles.includes("COUNSELOR");

  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [convertRow, setConvertRow] = useState<ConsultationRow | null>(null);
  const [followRow, setFollowRow] = useState<ConsultationRow | null>(null);
  const [intakeRow, setIntakeRow] = useState<ConsultationRow | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["consultations", page, status],
    queryFn: () => fetchConsultationRequests({ page: page + 1, status: status || undefined }),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["consultations"] });

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>درخواست‌های مشاوره</Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          {canCreate && (
            <Button variant="contained" onClick={() => setCreateOpen(true)}>ثبت درخواست جدید</Button>
          )}
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>وضعیت</InputLabel>
            <Select value={status} label="وضعیت" onChange={(e) => { setPage(0); setStatus(e.target.value); }}>
              <MenuItem value="">همه</MenuItem>
              {Object.entries(CONSULT_STATUS_META).map(([k, v]) => (
                <MenuItem key={k} value={k}>{v.label}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>نام</TableCell>
              <TableCell>موبایل</TableCell>
              <TableCell>موضوع</TableCell>
              <TableCell>تماس</TableCell>
              <TableCell>زمان ثبت</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={7} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {data?.items.length === 0 && (
              <TableRow><TableCell colSpan={7}>درخواستی ثبت نشده است.</TableCell></TableRow>
            )}
            {data?.items.map((row) => {
              const m = CONSULT_STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              const canConvert = (row.status === "new" || row.status === "in_review") && canCreate;
              return (
                <TableRow key={row.id}>
                  <TableCell>
                    {row.full_name}
                    {row.city && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        {row.city}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{row.mobile}</TableCell>
                  <TableCell>
                    {row.topic}
                    {row.referral_source && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        via {row.referral_source}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" variant="outlined"
                      color={(row.contact_attempts ?? 0) > 0 ? "primary" : "default"}
                      label={`${(row.contact_attempts ?? 0).toLocaleString("fa-IR")} تماس`} />
                  </TableCell>
                  <TableCell>
                    {row.created_at ? formatJalaliDateTime(row.created_at) : "—"}
                    {row.preferred_start_at && (
                      <Typography variant="caption" color="primary" display="block">
                        🗓 نوبت درخواستی: {new Date(row.preferred_start_at.slice(0, 16)).toLocaleString("fa-IR")}
                      </Typography>
                    )}
                    {/* فاز ۶۹: وضعیت پرداخت آنلاین رزرو (زرین‌پال) */}
                    {row.payment_status && row.payment_status !== "not_required" && (
                      <Chip size="small" sx={{ mt: 0.5 }}
                        color={CONSULT_PAYMENT_META[row.payment_status]?.color ?? "default"}
                        label={CONSULT_PAYMENT_META[row.payment_status]?.label ?? row.payment_status} />
                    )}
                  </TableCell>
                  <TableCell><Chip size="small" color={m.color} label={m.label} /></TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      {canConvert && (
                        <Button size="small" variant="outlined" onClick={() => setConvertRow(row)}>
                          تبدیل
                        </Button>
                      )}
                      <Button size="small" onClick={() => setFollowRow(row)}>پیگیری</Button>
                      <Button size="small" variant="outlined" onClick={() => setIntakeRow(row)}>
                        پرسشنامه پذیرش
                      </Button>
                      {/* فاز ۴۹ - B42: مانیتورینگ وضعیت این درخواست در فرایندها */}
                      <Button
                        size="small" title="مانیتورینگ فرایندهای این درخواست (B42)"
                        onClick={() =>
                          navigate(
                            `/process-monitoring?subject_type=consultation_request&subject_id=${row.id}&label=${encodeURIComponent(row.full_name ?? "")}`,
                          )
                        }
                      >
                        فرایند
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <TablePagination component="div" count={data?.total ?? 0} page={page}
          onPageChange={(_, p) => setPage(p)} rowsPerPage={20} rowsPerPageOptions={[20]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`} />
      </TableContainer>

      <CreateManualDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        invalidate={invalidate}
        onError={setError}
      />
      <IntakeDialog row={intakeRow} onClose={() => setIntakeRow(null)} onError={setError} />
      <ConvertDialog
        row={convertRow}
        onClose={() => setConvertRow(null)}
        invalidate={invalidate}
        onError={setError}
      />
      <FollowUpDialog
        row={followRow}
        onClose={() => setFollowRow(null)}
        invalidate={invalidate}
        onError={setError}
      />
    </Stack>
  );
}

function CreateManualDialog({ open, onClose, invalidate, onError }: {
  open: boolean; onClose: () => void; invalidate: () => void; onError: (m: string) => void;
}) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [preferredDate, setPreferredDate] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (open) { setForm({}); setPreferredDate(undefined); setFormError(null); setSuccess(null); }
  }, [open]);

  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createManualConsultationRequest({
        full_name: form.full_name?.trim() || "",
        mobile: form.mobile?.trim() || "",
        topic: form.topic || "",
        preferred_date: preferredDate,
        preferred_slot: form.preferred_slot || undefined,
        city: form.city?.trim() || undefined,
        referral_source: form.referral_source?.trim() || undefined,
        message: form.message?.trim() || undefined,
        reception_note: form.reception_note?.trim() || undefined,
      });
      setSuccess("درخواست ثبت شد. از جدول قابل پیگیری و تبدیل است.");
      invalidate();
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>ثبت درخواست مشاوره (حضوری/تلفنی)</DialogTitle>
        <DialogContent>
          {success && (
            <Alert severity="success" sx={{ mt: 2 }}>
              {success}
              <Button size="small" sx={{ display: "block", mt: 1 }} onClick={onClose}>بستن</Button>
            </Alert>
          )}
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          {!success && (
            <Stack spacing={2} mt={2}>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField label="نام و نام خانوادگی *" value={form.full_name ?? ""} onChange={set("full_name")} required fullWidth />
                <TextField label="موبایل * (09121234567)" value={form.mobile ?? ""} onChange={set("mobile")} required fullWidth />
              </Stack>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField select label="موضوع *" value={form.topic ?? ""} onChange={set("topic")} required fullWidth>
                  {TOPICS.map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
                </TextField>
                <TextField select label="بازه ترجیحی" value={form.preferred_slot ?? ""} onChange={set("preferred_slot")} fullWidth>
                  <MenuItem value="">—</MenuItem>
                  {SLOTS.map((s) => <MenuItem key={s} value={s}>{s}</MenuItem>)}
                </TextField>
              </Stack>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="flex-end">
                <TextField label="شهر (اختیاری)" value={form.city ?? ""} onChange={set("city")} fullWidth />
                <Box sx={{ flexGrow: 1, width: "100%" }}>
                  <JalaliDateField
                    label="تاریخ ترجیحی تماس"
                    value={undefined}
                    onChange={(iso) => setPreferredDate(iso)}
                  />
                </Box>
              </Stack>
              <TextField label="نحوه آشنایی (اختیاری)" value={form.referral_source ?? ""} onChange={set("referral_source")} fullWidth />
              <TextField label="توضیح مراجع (اختیاری)" value={form.message ?? ""} onChange={set("message")} multiline minRows={2} fullWidth />
              <TextField label="یادداشت پذیرش (اختیاری)" value={form.reception_note ?? ""} onChange={set("reception_note")} multiline minRows={2} fullWidth />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>بستن</Button>
          {!success && (
            <Button type="submit" variant="contained" disabled={busy}>
              {busy ? "در حال ثبت…" : "ثبت درخواست"}
            </Button>
          )}
        </DialogActions>
      </form>
    </Dialog>
  );
}

function ConvertDialog({ row, onClose, invalidate, onError }: {
  row: ConsultationRow | null;
  onClose: () => void;
  invalidate: () => void;
  onError: (m: string) => void;
}) {
  const [createCase, setCreateCase] = useState(true);
  const [counselorId, setCounselorId] = useState("");
  const [serviceLocationId, setServiceLocationId] = useState("");
  const [firstAppt, setFirstAppt] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const { data: counselors } = useQuery({
    queryKey: ["counselor-options"],
    queryFn: fetchCounselorOptions,
    enabled: Boolean(row) && createCase,
  });
  const { data: locations } = useQuery({
    queryKey: ["locations"],
    queryFn: fetchServiceLocations,
    enabled: Boolean(row) && createCase,
  });

  useEffect(() => {
    if (row) {
      setCreateCase(true); setCounselorId(""); setServiceLocationId("");
      setFirstAppt(row.preferred_start_at ? row.preferred_start_at.slice(0, 16) : "");
      setFormError(null); setSuccess(null);
    }
  }, [row]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!row) return;
    setFormError(null);
    setBusy(true);
    try {
      const res = await convertConsultationRequest(row.id, {
        create_case: createCase,
        counselor_id: createCase && counselorId ? counselorId : undefined,
        service_location_id: createCase && serviceLocationId ? serviceLocationId : undefined,
        first_appointment_at: createCase && counselorId && firstAppt ? firstAppt : undefined,
      });
      const parts = ["متقاضی " + (res.applicant_created ? "ایجاد" : "یافت") + " شد."];
      if (res.case_number) parts.push("پرونده " + res.case_number + " تشکیل شد.");
      if (res.first_appointment_created) parts.push("نوبت اولیه ثبت شد.");
      setSuccess(parts.join(" "));
      invalidate();
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={row !== null} onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>تبدیل به متقاضی</DialogTitle>
        <DialogContent>
          {success && (
            <Alert severity="success" sx={{ mt: 2 }}>
              {success}
              <Button size="small" sx={{ display: "block", mt: 1 }} onClick={onClose}>بستن</Button>
            </Alert>
          )}
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          {row && !success && (
            <Stack spacing={2} mt={2}>
              <Typography variant="body2" color="text.secondary">
                نام: <b>{row.full_name}</b> | موبایل: <b>{row.mobile}</b> | موضوع: <b>{row.topic}</b>
              </Typography>
              {row.preferred_start_at && (
                <Alert severity="info">
                  نوبت درخواستی مراجع: {new Date(row.preferred_start_at.slice(0, 16)).toLocaleString("fa-IR")}
                  {" "}— در فیلد نوبت اولیه پیش‌پر شده است.
                </Alert>
              )}
              <FormControlLabel
                control={<Checkbox checked={createCase} onChange={(e) => setCreateCase(e.target.checked)} />}
                label="تشکیل پرونده جدید"
              />
              {createCase && (
                <>
                  <FormControl size="small" fullWidth>
                    <InputLabel>مشاور (اختیاری — تخصیص فوری)</InputLabel>
                    <Select value={counselorId} label="مشاور (اختیاری)"
                      onChange={(e) => setCounselorId(e.target.value)}>
                      <MenuItem value="">— بعداً تخصیص می‌شود —</MenuItem>
                      {counselors?.items.map((o: OptionRow) => (
                        <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <FormControl size="small" fullWidth>
                    <InputLabel>مرکز ارائه خدمت</InputLabel>
                    <Select value={serviceLocationId} label="مرکز ارائه خدمت"
                      onChange={(e) => setServiceLocationId(e.target.value)}>
                      <MenuItem value="">—</MenuItem>
                      {locations?.map((l) => (
                        <MenuItem key={l.id} value={l.id}>{l.title} ({l.code})</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  {counselorId && (
                    <TextField
                      label="نوبت اولیه (اختیاری)"
                      type="datetime-local"
                      value={firstAppt}
                      onChange={(e) => setFirstAppt(e.target.value)}
                      fullWidth
                    />
                  )}
                </>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>بستن</Button>
          {row && !success && (
            <Button type="submit" variant="contained" disabled={busy}>
              {busy ? "در حال تبدیل…" : "تبدیل"}
            </Button>
          )}
        </DialogActions>
      </form>
    </Dialog>
  );
}

function FollowUpDialog({ row, onClose, invalidate, onError }: {
  row: ConsultationRow | null;
  onClose: () => void;
  invalidate: () => void;
  onError: (m: string) => void;
}) {
  const [status, setStatus] = useState("in_review");
  const [note, setNote] = useState("");
  const [addAttempt, setAddAttempt] = useState(false);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (row) {
      setStatus(row.status === "new" ? "in_review" : row.status);
      setNote(row.reception_note ?? "");
      setAddAttempt(false);
      setFormError(null);
    }
  }, [row]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!row) return;
    setFormError(null);
    setBusy(true);
    try {
      await updateConsultationRequest(row.id, {
        status,
        reception_note: note.trim() || undefined,
        add_contact_attempt: addAttempt,
      });
      invalidate();
      onClose();
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={row !== null} onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>پیگیری درخواست</DialogTitle>
        <DialogContent>
          {row && (
            <Typography variant="body2" color="text.secondary" mt={1}>
              {row.full_name} — {row.mobile} | تاکنون {(row.contact_attempts ?? 0).toLocaleString("fa-IR")} تماس
            </Typography>
          )}
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={2}>
            <FormControl size="small" fullWidth>
              <InputLabel>وضعیت</InputLabel>
              <Select value={status} label="وضعیت" onChange={(e) => setStatus(e.target.value)}>
                {Object.entries(CONSULT_STATUS_META).map(([k, v]) => (
                  <MenuItem key={k} value={k}>{v.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="یادداشت پیگیری پذیرش"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              multiline
              minRows={3}
              fullWidth
            />
            <FormControlLabel
              control={<Checkbox checked={addAttempt} onChange={(e) => setAddAttempt(e.target.checked)} />}
              label="یک تماس انجام‌شده ثبت شود (+۱)"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>
            {busy ? "در حال ثبت…" : "ثبت پیگیری"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}