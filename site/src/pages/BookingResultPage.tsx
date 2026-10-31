// فاز ۶۹ - صفحهٔ نتیجهٔ رزرو آنلاین (بازگشت از درگاه پرداخت)
//
// درگاه (زرین‌پال/شبیه‌ساز) پس از پرداخت، مرورگر کاربر را به همین صفحه
// برمی‌گرداند: /booking/result?state=success|failed&req=<id>&token=<review_token>
// در حالت موفق، کد پیگیری + توکن ثبت نظر نمایش داده می‌شود و کاربر می‌تواند
// همین‌جا امتیاز و نظرش را ثبت کند.
import {
  Alert, Box, Button, Chip, CircularProgress, Container, Paper, Stack, TextField, Typography,
} from "@mui/material";
import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { postCounselorReview } from "../api";
import Header from "../components/Header";
import Footer from "../components/Footer";

function faNum(n: number | string): string {
  return Number(n).toLocaleString("fa-IR");
}

export default function BookingResultPage() {
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const state = sp.get("state");
  const req = sp.get("req");
  const token = sp.get("token") ?? "";
  const success = state === "success";

  // فرم ثبت نظر (توکن از URL)
  const [counselorId, setCounselorId] = useState<string>("");
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [lookingUp, setLookingUp] = useState(success && !!token);

  // شناسهٔ مشاور رزرو برای ثبت نظر: از وضعیت رزرو (endpoint عمومی وضعیت) -
  // برای سادگی، توکن در فرم صفحهٔ متخصص هم پذیرفته است؛ اینجا فقط ثبت با توکن.
  useEffect(() => {
    if (!success || !token) { setLookingUp(false); return; }
    let alive = true;
    // یافتن مشاورِ رزرو از طریق endpoint وضعیت رزرو (بدون احراز هویت)
    (async () => {
      try {
        const r = await fetch(`/api/v1/public/booking-result-info?req=${encodeURIComponent(req ?? "")}&token=${encodeURIComponent(token)}`);
        if (r.ok) {
          const d = await r.json();
          if (alive && d.counselor_id) setCounselorId(String(d.counselor_id));
        }
      } catch {
        /* فرم صفحهٔ متخصص هم هست؛ اینجا اختیاری است */
      } finally {
        if (alive) setLookingUp(false);
      }
    })();
    return () => { alive = false; };
  }, [success, token, req]);

  const submitReview = async (e: FormEvent) => {
    e.preventDefault();
    if (!counselorId) { setMsg({ kind: "err", text: "شناسهٔ مشاور یافت نشد؛ از صفحهٔ مشاور نظر خود را ثبت کنید" }); return; }
    if (rating < 1) { setMsg({ kind: "err", text: "امتیاز ستاره‌ها را انتخاب کنید" }); return; }
    setBusy(true); setMsg(null);
    try {
      await postCounselorReview(counselorId, {
        review_token: token,
        rating,
        comment: comment.trim() || undefined,
      });
      setDone(true);
      setMsg({ kind: "ok", text: "نظر شما ثبت شد؛ سپاس از همراهی‌تان" });
    } catch (err) {
      setMsg({ kind: "err", text: (err as Error).message || "خطا در ثبت نظر" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container sx={{ py: { xs: 4, md: 7 }, minHeight: "55vh" }}>
          {lookingUp ? (
            <Stack alignItems="center" py={8}><CircularProgress sx={{ color: "primary.main" }} /></Stack>
          ) : (
            <Paper sx={{
              p: { xs: 3, md: 5 }, maxWidth: 640, mx: "auto", textAlign: "center",
              borderRadius: 4, border: "1px solid #f3dce2", boxShadow: "0 18px 44px rgba(124,39,64,.10)",
            }}>
              <Box sx={{
                width: 84, height: 84, borderRadius: "50%", mx: "auto", mb: 2,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 42, animation: "rosepsyPop .45s ease",
                "@keyframes rosepsyPop": { from: { transform: "scale(.4)", opacity: 0 }, to: { transform: "scale(1)", opacity: 1 } },
                ...(success
                  ? { background: "linear-gradient(135deg,#e8f5ec,#d3ecd9)", color: "#2e7d46" }
                  : { background: "linear-gradient(135deg,#fdeaea,#f9d5d5)", color: "#b3404a" }),
              }}>{success ? "✓" : "✕"}</Box>

              <Typography variant="h6" fontWeight={800} mb={1}>
                {success ? "پرداخت با موفقیت انجام شد" : "پرداخت انجام نشد"}
              </Typography>
              <Typography variant="body1" color="text.secondary" mb={2}>
                {success
                  ? "نوبت شما قطعی شد؛ پذیرش در زمان مقرر منتظر شماست."
                  : "در صورت کسر وجه، مبلغ حداکثر تا ۷۲ ساعت به حساب شما بازمی‌گردد. می‌توانید دوباره تلاش کنید."}
              </Typography>

              {success && req && (
                <Chip color="primary" variant="outlined" sx={{ fontWeight: 700, letterSpacing: 1, mb: 2 }}
                  label={`کد پیگیری: ${req.slice(0, 8).toUpperCase()}`} />
              )}

              {success && token && (
                <Box component="form" onSubmit={submitReview} sx={{ mt: 3, textAlign: "right" }}>
                  <Typography fontWeight={800} mb={1.5} textAlign="center">⭐ به این مشاور امتیاز بدهید</Typography>
                  <Stack direction="row" spacing={0.5} justifyContent="center" mb={2}>
                    {[1, 2, 3, 4, 5].map((i) => (
                      <Box
                        key={i}
                        component="svg" viewBox="0 0 24 24"
                        onClick={() => setRating(i)}
                        sx={{ width: 34, height: 34, cursor: "pointer", "&:hover": { transform: "scale(1.15)" }, transition: "transform .15s" }}
                        aria-label={`${i} ستاره`}
                      >
                        <path
                          d="M12 2.6l2.9 5.9 6.5.95-4.7 4.6 1.1 6.5L12 17.5l-5.8 3.05 1.1-6.5-4.7-4.6 6.5-.95z"
                          fill={i <= rating ? "#f0b429" : "#eadfe3"}
                        />
                      </Box>
                    ))}
                  </Stack>
                  <TextField fullWidth label="متن نظر (اختیاری)" value={comment} multiline minRows={2}
                    onChange={(e) => setComment(e.target.value)} inputProps={{ maxLength: 1000 }}
                    sx={{ mb: 1.5 }} />
                  {msg && (
                    <Alert severity={msg.kind === "ok" ? "success" : "warning"} sx={{ borderRadius: 2, mb: 1.5 }}>
                      {msg.text}
                    </Alert>
                  )}
                  {!done && (
                    <Button type="submit" variant="contained" disabled={busy} sx={{ borderRadius: 99, fontWeight: 800 }}>
                      {busy ? "در حال ثبت…" : "ثبت نظر و امتیاز"}
                    </Button>
                  )}
                  <Typography variant="caption" color="text.secondary" display="block" mt={1} textAlign="center">
                    توکن دعوت شما: <Box component="code" dir="ltr" sx={{ fontSize: 11 }}>{token.slice(0, 12)}…</Box> (این توکن برای یک نوبت یک‌بار قابل استفاده است)
                  </Typography>
                </Box>
              )}

              <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} justifyContent="center" mt={3}>
                <Button variant="contained" onClick={() => navigate("/booking")}>رزرو نوبت جدید</Button>
                <Button variant="outlined" onClick={() => navigate("/")}>بازگشت به صفحهٔ اصلی</Button>
              </Stack>
              {success && req && (
                <Typography variant="caption" color="text.secondary" display="block" mt={2}>
                  شمارهٔ درخواست: <span dir="ltr">{faNum(req.slice(0, 4))}…</span> — این نوبت در سامانهٔ پذیرش نیز ثبت شده است.
                </Typography>
              )}
            </Paper>
          )}
        </Container>
      </Box>
      <Footer />
    </Box>
  );
}
