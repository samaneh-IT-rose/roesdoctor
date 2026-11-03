// فاز ۵۸ - کارتابل برنامهٔ آزمون سازمانی: نمای تجمیعی پروژهٔ سازمان
// (آزمون‌های منتخب + مشاوران پروژه با گفتگوی آنلاین + راهنما + سوالات پرتکرار
// + اعضا و پیشرفت + مدیریت برنامه) — مثال: شرکت نفت پارس
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Card, CardContent,
  Chip, Dialog, DialogActions, DialogContent, DialogTitle, Divider, FormControl, Grid,
  InputLabel, LinearProgress, MenuItem, Paper, Select, Snackbar, Stack, Tab, Tabs, TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import AssignmentTurnedInRoundedIcon from "@mui/icons-material/AssignmentTurnedInRounded";
import ChatRoundedIcon from "@mui/icons-material/ChatRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import Diversity3RoundedIcon from "@mui/icons-material/Diversity3Rounded";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import ForumRoundedIcon from "@mui/icons-material/ForumRounded";
import GroupRoundedIcon from "@mui/icons-material/GroupRounded";
import HelpOutlineRoundedIcon from "@mui/icons-material/HelpOutlineRounded";
import InfoRoundedIcon from "@mui/icons-material/InfoRounded";
import MenuBookRoundedIcon from "@mui/icons-material/MenuBookRounded";
import PersonAddAlt1RoundedIcon from "@mui/icons-material/PersonAddAlt1Rounded";
import PlayCircleOutlineRoundedIcon from "@mui/icons-material/PlayCircleOutlineRounded";
import SaveRoundedIcon from "@mui/icons-material/SaveRounded";
import TimerRoundedIcon from "@mui/icons-material/TimerRounded";
import { errDetail } from "../api/client";
import JalaliDateField from "../components/JalaliDateField";
import { useAuth } from "../auth/AuthContext";
import { startConversation } from "../api/chat";
import { fetchChatDirectory } from "../api/chat";
import {
  OrgProgramWorkdesk,
  addOrgProgramCounselor, addOrgProgramMember, fetchOrgProgramWorkdesk,
  removeOrgProgramCounselor, removeOrgProgramMember, setOrgProgramFaq, setOrgProgramTests,
  updateOrgProgram, deleteOrgProgram,
} from "../api/orgPrograms";
import { fetchPublicPsychTests } from "../api/psych";
import { EmptyState } from "../components/FormKit";
import { formatJalali } from "../utils/jalali";

const statusChip = (s: string) =>
  s === "active"
    ? { label: "فعال", color: "success" as const }
    : s === "draft"
      ? { label: "پیش‌نویس", color: "default" as const }
      : { label: "پایان‌یافته", color: "warning" as const };

export default function OrgProgramWorkdeskPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const canManage = roles.includes("SYSTEM_ADMIN") || roles.includes("ORG_MANAGER");

  const [tab, setTab] = useState(0);
  const [snack, setSnack] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const workdesk = useQuery({
    queryKey: ["org-program", id],
    queryFn: () => fetchOrgProgramWorkdesk(id!),
    enabled: !!id,
  });
  const catalog = useQuery({ queryKey: ["public-psych-tests"], queryFn: fetchPublicPsychTests });

  const refetch = () => {
    qc.invalidateQueries({ queryKey: ["org-program", id] });
    qc.invalidateQueries({ queryKey: ["org-programs"] });
  };

  const p = workdesk.data;

  const chatMut = useMutation({
    mutationFn: (counselorUserId: string) => startConversation(counselorUserId),
    onSuccess: () => navigate("/chat"),
    onError: (e) => setErr(errDetail(e)),
  });

  const removeMut = useMutation({
    mutationFn: () => deleteOrgProgram(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org-programs"] });
      navigate("/org-programs");
    },
    onError: (e) => setErr(errDetail(e)),
  });

  if (workdesk.isLoading) {
    return <Paper sx={{ p: 4, textAlign: "center", color: "text.secondary" }}>در حال بارگذاری کارتابل…</Paper>;
  }
  if (!p) {
    return <Alert severity="error">برنامهٔ آزمون یافت نشد.</Alert>;
  }

  const st = statusChip(p.status);

  return (
    <Stack spacing={2.5}>
      {/* سرصفحهٔ کارتابل */}
      <Paper sx={{ p: 2.5, borderRadius: 3, background: "linear-gradient(120deg, rgba(90,60,140,0.08), rgba(40,110,140,0.06))" }}>
        <Stack direction="row" alignItems="flex-start" spacing={1.5} flexWrap="wrap" useFlexGap>
          <Box sx={{ flex: 1, minWidth: 260 }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
              <Chip size="small" icon={<InfoRoundedIcon />} label={p.organization_name ?? "سازمان"} variant="outlined" />
              <Chip size="small" {...st} />
              {p.due_date && (
                <Chip size="small" label={`مهلت: ${formatJalali(p.due_date)}`} variant="outlined" color="warning" />
              )}
            </Stack>
            <Typography variant="h5" fontWeight={800}>{p.title}</Typography>
            {p.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 760 }}>
                {p.description}
              </Typography>
            )}
          </Box>
          {canManage && (
            <Stack direction="row" spacing={1}>
              <Button size="small" color="error" startIcon={<DeleteOutlineRoundedIcon />} onClick={() => {
                if (window.confirm(`حذف برنامهٔ «${p.title}» و همهٔ اعضا/سوالات آن؟`)) removeMut.mutate();
              }}>
                حذف برنامه
              </Button>
            </Stack>
          )}
        </Stack>

        {/* شاخص‌ها */}
        <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap sx={{ mt: 2 }}>
          <Chip icon={<AssignmentTurnedInRoundedIcon />} label={`${p.tests_count} آزمون`} variant="outlined" />
          <Chip icon={<GroupRoundedIcon />} label={`${p.members_count} عضو`} variant="outlined" />
          <Chip icon={<Diversity3RoundedIcon />} label={`${p.counselors_count} مشاور پروژه`} variant="outlined" />
          <Chip icon={<ForumRoundedIcon />} label={`${p.faq_count} سوال پرتکرار`} variant="outlined" />
          <Box sx={{ minWidth: 220, flex: 1, maxWidth: 340 }}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <LinearProgress
                variant="determinate" value={p.progress_percent}
                sx={{ flex: 1, height: 8, borderRadius: 4 }}
              />
              <Typography variant="caption" color="text.secondary">
                میانگین پیشرفت {p.progress_percent}٪
              </Typography>
            </Stack>
          </Box>
        </Stack>
      </Paper>

      {err && <Alert severity="error" onClose={() => setErr(null)}>{err}</Alert>}

      <Paper sx={{ px: 1.5, py: 0.5 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="نمای کارتابل" />
          <Tab label="اعضا و پیشرفت" />
          {canManage && <Tab label="مدیریت برنامه" />}
        </Tabs>
      </Paper>

      {/* ---------------- نمای پروژه (کارتابل) ---------------- */}
      {tab === 0 && (
        <Grid container spacing={2}>
          {/* آزمون‌های برنامه */}
          <Grid item xs={12} md={8}>
            <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 1 }}>
              آزمون‌های این پروژه
            </Typography>
            {p.tests.length === 0 ? (
              <Paper sx={{ p: 3 }}>
                <EmptyState
                  title="هنوز آزمونی به برنامه اضافه نشده"
                  desc={canManage ? "از تب «مدیریت برنامه» آزمون‌های موردنیاز را از بانک آزمون اضافه کنید." : "به‌زودی آزمون‌های پروژه اعلام می‌شود."}
                />
              </Paper>
            ) : (
              <Grid container spacing={1.5}>
                {p.tests.map((t) => (
                  <Grid item xs={12} sm={6} key={t.id}>
                    <Card sx={{ borderRadius: 3, height: "100%", borderColor: t.accent_color ?? undefined }}>
                      <CardContent>
                        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
                          {t.code && (
                            <Chip size="small" label={t.code} sx={{ bgcolor: t.accent_color ?? "#8a757c", color: "#fff" }} />
                          )}
                          {t.is_required ? (
                            <Chip size="small" label="الزامی" color="primary" variant="outlined" />
                          ) : (
                            <Chip size="small" label="اختیاری" variant="outlined" />
                          )}
                        </Stack>
                        <Typography variant="subtitle2" fontWeight={800}>
                          {/* فاز ۷۵ — عنوان نمایشی برنامه در اولویت */}
                          {t.effective_title ?? t.title}
                        </Typography>
                        {(t.effective_title ?? t.title) !== t.title && (
                          <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                            نام اصلی: {t.title}
                          </Typography>
                        )}
                        {t.description && (
                          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5, minHeight: 32 }}>
                            {t.description?.slice(0, 110)}
                          </Typography>
                        )}
                        <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 1 }}>
                          {t.estimated_minutes && (
                            <Chip size="small" icon={<TimerRoundedIcon />} label={`~${t.estimated_minutes} دقیقه`} variant="outlined" />
                          )}
                          <Box flex={1} />
                          <Button
                            size="small" variant="text" startIcon={<PlayCircleOutlineRoundedIcon />}
                            onClick={() => navigate(`/psych-tests/${t.slug}/run?program=${p.id}`)}
                          >
                            شروع آزمون
                          </Button>
                        </Stack>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            )}
          </Grid>

          {/* ستون کنار: مشاوران + چت */}
          <Grid item xs={12} md={4}>
            <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 1 }}>
              مشاوران این پروژه
            </Typography>
            <Paper sx={{ p: 2, borderRadius: 3 }}>
              {p.counselors.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  هنوز مشاوری به این پروژه اضافه نشده است.
                </Typography>
              ) : (
                <Stack spacing={1.25}>
                  {p.counselors.map((c) => (
                    <Stack
                      key={c.id} direction="row" alignItems="center" spacing={1}
                      sx={{ p: 1, borderRadius: 2, bgcolor: "action.hover" }}
                    >
                      <Box sx={{ width: 34, height: 34, borderRadius: "50%", bgcolor: "primary.main", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800 }}>
                        {(c.display_name ?? "؟").slice(0, 1)}
                      </Box>
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="body2" fontWeight={700} noWrap>
                          {c.display_name ?? c.username}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">{c.role_in_project}</Typography>
                      </Box>
                      <Button
                        size="small" variant="outlined" startIcon={<ChatRoundedIcon />}
                        disabled={chatMut.isPending}
                        onClick={() => chatMut.mutate(c.user_id)}
                      >
                        گفتگو
                      </Button>
                    </Stack>
                  ))}
                  <Alert severity="info" variant="outlined" sx={{ py: 0.75 }}>
                    با دکمهٔ «گفتگو» چت آنلاین خصوصی با مشاور آغاز می‌شود — در همان صفحهٔ گفتگوی پنل.
                  </Alert>
                </Stack>
              )}
            </Paper>
          </Grid>

          {/* راهنمای پروژه — داخل خود کارتابل */}
          <Grid item xs={12} md={7}>
            <Paper sx={{ p: 2.5, borderRadius: 3 }}>
              <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                <MenuBookRoundedIcon color="primary" fontSize="small" />
                <Typography variant="subtitle1" fontWeight={800}>راهنمای پروژه</Typography>
              </Stack>
              {p.guide_text ? (
                p.guide_text.split("\n").filter(Boolean).map((line, i) => (
                  <Typography key={i} variant="body2" sx={{ mb: 0.75, lineHeight: 2 }}>
                    {line}
                  </Typography>
                ))
              ) : (
                <Typography variant="body2" color="text.secondary">راهنمایی ثبت نشده است.</Typography>
              )}
            </Paper>
          </Grid>
          {/* سوالات پرتکرار — داخل خود کارتابل */}
          <Grid item xs={12} md={5}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
              <HelpOutlineRoundedIcon color="primary" fontSize="small" />
              <Typography variant="subtitle1" fontWeight={800}>سوالات پرتکرار</Typography>
            </Stack>
            {p.faqs.length === 0 ? (
              <Paper sx={{ p: 3 }}>
                <Typography variant="body2" color="text.secondary">سوالی ثبت نشده است.</Typography>
              </Paper>
            ) : (
              p.faqs.map((f) => (
                <Accordion key={f.id} sx={{ borderRadius: "12px !important", mb: 1 }}>
                  <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />}>
                    <Typography variant="body2" fontWeight={700}>{f.question}</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Typography variant="body2" sx={{ lineHeight: 2 }}>{f.answer}</Typography>
                  </AccordionDetails>
                </Accordion>
              ))
            )}
          </Grid>
        </Grid>
      )}

      {/* ---------------- اعضا و پیشرفت ---------------- */}
      {tab === 1 && (
        <MembersTab p={p} canManage={canManage} onChanged={refetch} onError={setErr} onSnack={setSnack} />
      )}

      {/* ---------------- مدیریت برنامه ---------------- */}
      {tab === 2 && canManage && (
        <ManageTab p={p} catalog={catalog.data ?? []} onChanged={refetch} onError={setErr} onSnack={setSnack} />
      )}

      <Snackbar open={!!snack} autoHideDuration={3500} onClose={() => setSnack(null)} message={snack ?? ""} />
    </Stack>
  );
}

