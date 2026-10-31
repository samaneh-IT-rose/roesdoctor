// فاز ۴۷ - B37 مرکز آزمون روان‌شناسی: کاتالوگ کارتی (الهام از پلتفرم‌های آزمون)،
// نتایج من با ریزنمره زیرمقیاس‌ها و مدیریت ابزارها برای مدیران
// فاز ۶۳ - «گزارش کامل» نتایج: دیالوگ گزارش تحلیلی چندلایه (snapshot)
import {
  Alert, Box, Button, Card, CardActionArea, Chip, Dialog, DialogActions, DialogContent,
  DialogTitle, Grid, InputAdornment, MenuItem, Paper, Snackbar, Stack, Tab, Tabs, TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { formatJalaliDateTime } from "../utils/jalali";
import { errDetail } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { fetchTopics } from "../api/topics";
import {
  PsychAttempt, PsychInterpretation, PsychQuestion, PsychTest,
  addInterpretation, addPsychQuestion, createPsychTest, fetchInterpretations,
  fetchMyPsychResults, fetchPsychAttempts, fetchPsychQuestions, fetchPsychTests,
  fetchPublicPsychTests, markAttemptViewed, reviewPsychTest, submitPsychTestForReview,
} from "../api/psych";
import { EmptyState, FormSection, OptionsEditor, OptionRow } from "../components/FormKit";
import PsychResultReport from "../components/PsychResultReport";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import TimerRoundedIcon from "@mui/icons-material/TimerRounded";
import HelpOutlineRoundedIcon from "@mui/icons-material/HelpOutlineRounded";
import CategoryRoundedIcon from "@mui/icons-material/CategoryRounded";
import PlayCircleOutlineRoundedIcon from "@mui/icons-material/PlayCircleOutlineRounded";
import PrintRoundedIcon from "@mui/icons-material/PrintRounded";

const CATEGORY_COLORS: Record<string, string> = {
  "سلامت روان": "#b04a5a",
  "فردی": "#7a5c8a",
  "زوج و خانواده": "#c4767f",
  "شغلی": "#5c8a72",
  "هوش": "#4a7ba6",
  "خلاقیت": "#c98a2d",
  "تحصیلی": "#4a6fa6",
  "سبک زندگی": "#3f8f7a",
};

const topicColor = (name: string | null) =>
  CATEGORY_COLORS[name ?? ""] ?? "#8a757c";

/** تخمین مدت برگزاری: هر سؤال ~۲۰ ثانیه */
const estMinutes = (q: number) => Math.max(2, Math.ceil((q * 20) / 60));

export default function PsychTestCenterPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const canManage = roles.includes("SYSTEM_ADMIN") || roles.includes("ORG_MANAGER");
  const canReview = roles.includes("TECHNICAL_SUPERVISOR");

  const [tab, setTab] = useState(0);
  const [search, setSearch] = useState("");
  const [topicFilter, setTopicFilter] = useState("");

  const catalog = useQuery({ queryKey: ["public-psych-tests"], queryFn: fetchPublicPsychTests });
  const myResults = useQuery({ queryKey: ["my-psych-results"], queryFn: fetchMyPsychResults, enabled: tab === 1 });
  const adminTests = useQuery({ queryKey: ["psych-tests"], queryFn: fetchPsychTests, enabled: tab === 2 });

  const filtered = useMemo(() => {
    const items = catalog.data ?? [];
    return items.filter((t) => {
      const okSearch = !search || t.title.includes(search) || (t.description ?? "").includes(search);
      const okTopic = !topicFilter || t.topic_name === topicFilter;
      return okSearch && okTopic;
    });
  }, [catalog.data, search, topicFilter]);

  const topicCounts = useMemo(() => {
    const counts = new Map<string, number>();
    (catalog.data ?? []).forEach((t) => {
      if (t.topic_name) counts.set(t.topic_name, (counts.get(t.topic_name) ?? 0) + 1);
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [catalog.data]);

  return (
    <Stack spacing={2.5}>
      <Box>
        <Typography variant="h5" fontWeight={800}>مرکز آزمون روان‌شناسی</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          ابزارهای غربالگری استاندارد را انجام دهید، نتیجه و ریزنمره ابعاد را ببینید و در صورت نیاز
          برای مشاوره اقدام کنید. نتیجه هر آزمون در «نتایج من» نگهداری می‌شود.
        </Typography>
      </Box>

      <Paper sx={{ px: 1.5, py: 0.5 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="آزمون‌ها" />
          <Tab label="نتایج من" />
          {(canManage || canReview) && <Tab label="مدیریت ابزارها (ناظر علمی)" />}
        </Tabs>
      </Paper>

      {tab === 0 && (
        <>
          {/* فیلترها */}
          <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap alignItems="center">
            <TextField
              size="small" sx={{ minWidth: 260 }}
              placeholder="جست‌وجوی آزمون…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchRoundedIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
            <Chip
              label={`همه (${catalog.data?.length ?? 0})`}
              color={!topicFilter ? "primary" : "default"}
              variant={!topicFilter ? "filled" : "outlined"}
              onClick={() => setTopicFilter("")}
            />
            {topicCounts.map(([name, n]) => (
              <Chip
                key={name}
                label={`${name} (${n})`}
                variant={topicFilter === name ? "filled" : "outlined"}
                sx={topicFilter === name ? { bgcolor: topicColor(name), color: "#fff" } : {}}
                onClick={() => setTopicFilter(topicFilter === name ? "" : name)}
              />
            ))}
          </Stack>

          {catalog.isLoading && <Typography>در حال بارگذاری…</Typography>}
          {!catalog.isLoading && filtered.length === 0 && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <EmptyState title="آزمونی یافت نشد"
                desc="عبارت جست‌وجو یا فیلتر دسته را تغییر دهید. اگر هنوز ابزاری منتشر نشده، از تب مدیریت ابزارها شروع کنید." />
            </Paper>
          )}

          {/* فاز ۵۷ - نمایش گروه‌بندی‌شده بر اساس دسته (در جست‌وجو: نمایش تخت) */}
          {!catalog.isLoading && (search ? (
            <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr" }} gap={2}>
              {filtered.map((t) => (
                <TestCard key={t.id} test={t} color={t.accent_color || topicColor(t.topic_name)}
                  code={t.code || ""}
                  onRun={() => navigate(`/psych-tests/${t.slug}/run`)} />
              ))}
            </Box>
          ) : (
            <Stack spacing={3}>
              {topicCounts.filter(([name]) => filtered.some((t) => t.topic_name === name)).map(([name, count]) => (
                <Box key={name}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.25 }}>
                    <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: topicColor(name) }} />
                    <Typography variant="subtitle1" fontWeight={800}>{name}</Typography>
                    <Chip size="small" variant="outlined" sx={{ height: 22, fontSize: 11 }}
                      label={`${count.toLocaleString("fa-IR")} آزمون`} />
                  </Stack>
                  <Box display="grid" gridTemplateColumns={{ xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr" }} gap={2}>
                    {filtered.filter((t) => t.topic_name === name).map((t) => (
                      <TestCard key={t.id} test={t} color={t.accent_color || topicColor(t.topic_name)}
                        code={t.code || ""}
                        onRun={() => navigate(`/psych-tests/${t.slug}/run`)} />
                    ))}
                  </Box>
                </Box>
              ))}
            </Stack>
          ))}
        </>
      )}

      {tab === 1 && <MyResultsTable results={myResults.data ?? []} />}

      {tab === 2 && (canManage || canReview) && (
        <AdminTestsTab tests={adminTests.data ?? []} canManage={canManage} canReview={canReview} />
      )}

      <Snackbar open={!!catalog.error} autoHideDuration={5000}>
        <Alert severity="error">{errDetail(catalog.error)}</Alert>
      </Snackbar>
    </Stack>
  );
}

function TestCard({ test, color, code, onRun }: {
  test: {
    title: string; description: string | null; topic_name: string | null; question_count: number;
    age_range?: string | null; estimated_minutes?: number | null;
  };
  color: string; code: string; onRun: () => void;
}) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 3, height: "100%", display: "flex", flexDirection: "column" }}>
      <CardActionArea onClick={onRun} sx={{ display: "flex", alignItems: "stretch", height: "100%" }}>
        {/* زبانه رنگی سمت راست مانند کارت‌های آزمون مرجع (کد ابزار عمودی) */}
        <Box sx={{ width: 42, bgcolor: color, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "0 14px 14px 0" }}>
          <Typography sx={{ transform: "rotate(90deg)", whiteSpace: "nowrap", fontSize: 11, fontWeight: 700, letterSpacing: 0.5 }}>
            {code || test.title.slice(0, 12)}
          </Typography>
        </Box>
        <Stack sx={{ p: 2, flexGrow: 1 }} spacing={0.75}>
          <Typography variant="subtitle2" fontWeight={800} sx={{ lineHeight: 1.6 }}>
            {test.title}
          </Typography>
          {test.description && (
            <Typography variant="caption" color="text.secondary" sx={{
              display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
            }}>
              {test.description}
            </Typography>
          )}
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: "auto", pt: 1 }}>
            <Chip size="small" variant="outlined" icon={<CategoryRoundedIcon />} sx={{ height: 24, fontSize: 11 }}
              label={test.topic_name ?? "بدون دسته"} />
            <Stack direction="row" spacing={0.4} alignItems="center">
              <HelpOutlineRoundedIcon sx={{ fontSize: 15, color: "text.secondary" }} />
              <Typography variant="caption" color="text.secondary">{test.question_count.toLocaleString("fa-IR")} سؤال</Typography>
            </Stack>
            <Stack direction="row" spacing={0.4} alignItems="center">
              <TimerRoundedIcon sx={{ fontSize: 15, color: "text.secondary" }} />
              <Typography variant="caption" color="text.secondary">
                ~{(test.estimated_minutes ?? estMinutes(test.question_count)).toLocaleString("fa-IR")} دقیقه
              </Typography>
            </Stack>
            {test.age_range && (
              <Typography variant="caption" color="text.secondary" sx={{ width: "100%" }}>
                {test.age_range}
              </Typography>
            )}
          </Stack>
        </Stack>
      </CardActionArea>
      <Button variant="contained" startIcon={<PlayCircleOutlineRoundedIcon />} onClick={onRun}
        sx={{ borderRadius: "0 0 14px 14px", py: 1 }}>
        شروع آزمون
      </Button>
    </Card>
  );
}

