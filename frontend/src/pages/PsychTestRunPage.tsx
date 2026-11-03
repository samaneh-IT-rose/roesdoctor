// فاز ۴۷ - اجرای آزمون روان‌شناسی: سؤال‌به‌سؤال با نوار پیشرفت، پالت سؤال‌ها،
// صفحه نتیجه با گیج نمره و نمودار ریزنمره زیرمقیاس‌ها
// فاز ۵۰ - مرحله «مشخصات اولیه» مطابق فرم مرجع (جنسیت/سن/تحصیلات/تأهل)
// و نمایش عکس پیوست سؤال‌های تصویری (ریون)
// فاز ۶۳ - صفحه نتیجه: گزارش تحلیلی چندلایه (رادار + منحنی جایگاه + وجه‌ها + تفسیر سطح‌بندی‌شده)
import {
  Alert, Box, Button, Chip, CircularProgress, FormControl, LinearProgress, MenuItem,
  Paper, Stack, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { errDetail } from "../api/client";
import {
  AttemptResult, TestDemographics, fetchPublicPaper, submitPsychAttempt,
} from "../api/psych";
import PsychResultReport, { ScoreGauge } from "../components/PsychResultReport";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import ArrowForwardRoundedIcon from "@mui/icons-material/ArrowForwardRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import CircleRoundedIcon from "@mui/icons-material/CircleRounded";
import PrintRoundedIcon from "@mui/icons-material/PrintRounded";
import ListAltRoundedIcon from "@mui/icons-material/ListAltRounded";

export default function PsychTestRunPage() {
  const { slug = "" } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  // فاز ۷۵ — برندینگ سازمانی: اگر از کارتابل برنامهٔ سازمانی آمده باشیم
  // (?program=ID) عنوان نمایشی و لوگو/پیام سازمان برگردانده می‌شود.
  const [searchParams] = useSearchParams();
  const programId = searchParams.get("program") ?? "";

  const paper = useQuery({
    queryKey: ["psych-paper", slug, programId],
    queryFn: () => fetchPublicPaper(slug, programId || undefined),
  });

  const [started, setStarted] = useState(false);
  const [demographicsStep, setDemographicsStep] = useState(false);
  const [demographics, setDemographics] = useState<TestDemographics>({});
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [current, setCurrent] = useState(0);
  const [showPalette, setShowPalette] = useState(false);
  const [result, setResult] = useState<AttemptResult | null>(null);

  const questions = paper.data?.questions ?? [];
  // عنوان مؤثر: عنوان نمایشی برنامهٔ سازمانی (در صورت وجود) وگرنه عنوان آزمون
  const effTitle = paper.data?.effective_title || paper.data?.test.title || "";
  const branding = paper.data?.branding ?? null;
  // بیشینه نمره هر سؤال = اندیس آخرین گزینه (گزینه‌ها در همه ابزارهای درج‌شده صعودی‌اند)
  const questionMax = (qi: number) => (questions[qi]?.options.length ? questions[qi].options.length - 1 : 0);
  const totalMax = useMemo(
    () => questions.reduce((acc, _q, qi) => acc + questionMax(qi), 0),
    [questions],
  );

  const submitMut = useMutation({
    mutationFn: () => submitPsychAttempt(slug, questions.map((_, i) => answers[i]), demographics),
    onSuccess: (res) => setResult(res),
  });

  const answeredCount = Object.keys(answers).length;
  const progress = questions.length ? (answeredCount / questions.length) * 100 : 0;
  // فاز ۷۵ — رفع «گیر کردن روی سؤال آخر»: اگر سؤالی بی‌پاسخ مانده باشد
  // دکمهٔ پایانی به اولین سؤال بی‌پاسخ می‌پرد و راهنما نشان می‌دهد.
  const firstUnanswered = useMemo(
    () => questions.findIndex((_, i) => answers[i] === undefined),
    [questions, answers],
  );
  const [jumpHint, setJumpHint] = useState<string | null>(null);

  const tryFinish = () => {
    if (firstUnanswered >= 0) {
      setCurrent(firstUnanswered);
      setJumpHint(
        `پاسخ سؤال ${(firstUnanswered + 1).toLocaleString("fa-IR")} هنوز ثبت نشده است — به همان سؤال رفتید`,
      );
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    setJumpHint(null);
    submitMut.mutate();
  };

  const pick = (optIdx: number) => {
    setAnswers((p) => ({ ...p, [current]: optIdx }));
    // پرش خودکار به سؤال بعد (با تأخیر کوتاه برای حس پاسخ‌گویی)
    setTimeout(() => {
      if (current < questions.length - 1) setCurrent((c) => c + 1);
    }, 220);
  };

  // -------------------------------------------------- نتیجه
  if (result) {
    const a = result.attempt;
    const subs = Object.entries(a.subscale_scores ?? {});
    const report = a.result_payload ?? null;
    return (
      <Stack sx={{ maxWidth: 860, mx: "auto", py: 2 }}>
        <Stack spacing={2.5}>
          <Paper sx={{ p: 2, textAlign: "center" }}>
            <Stack direction="row" spacing={1} justifyContent="center" alignItems="center" flexWrap="wrap" useFlexGap>
              <CheckCircleRoundedIcon color="success" />
              <Typography variant="body2" fontWeight={700}>نتیجهٔ آزمون شما ثبت شد</Typography>
            </Stack>
          </Paper>

          {report ? (
            <PsychResultReport payload={report} attempt={a} testTitle={effTitle} />
          ) : (
            <Paper sx={{ p: 3, textAlign: "center" }}>
              <Typography variant="h6" fontWeight={800} mt={1}>{effTitle}</Typography>
              <Stack alignItems="center" mt={2}>
                <ScoreGauge score={a.score} max={totalMax} label={a.interpretation_label} />
              </Stack>
              {a.interpretation_guidance && (
                <Alert severity="info" sx={{ mt: 2, textAlign: "right" }}>
                  {a.interpretation_guidance}
                </Alert>
              )}
              {subs.length > 0 && (
                <Box sx={{ mt: 2.5, textAlign: "right" }}>
                  <Typography variant="subtitle1" fontWeight={800} mb={2}>ریزنمرهٔ ابعاد</Typography>
                  <Stack spacing={1.5}>
                    {subs.map(([name, val]) => {
                      const subMax = questions
                        .filter((q) => q.subscale === name)
                        .reduce((acc, q) => acc + questionMax(questions.indexOf(q)), 0);
                      const pct = subMax > 0 ? (val / subMax) * 100 : 0;
                      return (
                        <Box key={name}>
                          <Stack direction="row" justifyContent="space-between" mb={0.5}>
                            <Typography variant="body2" fontWeight={700}>{name}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              {val.toLocaleString("fa-IR")} از {subMax.toLocaleString("fa-IR")}
                            </Typography>
                          </Stack>
                          <Box sx={{ bgcolor: "#f3e8ea", borderRadius: 99, height: 10 }}>
                            <Box sx={{
                              width: `${pct}%`, height: 10, borderRadius: 99,
                              background: "linear-gradient(90deg,#b04a5a,#7a5c8a)",
                              transition: "width .6s",
                            }} />
                          </Box>
                        </Box>
                      );
                    })}
                  </Stack>
                </Box>
              )}
            </Paper>
          )}

          <Alert severity="warning">{result.disclaimer}</Alert>

          <Stack direction="row" spacing={1.5} justifyContent="center" flexWrap="wrap" useFlexGap>
            <Button variant="outlined" startIcon={<ListAltRoundedIcon />} onClick={() => navigate("/psych-tests")}>
              آزمون‌های دیگر
            </Button>
            <Button variant="outlined" startIcon={<PrintRoundedIcon />} onClick={() => window.print()}>
              چاپ گزارش
            </Button>
          </Stack>
        </Stack>
      </Stack>
    );
  }

  // -------------------------------------------------- مرحله مشخصات اولیه (فاز ۵۰)
  if (!started && demographicsStep) {
    const set = (k: keyof TestDemographics) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setDemographics((p) => ({ ...p, [k]: e.target.value }));
    return (
      <Stack sx={{ maxWidth: 620, mx: "auto", py: 4 }}>
        <Paper sx={{ p: { xs: 2.5, md: 4 }, borderRadius: 4 }}>
          <Typography variant="h5" fontWeight={800} textAlign="center" mb={0.5}>
            مشخصات اولیه
          </Typography>
          <Typography variant="body2" color="text.secondary" textAlign="center" mb={3}>
            {effTitle} — این اطلاعات صرفاً برای پرونده آزمون ثبت می‌شود
          </Typography>
          <Stack spacing={2.5}>
            <FormControl fullWidth>
              <Typography variant="caption" fontWeight={700} mb={0.5}>جنسیت</Typography>
              <TextField select value={demographics.gender ?? ""} onChange={set("gender")}
                placeholder="انتخاب کنید">
                <MenuItem value="زن">زن</MenuItem>
                <MenuItem value="مرد">مرد</MenuItem>
              </TextField>
            </FormControl>
            <TextField label="سن" type="number" inputProps={{ min: 3, max: 99 }}
              value={demographics.age ?? ""} onChange={set("age")} />
            <FormControl fullWidth>
              <Typography variant="caption" fontWeight={700} mb={0.5}>تحصیلات</Typography>
              <TextField select value={demographics.education ?? ""} onChange={set("education")}>
                {"زیر دیپلم|دیپلم|کاردانی|کارشناسی|کارشناسی ارشد|دکتری".split("|").map((s) => (
                  <MenuItem key={s} value={s}>{s}</MenuItem>
                ))}
              </TextField>
            </FormControl>
            <FormControl fullWidth>
              <Typography variant="caption" fontWeight={700} mb={0.5}>وضعیت تاهل</Typography>
              <TextField select value={demographics.marital ?? ""} onChange={set("marital")}>
                {"مجرد|متاهل|مطلقه|همسر فوت شده".split("|").map((s) => (
                  <MenuItem key={s} value={s}>{s}</MenuItem>
                ))}
              </TextField>
            </FormControl>
            <Button variant="contained" size="large"
              sx={{
                mt: 1.5, py: 1.6, borderRadius: 3, fontSize: 17, fontWeight: 800,
                background: "linear-gradient(135deg, #14b8a6, #0d9488)",
                boxShadow: "0 8px 20px rgba(20,184,166,.35)",
                "&:hover": { background: "linear-gradient(135deg, #0d9488, #0f766e)" },
              }}
              onClick={() => setStarted(true)}>
              شروع
            </Button>
            <Button size="small" onClick={() => setDemographicsStep(false)} sx={{ alignSelf: "center" }}>
              بازگشت
            </Button>
          </Stack>
        </Paper>
      </Stack>
    );
  }

  // -------------------------------------------------- صفحه معرفی
  if (!started) {
    return (
      <Stack sx={{ maxWidth: 760, mx: "auto", py: 2 }}>
        {paper.isLoading && <CircularProgress sx={{ display: "block", mx: "auto", mt: 6 }} />}
        {paper.error && (
          <Alert severity="error">{errDetail(paper.error)}</Alert>
        )}
        {paper.data && (
          <Stack spacing={2.5}>
            <Button startIcon={<ArrowForwardRoundedIcon />} onClick={() => navigate("/psych-tests")}
              sx={{ alignSelf: "flex-start" }}>
              بازگشت به مرکز آزمون
            </Button>
            <Paper sx={{ p: 3 }}>
              {/* فاز ۷۵ — برندینگ سازمانی صفحه ورودی */}
              {branding?.brand_logo_url && (
                <Box
                  component="img"
                  src={branding.brand_logo_url}
                  alt={branding.brand_name || "لوگو"}
                  sx={{ display: "block", mx: "auto", mb: 2, maxWidth: 220, maxHeight: 110, objectFit: "contain" }}
                />
              )}
              <Typography variant="h5" fontWeight={800} textAlign="center">
                {branding?.entry_title || effTitle}
              </Typography>
              {branding?.brand_name && (
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", textAlign: "center", mt: 0.5 }}>
                  {branding.brand_name}
                </Typography>
              )}
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5, lineHeight: 2 }}>
                {branding?.entry_note || paper.data.test.description}
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap mt={2}>
                {paper.data.test.code && (
                  <Chip variant="filled" label={paper.data.test.code}
                    sx={{ bgcolor: paper.data.test.accent_color || "#8a3342", color: "#fff", fontWeight: 700 }} />
                )}
                <Chip variant="outlined" label={`${questions.length.toLocaleString("fa-IR")} سؤال`} />
                {paper.data.test.estimated_minutes != null && (
                  <Chip variant="outlined" label={`~${paper.data.test.estimated_minutes.toLocaleString("fa-IR")} دقیقه`} />
                )}
                {paper.data.test.age_range && <Chip variant="outlined" label={paper.data.test.age_range} />}
                <Chip variant="outlined" label="نتیجه فوری پس از پاسخ به همه سؤال‌ها" />
                <Chip variant="outlined" label="پاسخ‌ها محرمانه است" />
              </Stack>
            </Paper>
            <Alert severity="info">
              نکته: پاسخ «صادقانه به حالت فعلی خود» بدهید؛ پاسخ درست/غلطی وجود ندارد. می‌توانید قبل از
              ثبت نهایی، بین سؤال‌ها جابه‌جا شوید و پاسخ‌ها را تغییر دهید.
            </Alert>
            <Button variant="contained" size="large" sx={{ alignSelf: "center", px: 6, py: 1.5 }}
              onClick={() => setDemographicsStep(true)}>
              شروع آزمون
            </Button>
          </Stack>
        )}
      </Stack>
    );
  }

  // -------------------------------------------------- اجرا
  const q = questions[current];
  return (
    <Stack sx={{ maxWidth: 860, mx: "auto", py: 2 }}>
      <Stack spacing={2}>
        <Stack direction="row" alignItems="center" spacing={1.5} flexWrap="wrap" useFlexGap>
          <Typography variant="subtitle1" fontWeight={800} flexGrow={1}>
            {effTitle}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            سؤال {(current + 1).toLocaleString("fa-IR")} از {questions.length.toLocaleString("fa-IR")}
          </Typography>
          <Button size="small" variant="outlined" onClick={() => setShowPalette((s) => !s)}>
            {showPalette ? "بستن فهرست" : "فهرست سؤال‌ها"}
          </Button>
        </Stack>

        <LinearProgress variant="determinate" value={progress} sx={{ height: 8, borderRadius: 99 }} />

        {showPalette && (
          <Paper variant="outlined" sx={{ p: 1.5 }}>
            <Box display="grid" gridTemplateColumns={{ xs: "repeat(8, 1fr)", md: "repeat(12, 1fr)" }} gap={0.75}>
              {questions.map((_, i) => {
                const done = answers[i] !== undefined;
                return (
                  <Box key={i} onClick={() => setCurrent(i)}
                    sx={{
                      height: 32, borderRadius: 1.5, cursor: "pointer",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 12, fontWeight: 700,
                      bgcolor: i === current ? "primary.main" : done ? "primary.main" : "#f7eef0",
                      opacity: i === current ? 1 : done ? 0.75 : 1,
                      color: i === current || done ? "#fff" : "#8a757c",
                      outline: i === current ? "2px solid #8a3342" : "none",
                      transition: "all .15s",
                    }}>
                    {(i + 1).toLocaleString("fa-IR")}
                  </Box>
                );
              })}
            </Box>
          </Paper>
        )}

        {q && (
          <Paper sx={{ p: { xs: 2, md: 3.5 } }}>
            {/* فاز ۵۷ - در ابزارهای بلند (مثل نئو ۲۴۰) نام زیرمقیاس نشان داده نمی‌شود تا پاسخ‌دهی بی‌سوگیری بماند */}
            {q.subscale && questions.length < 100 && (
              <Chip size="small" color="secondary" variant="outlined" label={q.subscale} sx={{ mb: 1.5 }} />
            )}
            <Typography variant="h6" fontWeight={800} sx={{ lineHeight: 1.9, mb: 2.5 }}>
              {q.prompt}
            </Typography>
            {q.image_url && (
              <Box
                component="img"
                src={q.image_url}
                alt={q.prompt}
                sx={{
                  display: "block", mx: "auto", mb: 2.5, maxWidth: "100%",
                  maxHeight: 520, borderRadius: 2, border: "1px solid #ece2e4",
                  bgcolor: "#fff",
                }}
              />
            )}
            <Stack spacing={1.25}>
              {q.options.map((label, oi) => {
                const selected = answers[current] === oi;
                return (
                  <Box key={oi}
                    onClick={() => pick(oi)}
                    sx={{
                      px: 2, py: 1.5, borderRadius: 2.5, cursor: "pointer",
                      border: "1.5px solid",
                      borderColor: selected ? "primary.main" : "#ece2e4",
                      bgcolor: selected ? "#faf3f4" : "#fff",
                      transition: "all .15s",
                      "&:hover": { borderColor: "primary.main", bgcolor: "#fdf7f8" },
                      display: "flex", alignItems: "center", gap: 1.5,
                    }}>
                    {selected
                      ? <CheckCircleRoundedIcon color="primary" />
                      : <CircleRoundedIcon sx={{ fontSize: 20, color: "#d3bfc4" }} />}
                    <Typography variant="body1" fontWeight={selected ? 700 : 500}>{label}</Typography>
                  </Box>
                );
              })}
            </Stack>
          </Paper>
        )}

        {/* فاز ۷۵ — راهنمای سؤال بی‌پاسخ */}
        {jumpHint && current === firstUnanswered && (
          <Alert severity="warning" onClose={() => setJumpHint(null)}>{jumpHint}</Alert>
        )}
        {current === questions.length - 1 && firstUnanswered >= 0 && !jumpHint && (
          <Alert severity="info">
            {(questions.length - answeredCount).toLocaleString("fa-IR")} سؤال بی‌پاسخ مانده است؛ برای ثبت نهایی،
            همهٔ سؤال‌ها باید پاسخ داده شوند. دکمهٔ پایین شما را به اولین سؤال بی‌پاسخ می‌برد.
          </Alert>
        )}

        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1} useFlexGap>
          <Button startIcon={<ArrowForwardRoundedIcon />} disabled={current === 0}
            onClick={() => setCurrent((c) => c - 1)}>
            سؤال قبلی
          </Button>
          <Box>
            {current < questions.length - 1 ? (
              <Button variant="contained" endIcon={<ArrowBackRoundedIcon />}
                onClick={() => setCurrent((c) => c + 1)}>
                سؤال بعدی
              </Button>
            ) : (
              <Button
                variant="contained"
                color={firstUnanswered >= 0 ? "primary" : "success"}
                disabled={submitMut.isPending}
                onClick={tryFinish}
              >
                {firstUnanswered >= 0
                  ? `تکمیل پاسخ‌ها (${answeredCount.toLocaleString("fa-IR")}/${questions.length.toLocaleString("fa-IR")})`
                  : submitMut.isPending ? "در حال ثبت…" : "ثبت و مشاهده نتیجه"}
              </Button>
            )}
          </Box>
        </Stack>

        {submitMut.error && <Alert severity="error">{errDetail(submitMut.error)}</Alert>}
      </Stack>
    </Stack>
  );
}