/* ================= اعضا و پیشرفت ================= */
function MembersTab({
  p, canManage, onChanged, onError, onSnack,
}: {
  p: OrgProgramWorkdesk;
  canManage: boolean;
  onChanged: () => void;
  onError: (s: string | null) => void;
  onSnack: (s: string | null) => void;
}) {
  const [addOpen, setAddOpen] = useState(false);
  const [fName, setFName] = useState("");
  const [fCode, setFCode] = useState("");
  const [fMobile, setFMobile] = useState("");
  const [fUnit, setFUnit] = useState("");
  const [fUser, setFUser] = useState("");

  const directory = useQuery({ queryKey: ["chat-directory", ""], queryFn: () => fetchChatDirectory("") });

  const addMut = useMutation({
    mutationFn: () =>
      addOrgProgramMember(p.id, {
        full_name: fName.trim(),
        employee_code: fCode.trim() || undefined,
        mobile: fMobile.trim() || undefined,
        unit: fUnit.trim() || undefined,
        user_id: fUser || undefined,
      }),
    onSuccess: () => {
      onSnack("عضو به برنامه اضافه شد");
      setAddOpen(false);
      setFName(""); setFCode(""); setFMobile(""); setFUnit(""); setFUser("");
      onChanged();
    },
    onError: (e) => onError(errDetail(e)),
  });

  const removeMut = useMutation({
    mutationFn: (memberId: string) => removeOrgProgramMember(p.id, memberId),
    onSuccess: () => { onSnack("عضو حذف شد"); onChanged(); },
    onError: (e) => onError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
        <Typography variant="subtitle1" fontWeight={800}>
          اعضای برنامه ({p.members.length} نفر)
        </Typography>
        <Box flex={1} />
        {canManage && (
          <Button variant="contained" size="small" startIcon={<PersonAddAlt1RoundedIcon />} onClick={() => setAddOpen(true)}>
            افزودن عضو
          </Button>
        )}
      </Stack>

      {p.members.length === 0 ? (
        <Paper sx={{ p: 4 }}>
          <EmptyState title="هنوز عضوی ثبت نشده" desc="کارکنان سازمان را با نام، کد پرسنلی و واحد سازمانی اضافه کنید." />
        </Paper>
      ) : (
        <Paper sx={{ borderRadius: 3, overflow: "hidden" }}>
          {p.members.map((m, i) => (
            <Box key={m.id}>
              {i > 0 && <Divider />}
              <Stack direction="row" alignItems="center" spacing={1.5} sx={{ px: 2, py: 1.25 }} flexWrap="wrap" useFlexGap>
                <Box sx={{ width: 34, height: 34, borderRadius: "50%", bgcolor: "secondary.main", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800 }}>
                  {m.full_name.slice(0, 1)}
                </Box>
                <Box sx={{ minWidth: 150 }}>
                  <Typography variant="body2" fontWeight={700}>{m.full_name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {m.unit ?? "—"}{m.employee_code ? ` • کد: ${m.employee_code}` : ""}
                  </Typography>
                </Box>
                {m.user_id ? (
                  <Chip size="small" label={`حساب متصل: ${m.username ?? "—"}`} color="primary" variant="outlined" />
                ) : (
                  <Chip size="small" label="بدون حساب کاربری" variant="outlined" />
                )}
                <Box sx={{ flex: 1, minWidth: 180 }}>
                  <Stack direction="row" alignItems="center" spacing={1}>
                    <LinearProgress
                      variant="determinate" value={m.progress_percent}
                      sx={{ flex: 1, height: 6, borderRadius: 3 }}
                      color={m.progress_percent >= 100 ? "success" : "primary"}
                    />
                    <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
                      {m.done_count} از {m.total_tests} آزمون
                    </Typography>
                  </Stack>
                </Box>
                {canManage && (
                  <Button
                    size="small" color="error" startIcon={<DeleteOutlineRoundedIcon />}
                    onClick={() => { if (window.confirm(`حذف «${m.full_name}» از برنامه؟`)) removeMut.mutate(m.id); }}
                  >
                    حذف
                  </Button>
                )}
              </Stack>
            </Box>
          ))}
        </Paper>
      )}

      {/* افزودن عضو */}
      <Dialog open={addOpen} onClose={() => setAddOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>افزودن عضو به برنامه</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField size="small" label="نام و نام خانوادگی" required value={fName} onChange={(e) => setFName(e.target.value)} />
            <TextField size="small" label="کد پرسنلی" value={fCode} onChange={(e) => setFCode(e.target.value)} />
            <TextField size="small" label="موبایل" value={fMobile} onChange={(e) => setFMobile(e.target.value)} />
            <TextField size="small" label="واحد سازمانی" value={fUnit} onChange={(e) => setFUnit(e.target.value)} />
            <FormControl size="small" fullWidth>
              <InputLabel>پیوند به حساب کاربری (اختیاری)</InputLabel>
              <Select label="پیوند به حساب کاربری (اختیاری)" value={fUser} onChange={(e) => setFUser(e.target.value)}>
                <MenuItem value="">— بدون پیوند —</MenuItem>
                {(directory.data ?? []).map((u) => (
                  <MenuItem key={u.id} value={u.id}>
                    {u.display_name ?? u.username} {u.roles.includes("APPLICANT") ? "(متقاضی)" : ""}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Alert severity="info" variant="outlined" sx={{ py: 0.75 }}>
              اگر عضو حساب کاربری داشته باشد، پیشرفت او در آزمون‌های برنامه به‌صورت خودکار پیگیری می‌شود.
            </Alert>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddOpen(false)}>انصراف</Button>
          <Button variant="contained" disabled={fName.trim().length < 2 || addMut.isPending} onClick={() => addMut.mutate()}>
            افزودن
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

/* ================= مدیریت برنامه ================= */
function ManageTab({
  p, catalog, onChanged, onError, onSnack,
}: {
  p: OrgProgramWorkdesk;
  catalog: { id: string; title: string; topic_name: string | null }[];
  onChanged: () => void;
  onError: (s: string | null) => void;
  onSnack: (s: string | null) => void;
}) {
  const qc = useQueryClient();
  const currentTestIds = useMemo(() => p.tests.map((t) => t.test_id), [p.tests]);
  const [selTests, setSelTests] = useState<string[] | null>(null);
  // فاز ۷۵ — عنوان نمایشی هر آزمون برای شرکت‌کنندگان (خالی = عنوان اصلی)
  const [titles, setTitles] = useState<Record<string, string>>(() =>
    Object.fromEntries(p.tests.map((t) => [t.test_id, t.display_title ?? ""])),
  );
  const [status, setStatus] = useState<string>(p.status);
  const [dueDate, setDueDate] = useState(p.due_date ?? "");
  const [guide, setGuide] = useState(p.guide_text ?? "");
  const [faqs, setFaqs] = useState(p.faqs.map((f) => ({ question: f.question, answer: f.answer })));
  const [counselorPick, setCounselorPick] = useState("");
  const [counselorRole, setCounselorRole] = useState("مشاور");

  const directory = useQuery({ queryKey: ["chat-directory", ""], queryFn: () => fetchChatDirectory("") });

  const saveTests = useMutation({
    mutationFn: () => setOrgProgramTests(p.id, selTests ?? currentTestIds),
    onSuccess: () => { onSnack("فهرست آزمون‌های برنامه ذخیره شد"); onChanged(); },
    onError: (e) => onError(errDetail(e)),
  });

  // فاز ۷۵ — ذخیرهٔ عنوان‌های نمایشی (فقط ردیف‌های ذخیره‌شدهٔ برنامه)
  const saveTitles = useMutation({
    mutationFn: () =>
      setOrgProgramTests(
        p.id,
        currentTestIds,
        p.tests.map((t) => ({
          test_id: t.test_id,
          display_title: (titles[t.test_id] ?? "").trim() || null,
        })),
      ),
    onSuccess: () => { onSnack("عنوان‌های نمایشی آزمون‌ها ذخیره شد"); onChanged(); },
    onError: (e) => onError(errDetail(e)),
  });

  const saveInfo = useMutation({
    mutationFn: () => updateOrgProgram(p.id, { status, due_date: dueDate || null, guide_text: guide }),
    onSuccess: () => { onSnack("اطلاعات برنامه ذخیره شد"); onChanged(); },
    onError: (e) => onError(errDetail(e)),
  });

  const saveFaq = useMutation({
    mutationFn: () => setOrgProgramFaq(p.id, faqs.filter((f) => f.question.trim() && f.answer.trim())),
    onSuccess: () => { onSnack("سوالات پرتکرار ذخیره شد"); onChanged(); },
    onError: (e) => onError(errDetail(e)),
  });

  const addCounselor = useMutation({
    mutationFn: () => addOrgProgramCounselor(p.id, { user_id: counselorPick, role_in_project: counselorRole.trim() || "مشاور" }),
    onSuccess: () => {
      onSnack("مشاور به پروژه اضافه شد");
      setCounselorPick("");
      qc.invalidateQueries({ queryKey: ["chat-directory", ""] });
      onChanged();
    },
    onError: (e) => onError(errDetail(e)),
  });

  const removeCounselor = useMutation({
    mutationFn: (cid: string) => removeOrgProgramCounselor(p.id, cid),
    onSuccess: () => { onSnack("مشاور از پروژه حذف شد"); onChanged(); },
    onError: (e) => onError(errDetail(e)),
  });

  return (
    <Grid container spacing={2}>
      {/* آزمون‌های برنامه */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2.5, borderRadius: 3 }}>
          <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 0.5 }}>
            آزمون‌های موردنیاز برنامه
          </Typography>
          <Typography variant="caption" color="text.secondary">
            با کلیک، آزمون‌های منتشرشدهٔ بانک آزمون را به برنامه اضافه/حذف کنید
          </Typography>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1.5 }}>
            {catalog.map((t) => {
              const on = (selTests ?? currentTestIds).includes(t.id);
              return (
                <Chip
                  key={t.id}
                  size="small"
                  label={t.title}
                  color={on ? "primary" : "default"}
                  variant={on ? "filled" : "outlined"}
                  onClick={() => {
                    const base = selTests ?? currentTestIds;
                    setSelTests(on ? base.filter((x) => x !== t.id) : [...base, t.id]);
                  }}
                />
              );
            })}
          </Box>
          <Stack direction="row" justifyContent="flex-end" sx={{ mt: 1.5 }}>
            <Button variant="contained" startIcon={<SaveRoundedIcon />} disabled={saveTests.isPending || selTests === null} onClick={() => saveTests.mutate()}>
              ذخیرهٔ آزمون‌ها
            </Button>
          </Stack>

          {/* فاز ۷۵ — عنوان نمایشی هر آزمون برای شرکت‌کنندگان */}
          {p.tests.length > 0 && (
            <Box sx={{ mt: 2, pt: 2, borderTop: "1px dashed", borderColor: "divider" }}>
              <Typography variant="subtitle2" fontWeight={800} sx={{ mb: 0.5 }}>
                عنوان نمایشی آزمون‌ها برای شرکت‌کنندگان
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.5 }}>
                مثلاً به‌جای «پرسشنامه سلامت عمومی (GHQ-28)»، عنوان دلخواه مثل «ارزیابی سلامت کارکنان» بگذارید؛
                این عنوان در صفحه ورودی، حین اجرا و گزارش نتیجه برای اعضای همین برنامه نمایش داده می‌شود. خالی = عنوان اصلی.
              </Typography>
              <Stack spacing={1.5}>
                {p.tests.map((t) => (
                  <TextField
                    key={t.test_id}
                    size="small"
                    fullWidth
                    label={t.title}
                    placeholder="عنوان نمایشی (اختیاری)"
                    value={titles[t.test_id] ?? ""}
                    onChange={(e) => setTitles((prev) => ({ ...prev, [t.test_id]: e.target.value }))}
                  />
                ))}
              </Stack>
              <Stack direction="row" justifyContent="flex-end" sx={{ mt: 1.5 }}>
                <Button variant="contained" startIcon={<SaveRoundedIcon />} disabled={saveTitles.isPending} onClick={() => saveTitles.mutate()}>
                  ذخیرهٔ عنوان‌های نمایشی
                </Button>
              </Stack>
            </Box>
          )}
        </Paper>
      </Grid>

      {/* وضعیت و راهنما */}
      <Grid item xs={12} md={7}>
        <Paper sx={{ p: 2.5, borderRadius: 3 }}>
          <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 1.5 }}>
            وضعیت، مهلت و راهنمای پروژه
          </Typography>
          <Stack spacing={2}>
            <Stack direction="row" spacing={1.5}>
              <FormControl size="small" sx={{ minWidth: 170 }}>
                <InputLabel>وضعیت برنامه</InputLabel>
                <Select label="وضعیت برنامه" value={status} onChange={(e) => setStatus(e.target.value)}>
                  <MenuItem value="active">فعال</MenuItem>
                  <MenuItem value="draft">پیش‌نویس</MenuItem>
                  <MenuItem value="closed">پایان‌یافته</MenuItem>
                </Select>
              </FormControl>
              {/* فاز ۵۹: تقویم شمسی */}
              <Box sx={{ flex: 1 }}>
                <JalaliDateField label="مهلت انجام" value={dueDate}
                  onChange={(iso) => setDueDate(iso ?? "")} />
              </Box>
            </Stack>
            <TextField
              size="small" label="متن راهنمای پروژه (نمایش در تب راهنما)"
              multiline minRows={7} fullWidth value={guide} onChange={(e) => setGuide(e.target.value)}
            />
            <Stack direction="row" justifyContent="flex-end">
              <Button variant="contained" startIcon={<SaveRoundedIcon />} disabled={saveInfo.isPending} onClick={() => saveInfo.mutate()}>
                ذخیره
              </Button>
            </Stack>
          </Stack>
        </Paper>
      </Grid>

      {/* مشاوران پروژه */}
      <Grid item xs={12} md={5}>
        <Paper sx={{ p: 2.5, borderRadius: 3 }}>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
            <Diversity3RoundedIcon color="primary" fontSize="small" />
            <Typography variant="subtitle1" fontWeight={800}>مشاوران پروژه</Typography>
          </Stack>
          <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
            <FormControl size="small" sx={{ flex: 1 }}>
              <InputLabel>افزودن مشاور</InputLabel>
              <Select label="افزودن مشاور" value={counselorPick} onChange={(e) => setCounselorPick(e.target.value)}>
                {(directory.data ?? []).map((u) => (
                  <MenuItem key={u.id} value={u.id}>{u.display_name ?? u.username}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField size="small" label="نقش" sx={{ width: 130 }} value={counselorRole} onChange={(e) => setCounselorRole(e.target.value)} />
            <Button variant="contained" disabled={!counselorPick || addCounselor.isPending} onClick={() => addCounselor.mutate()}>
              افزودن
            </Button>
          </Stack>
          {p.counselors.length === 0 ? (
            <Typography variant="body2" color="text.secondary">مشاوری اضافه نشده است.</Typography>
          ) : (
            <Stack spacing={1}>
              {p.counselors.map((c) => (
                <Stack key={c.id} direction="row" alignItems="center" spacing={1} sx={{ p: 1, borderRadius: 2, bgcolor: "action.hover" }}>
                  <Box flex={1}>
                    <Typography variant="body2" fontWeight={700}>{c.display_name ?? c.username}</Typography>
                    <Typography variant="caption" color="text.secondary">{c.role_in_project}</Typography>
                  </Box>
                  <Button size="small" color="error" onClick={() => removeCounselor.mutate(c.id)}>حذف</Button>
                </Stack>
              ))}
            </Stack>
          )}
        </Paper>
      </Grid>

      {/* سوالات پرتکرار */}
      <Grid item xs={12}>
        <Paper sx={{ p: 2.5, borderRadius: 3 }}>
          <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 1.5 }}>
            سوالات پرتکرار ({faqs.length} ردیف)
          </Typography>
          <Stack spacing={1.5}>
            {faqs.map((f, i) => (
              <Stack key={i} direction="row" spacing={1} alignItems="flex-start">
                <TextField
                  size="small" label={`سوال ${i + 1}`} sx={{ flex: 2 }}
                  value={f.question}
                  onChange={(e) => setFaqs(faqs.map((x, j) => (j === i ? { ...x, question: e.target.value } : x)))}
                />
                <TextField
                  size="small" label="پاسخ" sx={{ flex: 3 }}
                  value={f.answer}
                  onChange={(e) => setFaqs(faqs.map((x, j) => (j === i ? { ...x, answer: e.target.value } : x)))}
                />
                <Button color="error" sx={{ mt: 0.5 }} onClick={() => setFaqs(faqs.filter((_, j) => j !== i))}>
                  حذف
                </Button>
              </Stack>
            ))}
            <Box>
              <Button startIcon={<AddRoundedIcon />} onClick={() => setFaqs([...faqs, { question: "", answer: "" }])}>
                افزودن سوال
              </Button>
            </Box>
            <Stack direction="row" justifyContent="flex-end">
              <Button variant="contained" startIcon={<SaveRoundedIcon />} disabled={saveFaq.isPending} onClick={() => saveFaq.mutate()}>
                ذخیرهٔ سوالات پرتکرار
              </Button>
            </Stack>
          </Stack>
        </Paper>
      </Grid>
    </Grid>
  );
}