function MyResultsTable({ results }: { results: PsychAttempt[] }) {
  const [report, setReport] = useState<PsychAttempt | null>(null);
  const qc = useQueryClient();
  // فاز ۷۰ - بازکردن «گزارش کامل» = ثبت زمان دیده‌شدن نتیجه
  const viewedMut = useMutation({
    mutationFn: markAttemptViewed,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["my-psych-results"] }),
  });
  const openReport = (a: PsychAttempt) => {
    setReport(a);
    if (!a.viewed_at) viewedMut.mutate(a.id);
  };
  return (
    <Stack spacing={1.5}>
      {results.length === 0 && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <EmptyState title="هنوز آزمونی انجام نداده‌اید"
            desc="از تب «آزمون‌ها» یک ابزار انتخاب کنید و شروع کنید." />
        </Paper>
      )}
      {results.map((a) => (
        <Paper key={a.id} variant="outlined" sx={{ p: 2 }}>
          <Stack direction="row" justifyContent="space-between" flexWrap="wrap" gap={1} useFlexGap>
            <Box>
              <Typography variant="subtitle2" fontWeight={800}>{a.test_title ?? "آزمون"}</Typography>
              <Typography variant="caption" color="text.secondary">
                {a.interpretation_label}
                {a.viewed_at ? ` — دیده‌شده: ${formatJalaliDateTime(a.viewed_at)}` : " — دیده‌نشده"}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              {a.subscale_scores && Object.entries(a.subscale_scores).length > 0 && (
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                  {Object.entries(a.subscale_scores).slice(0, 6).map(([k, v]) => (
                    <Chip key={k} size="small" variant="outlined" sx={{ height: 22, fontSize: 11 }}
                      label={`${k}: ${v.toLocaleString("fa-IR")}`} />
                  ))}
                  {Object.entries(a.subscale_scores).length > 6 && (
                    <Chip size="small" variant="outlined" sx={{ height: 22, fontSize: 11 }}
                      label={`+${(Object.entries(a.subscale_scores).length - 6).toLocaleString("fa-IR")}`} />
                  )}
                </Stack>
              )}
              <Chip color="primary" label={`نمره: ${a.score.toLocaleString("fa-IR")}`} />
              {a.result_payload && (
                <Button size="small" variant="contained" onClick={() => openReport(a)}>
                  گزارش کامل
                </Button>
              )}
            </Stack>
          </Stack>
        </Paper>
      ))}
      {/* فاز ۶۳ - دیالوگ گزارش کامل (از snapshot بدون رفت‌وبرگشت سرور) */}
      <Dialog open={!!report} onClose={() => setReport(null)} maxWidth="md" fullWidth
        PaperProps={{ sx: { borderRadius: 3 } }}>
        <DialogTitle sx={{ fontWeight: 800 }}>
          گزارش کامل — {report?.test_title}
        </DialogTitle>
        <DialogContent dividers>
          {report?.result_payload && (
            <PsychResultReport payload={report.result_payload} attempt={report} testTitle={report.test_title ?? undefined} />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => window.print()} startIcon={<PrintRoundedIcon />}>چاپ</Button>
          <Button onClick={() => setReport(null)}>بستن</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

// ---------------------------------------------------------------- مدیریت
function AdminTestsTab({ tests, canManage, canReview }: {
  tests: PsychTest[]; canManage: boolean; canReview: boolean;
}) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [detail, setDetail] = useState<PsychTest | null>(null);
  const [rejectOpen, setRejectOpen] = useState<PsychTest | null>(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["psych-tests"] });
    qc.invalidateQueries({ queryKey: ["psych-questions"] });
    qc.invalidateQueries({ queryKey: ["psych-interps"] });
    qc.invalidateQueries({ queryKey: ["public-psych-tests"] });
  };

  const createMut = useMutation({
    mutationFn: createPsychTest,
    onSuccess: () => { invalidate(); setCreateOpen(false); setOkMsg("ابزار پیش‌نویس ایجاد شد"); },
    onError: (e) => setError(errDetail(e)),
  });
  const submitReviewMut = useMutation({
    mutationFn: submitPsychTestForReview,
    onSuccess: () => { invalidate(); setOkMsg("برای بازبینی ناظر علمی ارسال شد"); },
    onError: (e) => setError(errDetail(e)),
  });
  const reviewMut = useMutation({
    mutationFn: ({ id, approve, note }: { id: string; approve: boolean; note?: string }) =>
      reviewPsychTest(id, { approve, note }),
    onSuccess: (t) => {
      invalidate(); setRejectOpen(null);
      setOkMsg(t.status === "published" ? "ابزار با تأیید ناظر علمی منتشر شد" : "ابزار رد شد");
    },
    onError: (e) => setError(errDetail(e)),
  });

  const stChip = (s: string) => {
    const map: Record<string, { label: string; color: "success" | "default" | "warning" | "error" | "info" }> = {
      draft: { label: "پیش‌نویس", color: "default" },
      pending_review: { label: "در انتظار ناظر علمی", color: "warning" },
      published: { label: "منتشرشده", color: "success" },
      rejected: { label: "رد‌شده", color: "error" },
    };
    const it = map[s] ?? { label: s, color: "default" as const };
    return <Chip size="small" variant="outlined" label={it.label} color={it.color} />;
  };

  return (
    <Stack spacing={2}>
      <Alert severity="info">
        چرخه ابزار: پیش‌نویس → ارسال برای بازبینی → تأیید/رد ناظر علمی (D08). ویرایش ابزار منتشرشده
        آن را به پیش‌نویس برمی‌گرداند و باید دوباره تأیید شود.
      </Alert>
      <Box display="flex" justifyContent="flex-end">
        <Button variant="contained" onClick={() => setCreateOpen(true)}>ابزار جدید</Button>
      </Box>

      {tests.length === 0 && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <EmptyState title="ابزاری ثبت نشده"
            desc="با دکمه «ابزار جدید» یک ابزار بسازید، سؤال و بازه تفسیر اضافه کنید و برای بازبینی ارسال کنید. بانک آماده را نیز می‌توانید با seed_psych_tests.py بارگذاری کنید." />
        </Paper>
      )}

      {tests.map((t) => (
        <Paper key={t.id} variant="outlined" sx={{ p: 2 }}>
          <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
            <Typography variant="subtitle2" fontWeight={800}>{t.title}</Typography>
            {stChip(t.status)}
            <Chip size="small" variant="outlined" label={`${(t.question_count ?? 0).toLocaleString("fa-IR")} سؤال`} />
            <Chip size="small" variant="outlined" label={`${(t.attempt_count ?? 0).toLocaleString("fa-IR")} اجرا`} />
            {t.review_note && (
              <Typography variant="caption" color="text.secondary">یادداشت ناظر: {t.review_note}</Typography>
            )}
            <Box flexGrow={1} />
            {canManage && (t.status === "draft" || t.status === "rejected") && (
              <Button size="small" variant="outlined" onClick={() => submitReviewMut.mutate(t.id)}>
                ارسال برای بازبینی
              </Button>
            )}
            {canReview && t.status === "pending_review" && (
              <>
                <Button size="small" color="success" variant="contained"
                  onClick={() => reviewMut.mutate({ id: t.id, approve: true, note: "تأیید علمی" })}>
                  تأیید (ناظر)
                </Button>
                <Button size="small" color="error" onClick={() => setRejectOpen(t)}>رد</Button>
              </>
            )}
            {canManage && <Button size="small" variant="contained" onClick={() => setDetail(t)}>مدیریت سؤال و تفسیر</Button>}
          </Stack>
        </Paper>
      ))}

      <CreateTestDialog open={createOpen} onClose={() => setCreateOpen(false)}
        onSubmit={(p) => createMut.mutate(p)} loading={createMut.isPending} />

      {detail && (
        <TestDetailDialog test={detail} onClose={() => setDetail(null)} onChanged={invalidate} />
      )}

      {rejectOpen && (
        <RejectDialog loading={reviewMut.isPending}
          onClose={() => setRejectOpen(null)}
          onSubmit={(note) => reviewMut.mutate({ id: rejectOpen.id, approve: false, note })} />
      )}

      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
      <Snackbar open={!!okMsg} autoHideDuration={4000} onClose={() => setOkMsg(null)}>
        <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>
      </Snackbar>
    </Stack>
  );
}

