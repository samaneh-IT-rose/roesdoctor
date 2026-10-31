import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle,
  FormControl, FormControlLabel, InputLabel, MenuItem, Paper, Radio, RadioGroup, Select, Stack,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import {
  CASE_STATUS_META, CONSENT_META, PRIORITY_LABELS,
  addConsent, assignCounselor, closeCase, fetchCase, fetchCounselorOptions, reopenCase, revokeConsent, updateCase,
} from "../api/cases";
import type { CaseDetail } from "../api/cases";
import { fetchServiceLocations } from "../api/people";
import CaseClinical from "../components/CaseClinical";
import CaseReferrals from "../components/CaseReferrals";
import CaseAssessments from "../components/CaseAssessments";
import CaseAppointments from "../components/CaseAppointments";
import CaseSessions from "../components/CaseSessions";
import CaseRecommendations from "../components/CaseRecommendations";
import CaseFiles from "../components/CaseFiles";
import CasePsychAttempts from "../components/CasePsychAttempts";
import { formatJalali, formatJalaliDateTime } from "../utils/jalali";

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const canManage = roles.includes("ORG_MANAGER") || roles.includes("RECEPTION");
  const canAssign = roles.includes("ORG_MANAGER") || roles.includes("TECHNICAL_SUPERVISOR");
  const canReopen = roles.includes("ORG_MANAGER");

  const [editOpen, setEditOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);
  const [actionMode, setActionMode] = useState<null | "close" | "reopen">(null);
  const [consentOpen, setConsentOpen] = useState(false);

  const { data: c, isLoading, error } = useQuery({
    queryKey: ["case", id],
    queryFn: () => fetchCase(id!),
    enabled: Boolean(id),
  });

  if (isLoading) return <CircularProgress />;
  if (error) return <Alert severity="error">{errDetail(error)}</Alert>;
  if (!c) return null;

  const st = CASE_STATUS_META[c.status] ?? { label: c.status, color: "default" as const };
  const cs = CONSENT_META[c.consent_status] ?? { label: c.consent_status, color: "default" as const };

  return (
    <Stack spacing={2}>
      {c.status === "closed" && (
        <Alert severity="warning">
          این پرونده بسته شده است — علت: {c.close_reason ?? "—"} ({c.close_date ? formatJalali(c.close_date) : "—"})
        </Alert>
      )}

      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={700}>پرونده {c.case_number}</Typography>
        <Chip size="small" color={st.color} label={st.label} />
        <Chip size="small" variant="outlined" color={cs.color} label={cs.label} />
        <Chip size="small" variant="outlined" label={`اولویت: ${PRIORITY_LABELS[c.priority] ?? c.priority}`} />
        <Box flexGrow={1} />
        <Typography variant="caption" color="text.secondary">نسخه رکورد: {c.version}</Typography>
        {canManage && <Button size="small" variant="outlined" onClick={() => setEditOpen(true)}>ویرایش</Button>}
        {canAssign && (
          <Button size="small" variant="contained" onClick={() => setAssignOpen(true)}>
            {c.primary_counselor_name ? "انتقال مشاور" : "تخصیص مشاور"}
          </Button>
        )}
        {canManage && c.status !== "closed" && c.status !== "archived" && (
          <Button size="small" color="error" variant="outlined" onClick={() => setActionMode("close")}>بستن پرونده</Button>
        )}
        {canReopen && c.status === "closed" && (
          <Button size="small" color="warning" variant="outlined" onClick={() => setActionMode("reopen")}>بازگشایی</Button>
        )}
        {canManage && (
          <Button size="small" variant="outlined" onClick={() => setConsentOpen(true)}>ثبت رضایت</Button>
        )}
      </Box>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={1}>اطلاعات پرونده</Typography>
        <Stack spacing={0.5}>
          <InfoRow label="متقاضی" value={c.applicant_name} />
          <InfoRow label="کد ملی" value={c.applicant_national_id} />
          <InfoRow label="تاریخ پذیرش" value={formatJalali(c.acceptance_date)} />
          <InfoRow label="محل ارائه خدمت" value={c.service_location_title} />
          <InfoRow label="نوع خدمت" value={c.service_type} />
          <InfoRow label="مشاور اصلی" value={c.primary_counselor_name} />
        </Stack>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={1}>تاریخچه تخصیص مشاور</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>مشاور</TableCell>
                <TableCell>شروع</TableCell>
                <TableCell>پایان</TableCell>
                <TableCell>علت تخصیص</TableCell>
                <TableCell>علت پایان</TableCell>
                <TableCell>وضعیت</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {c.assignments.length === 0 && (
                <TableRow><TableCell colSpan={6}>هنوز مشاوری تخصیص نیافته است.</TableCell></TableRow>
              )}
              {c.assignments.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>
                    {a.counselor_name} {a.role === "collaborator" && <Chip size="small" label="همکار" variant="outlined" />}
                  </TableCell>
                  <TableCell>{a.start_at ? formatJalaliDateTime(a.start_at) : "—"}</TableCell>
                  <TableCell>{a.end_at ? formatJalaliDateTime(a.end_at) : "—"}</TableCell>
                  <TableCell>{a.reason ?? "—"}</TableCell>
                  <TableCell>{a.end_reason ?? "—"}</TableCell>
                  <TableCell>
                    <Chip size="small" color={a.is_current ? "success" : "default"}
                      label={a.is_current ? "جاری" : "پایان‌یافته"} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle1" fontWeight={700} mb={1}>رضایت‌نامه‌ها</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>نسخه</TableCell>
                <TableCell>نوع</TableCell>
                <TableCell>وضعیت</TableCell>
                <TableCell>تاریخ</TableCell>
                <TableCell>ثبت‌کننده</TableCell>
                <TableCell>توضیح</TableCell>
                <TableCell align="left">عمل</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {c.consents.length === 0 && (
                <TableRow><TableCell colSpan={7}>رضایتی ثبت نشده است.</TableCell></TableRow>
              )}
              {c.consents.map((x) => {
                const m = CONSENT_META[x.status] ?? { label: x.status, color: "default" as const };
                const kindLabel: Record<string, string> = {
                  treatment: "درمان", psych_test: "تست روان", data_share: "اشتراک داده", marketing: "تبلیغاتی",
                };
                return (
                  <TableRow key={x.id}>
                    <TableCell>{x.version}</TableCell>
                    <TableCell>{kindLabel[x.kind] ?? x.kind}</TableCell>
                    <TableCell>
                      <Chip size="small" color={m.color} label={m.label} />
                      {x.revoked_at && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                          ابطال: {formatJalali(x.revoked_at)} — {x.revoke_reason ?? "—"}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>{x.consent_date ? formatJalali(x.consent_date) : "—"}</TableCell>
                    <TableCell>{x.recorded_by_name ?? "—"}</TableCell>
                    <TableCell>{x.note ?? "—"}</TableCell>
                    <TableCell align="left">
                      {x.status === "granted" && (canManage || roles.includes("TECHNICAL_SUPERVISOR")) && (
                        <RevokeConsentButton consentId={x.id} caseId={c.id} />
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <CaseAssessments caseId={c.id} />
      {/* فاز ۷۰ - نتایج آزمون‌های روان‌شناسی متصل به پرونده */}
      <CasePsychAttempts caseId={c.id} />
      <CaseFiles caseId={c.id} />
      <CaseClinical caseId={c.id} />
      <CaseReferrals caseId={c.id} />
      <CaseAppointments caseId={c.id} />
      <CaseSessions caseId={c.id} />
      <CaseRecommendations caseId={c.id} />
      {editOpen && <EditDialog caseData={c} onClose={() => setEditOpen(false)} />}
      {assignOpen && <AssignDialog caseData={c} onClose={() => setAssignOpen(false)} />}
      {actionMode !== null && <ActionDialog mode={actionMode} caseData={c} onClose={() => setActionMode(null)} />}
      {consentOpen && <ConsentDialog caseData={c} onClose={() => setConsentOpen(false)} />}
    </Stack>
  );
}

function InfoRow({ label, value }: { label: string; value: string | null }) {
  return (
    <Stack direction="row" spacing={1}>
      <Typography variant="body2" sx={{ minWidth: 140, color: "text.secondary" }}>{label}:</Typography>
      <Typography variant="body2">{value ?? "—"}</Typography>
    </Stack>
  );
}

function EditDialog({ caseData, onClose }: { caseData: CaseDetail; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({
    service_type: caseData.service_type ?? "",
    priority: caseData.priority,
    service_location_id: "",
    status: caseData.status === "suspended" ? "suspended" : "active",
  });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { data: locations } = useQuery({ queryKey: ["locations"], queryFn: fetchServiceLocations });

  const set = (k: string) => (e: { target: { value: string } }) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await updateCase(caseData.id, {
        expected_version: caseData.version,
        service_type: form.service_type?.trim() || undefined,
        priority: form.priority,
        status: form.status,
        ...(form.service_location_id ? { service_location_id: form.service_location_id } : {}),
      });
      await queryClient.invalidateQueries({ queryKey: ["case", caseData.id] });
      onClose();
    } catch (err) {
      setFormError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>ویرایش پرونده {caseData.case_number}</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <Stack spacing={2} mt={2}>
            <TextField label="نوع خدمت" value={form.service_type} onChange={set("service_type")} />
            <FormControl size="small">
              <InputLabel>اولویت</InputLabel>
              <Select value={form.priority} onChange={set("priority")} label="اولویت">
                <MenuItem value="low">کم</MenuItem>
                <MenuItem value="normal">عادی</MenuItem>
                <MenuItem value="high">فوری</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small">
              <InputLabel>وضعیت</InputLabel>
              <Select value={form.status} onChange={set("status")} label="وضعیت">
                <MenuItem value="active">فعال</MenuItem>
                <MenuItem value="suspended">متوقف</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small">
              <InputLabel>محل ارائه خدمت (تغییر اختیاری)</InputLabel>
              <Select value={form.service_location_id} onChange={set("service_location_id")} label="محل ارائه خدمت (تغییر اختیاری)">
                <MenuItem value="">— بدون تغییر —</MenuItem>
                {locations?.map((l) => <MenuItem key={l.id} value={l.id}>{l.title} ({l.code})</MenuItem>)}
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>{busy ? "در حال ثبت…" : "ذخیره"}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function AssignDialog({ caseData, onClose }: { caseData: CaseDetail; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [role, setRole] = useState<"primary" | "collaborator">("primary");
  const [counselorId, setCounselorId] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { data: counselors } = useQuery({ queryKey: ["counselor-options"], queryFn: fetchCounselorOptions });

  const isTransfer = role === "primary" && Boolean(caseData.primary_counselor_name);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!counselorId) {
      setFormError("انتخاب مشاور الزامی است");
      return;
    }
    if (isTransfer && reason.trim().length < 3) {
      setFormError("برای انتقال مشاور، ثبت علت الزامی است");
      return;
    }
    setBusy(true);
    try {
      await assignCounselor(caseData.id, {
        counselor_id: counselorId,
        reason: reason.trim() || undefined,
        expected_version: caseData.version,
        role_in_case: role,
      });
      await queryClient.invalidateQueries({ queryKey: ["case", caseData.id] });
      onClose();
    } catch (err) {
      setFormError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>تخصیص مشاور</DialogTitle>
        <DialogContent>
          <Stack spacing={2} mt={2}>
            <Typography variant="body2" color="text.secondary">
              نقش: «مشاور اصلی» جایگزین مشاور فعلی می‌شود (انتقال با علت الزامی)؛
              «همکار پرونده» مشاور را بدون تغییر مشاور اصلی اضافه می‌کند (بند v1.00).
            </Typography>
            <Stack direction="row" spacing={2}>
              <FormControlLabel
                control={<Radio checked={role === "primary"} onChange={() => setRole("primary")} />}
                label="مشاور اصلی"
              />
              <FormControlLabel
                control={<Radio checked={role === "collaborator"} onChange={() => setRole("collaborator")} />}
                label="همکار پرونده"
              />
            </Stack>
            {isTransfer && (
              <Alert severity="info">
                مشاور فعلی: {caseData.primary_counselor_name} — پس از انتقال، دسترسی جاری مشاور قبلی قطع می‌شود.
              </Alert>
            )}
            {formError && <Alert severity="error">{formError}</Alert>}
            <FormControl size="small" required>
              <InputLabel>مشاور *</InputLabel>
              <Select value={counselorId} onChange={(e) => setCounselorId(e.target.value)} label="مشاور *">
                <MenuItem value="">— انتخاب کنید —</MenuItem>
                {counselors?.items.map((o) => (
                  <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label={isTransfer ? "علت انتقال *" : "علت (اختیاری)"}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required={isTransfer}
              multiline
              minRows={2}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>
            {busy ? "در حال ثبت…" : "ثبت"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
function ActionDialog({ mode, caseData, onClose }: { mode: "close" | "reopen"; caseData: CaseDetail; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (reason.trim().length < 3) {
      setFormError("ثبت دلیل الزامی است");
      return;
    }
    setBusy(true);
    try {
      if (mode === "close") await closeCase(caseData.id, reason.trim());
      else await reopenCase(caseData.id, reason.trim());
      await queryClient.invalidateQueries({ queryKey: ["case", caseData.id] });
      onClose();
    } catch (err) {
      setFormError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>{mode === "close" ? "بستن پرونده" : "بازگشایی پرونده"}</DialogTitle>
        <DialogContent>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <TextField
            autoFocus fullWidth multiline minRows={3} margin="normal"
            label={mode === "close" ? "علت بستن پرونده *" : "دلیل بازگشایی *"}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" color={mode === "close" ? "error" : "primary"} disabled={busy}>
            {busy ? "در حال ثبت…" : "ثبت"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function ConsentDialog({ caseData, onClose }: { caseData: CaseDetail; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("granted");
  const [kind, setKind] = useState("treatment");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await addConsent(caseData.id, { status, kind, note: note.trim() || undefined });
      await queryClient.invalidateQueries({ queryKey: ["case", caseData.id] });
      onClose();
    } catch (err) {
      setFormError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="xs" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>ثبت رضایت‌نامه</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            هر ثبت یک نسخه جدید ایجاد می‌کند؛ سوابق قبلی حفظ می‌شوند.
          </Typography>
          {formError && <Alert severity="error" sx={{ mt: 2 }}>{formError}</Alert>}
          <RadioGroup row value={status} onChange={(e) => setStatus(e.target.value)} sx={{ mt: 2 }}>
            <FormControlLabel value="granted" control={<Radio />} label="ثبت رضایت" />
            <FormControlLabel value="revoked" control={<Radio />} label="پس‌گرفتن رضایت" />
          </RadioGroup>
          <FormControl fullWidth size="small" sx={{ mt: 1 }}>
            <InputLabel>نوع رضایت</InputLabel>
            <Select value={kind} onChange={(e) => setKind(e.target.value)} label="نوع رضایت">
              <MenuItem value="treatment">درمان</MenuItem>
              <MenuItem value="psych_test">تست روان</MenuItem>
              <MenuItem value="data_share">اشتراک داده</MenuItem>
              <MenuItem value="marketing">تبلیغاتی</MenuItem>
            </Select>
          </FormControl>
          <TextField fullWidth multiline minRows={2} label="توضیح (اختیاری)" sx={{ mt: 2 }}
            value={note} onChange={(e) => setNote(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>{busy ? "در حال ثبت…" : "ثبت"}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/** دکمه ابطال رضایت با دلیل - B41: ابطال آینده را قطع می‌کند و سابقه حفظ می‌شود */
function RevokeConsentButton({ consentId, caseId }: { consentId: string; caseId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (reason.trim().length < 3) {
      setErr("ثبت دلیل ابطال الزامی است");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await revokeConsent(consentId, reason.trim());
      await queryClient.invalidateQueries({ queryKey: ["case", caseId] });
      setOpen(false);
      setReason("");
    } catch (e) {
      setErr(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button size="small" color="warning" onClick={() => setOpen(true)}>ابطال</Button>
      {open && (
        <Dialog open onClose={() => setOpen(false)} maxWidth="xs" fullWidth>
          <DialogTitle>ابطال رضایت</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              ابطال، آینده را قطع می‌کند و سابقه رضایت حفظ می‌شود (B41 سند جامع).
            </Typography>
            {err && <Alert severity="error" sx={{ mt: 2 }}>{err}</Alert>}
            <TextField
              fullWidth multiline minRows={2} sx={{ mt: 2 }}
              label="دلیل ابطال (الزامی)"
              value={reason} onChange={(e) => setReason(e.target.value)}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setOpen(false)}>انصراف</Button>
            <Button color="warning" variant="contained" disabled={busy} onClick={submit}>
              {busy ? "در حال ثبت…" : "ثبت ابطال"}
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
}