function CreateTestDialog({ open, onClose, onSubmit, loading }: {
  open: boolean; onClose: () => void; loading: boolean;
  onSubmit: (p: Record<string, unknown>) => void;
}) {
  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const topics = useQuery({ queryKey: ["topics"], queryFn: () => fetchTopics(true) });
  const [topicId, setTopicId] = useState("");
  const submit = () => {
    onSubmit({ slug: slug.trim(), title: title.trim(), description, topic_id: topicId || null });
    setSlug(""); setTitle(""); setDescription(""); setTopicId("");
  };
  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>ابزار تست جدید (پیش‌نویس)</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          <TextField required label="شناسه لاتین (slug)" dir="ltr" value={slug}
            onChange={(e) => setSlug(e.target.value)} helperText="مثلاً bdi-ii — فقط حروف کوچک لاتین، عدد و خط تیره" />
          <TextField required label="عنوان ابزار" value={title} onChange={(e) => setTitle(e.target.value)} />
          <TextField label="توضیح (متر، مدت، گروه سنی…)" multiline minRows={2}
            value={description} onChange={(e) => setDescription(e.target.value)} />
          <TextField select label="دسته موضوعی (اختیاری)" value={topicId}
            onChange={(e) => setTopicId(e.target.value)}>
            <MenuItem value="">— بدون دسته —</MenuItem>
            {(topics.data ?? []).map((t) => <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>)}
          </TextField>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={loading || !slug.trim() || !title.trim()} onClick={submit}>
          ایجاد
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function TestDetailDialog({ test, onClose, onChanged }: {
  test: PsychTest; onClose: () => void; onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const questions = useQuery({ queryKey: ["psych-questions", test.id], queryFn: () => fetchPsychQuestions(test.id) });
  const interps = useQuery({ queryKey: ["psych-interps", test.id], queryFn: () => fetchInterpretations(test.id) });
  const attempts = useQuery({ queryKey: ["psych-attempts", test.id], queryFn: () => fetchPsychAttempts(test.id) });

  const qMut = useMutation({
    mutationFn: (p: { prompt: string; options: OptionRow[]; subscale?: string | null }) =>
      addPsychQuestion(test.id, { prompt: p.prompt, options: p.options, subscale: p.subscale ?? null }),
    onSuccess: () => onChanged(),
    onError: (e) => setError(errDetail(e)),
  });
  const iMut = useMutation({
    mutationFn: (p: { score_min: number; score_max: number; label: string; guidance?: string }) =>
      addInterpretation(test.id, p),
    onSuccess: () => onChanged(),
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>مدیریت «{test.title}»</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          {error && <Alert severity="error">{error}</Alert>}

          <QuestionAddForm onSubmit={(p) => qMut.mutate(p)} />

          <FormSection title={`سؤال‌ها (${questions.data?.length ?? 0})`} subtitle="گزینه‌ها و امتیاز هر گزینه — نمره کل = جمع امتیازها">
            {!(questions.data ?? []).length ? (
              <EmptyState title="سؤالی ثبت نشده" desc="با فرم بالا نخستین سؤال را اضافه کنید." />
            ) : (
              <Stack spacing={1}>
                {(questions.data ?? []).map((q: PsychQuestion) => (
                  <Paper key={q.id} variant="outlined" sx={{ p: 1.25 }}>
                    <Stack direction="row" spacing={1} alignItems="flex-start">
                      {q.subscale && <Chip size="small" sx={{ height: 22, fontSize: 11 }} color="secondary" label={q.subscale} />}
                      <Typography variant="body2" fontWeight={700} sx={{ flexGrow: 1 }}>{q.prompt}</Typography>
                    </Stack>
                    <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                      {q.options.map((o) => `${o.label} (${o.score})`).join("  •  ")}
                    </Typography>
                  </Paper>
                ))}
              </Stack>
            )}
          </FormSection>

          <InterpAddForm onSubmit={(p) => iMut.mutate(p)} />
          <FormSection title={`بازه‌های تفسیر (${interps.data?.length ?? 0})`} subtitle="نمره کل در بازه‌ها تفسیر می‌شود">
            {!(interps.data ?? []).length ? (
              <EmptyState title="بازه‌ای ثبت نشده" desc="تأیید ناظر علمی بدون حداقل یک بازه تفسیر ممکن نیست." />
            ) : (
              <Stack spacing={1}>
                {(interps.data ?? []).map((i: PsychInterpretation) => (
                  <Paper key={i.id} variant="outlined" sx={{ p: 1.25 }}>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                      <Chip size="small" color="primary" variant="outlined" label={`${i.score_min} تا ${i.score_max}`} />
                      <Typography variant="body2" fontWeight={700}>{i.label}</Typography>
                      {i.guidance && <Typography variant="caption" color="text.secondary">{i.guidance}</Typography>}
                    </Stack>
                  </Paper>
                ))}
              </Stack>
            )}
          </FormSection>

          <Typography variant="subtitle2" fontWeight={700}>اجراها ({attempts.data?.length ?? 0})</Typography>
          {(attempts.data ?? []).map((a: PsychAttempt) => (
            <Paper key={a.id} variant="outlined" sx={{ p: 1.25 }}>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                <Chip size="small" color="primary" label={`نمره ${a.score}`} />
                <Typography variant="body2" fontWeight={700}>{a.interpretation_label}</Typography>
                {a.subscale_scores && Object.entries(a.subscale_scores).map(([k, v]) => (
                  <Chip key={k} size="small" variant="outlined" sx={{ height: 22, fontSize: 11 }} label={`${k}: ${v}`} />
                ))}
              </Stack>
            </Paper>
          ))}
          {!(attempts.data ?? []).length && (
            <Typography variant="caption" color="text.secondary">اجرایی ثبت نشده است.</Typography>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

function QuestionAddForm({ onSubmit }: {
  onSubmit: (p: { prompt: string; options: OptionRow[]; subscale?: string | null }) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [subscale, setSubscale] = useState("");
  const [options, setOptions] = useState<OptionRow[]>([
    { label: "هرگز", score: 0 }, { label: "گاهی", score: 1 },
    { label: "اغلب", score: 2 }, { label: "همیشه", score: 3 },
  ]);
  const [optError, setOptError] = useState<string | null>(null);
  const submit = () => {
    if (!prompt.trim()) return;
    if (options.some((o) => !o.label.trim())) {
      setOptError("متن همه گزینه‌ها را کامل کنید.");
      return;
    }
    if (options.length < 2) {
      setOptError("حداقل دو گزینه لازم است.");
      return;
    }
    setOptError(null);
    onSubmit({ prompt: prompt.trim(), options, subscale: subscale.trim() || null });
    setPrompt("");
    setSubscale("");
  };
  return (
    <FormSection title="افزودن سؤال جدید" step="+"
      subtitle="متن سؤال، نام زیرمقیاس (اختیاری) و گزینه‌ها با امتیاز هر گزینه">
      <Stack spacing={2}>
        <TextField label="متن سؤال" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        <TextField label="زیرمقیاس (اختیاری — مثلاً اضطراب)" value={subscale}
          onChange={(e) => setSubscale(e.target.value)} />
        <OptionsEditor options={options} onChange={setOptions} error={optError} />
        <Button variant="contained" onClick={submit} sx={{ alignSelf: "flex-start" }}>افزودن سؤال</Button>
      </Stack>
    </FormSection>
  );
}

function InterpAddForm({ onSubmit }: {
  onSubmit: (p: { score_min: number; score_max: number; label: string; guidance?: string }) => void;
}) {
  const [min, setMin] = useState("0");
  const [max, setMax] = useState("4");
  const [label, setLabel] = useState("");
  const [guidance, setGuidance] = useState("");
  const submit = () => {
    if (!label.trim()) return;
    onSubmit({ score_min: Number(min) || 0, score_max: Number(max) || 0, label: label.trim(), guidance: guidance.trim() || undefined });
    setLabel("");
    setGuidance("");
  };
  return (
    <FormSection title="افزودن بازه تفسیر" step="+"
      subtitle="محدوده نمره، برچسب تفسیر و راهنمای پیشنهادی">
      <Grid container spacing={1.5}>
        <Grid item xs={6} sm={3}>
          <TextField fullWidth type="number" label="از نمره" value={min} onChange={(e) => setMin(e.target.value)} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <TextField fullWidth type="number" label="تا نمره" value={max} onChange={(e) => setMax(e.target.value)} />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField fullWidth label="برچسب تفسیر" value={label} onChange={(e) => setLabel(e.target.value)} />
        </Grid>
        <Grid item xs={12}>
          <TextField fullWidth label="راهنما / توصیه (اختیاری)" value={guidance} onChange={(e) => setGuidance(e.target.value)} />
        </Grid>
        <Grid item xs={12}>
          <Button variant="contained" onClick={submit} disabled={!label.trim()}>افزودن بازه</Button>
        </Grid>
      </Grid>
    </FormSection>
  );
}

function RejectDialog({ onClose, onSubmit, loading }: {
  onClose: () => void; loading: boolean; onSubmit: (note: string) => void;
}) {
  const [note, setNote] = useState("");
  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>رد ابزار — یادداشت ناظر علمی الزامی است</DialogTitle>
      <DialogContent>
        <TextField required multiline minRows={3} fullWidth value={note}
          onChange={(e) => setNote(e.target.value)} label="یادداشت" sx={{ mt: 1 }} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button color="error" variant="contained" disabled={loading || !note.trim()} onClick={() => onSubmit(note.trim())}>
          رد ابزار
        </Button>
      </DialogActions>
    </Dialog>
  );
}
