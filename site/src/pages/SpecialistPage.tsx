// فاز ۶۹ - صفحهٔ پروفایل متخصص (الگوی اسنپ‌داکتر)
//
// همه‌چیز دربارهٔ یک مشاور در یک صفحه: هدر با عکس/عنوان/امتیاز ستاره‌دار،
// پنل رزرو نوبت (تقویم روزها + بازه‌های ساعتی + انتخاب خدمت + پرداخت آنلاین
// درگاه زرین‌پال) و بخش نظرات کاربران (میانگین + تفکیک + ثبت نظر با توکن
// رزرو پرداخت‌شده). جریان رزرو: انتخاب روز/ساعت → نگهداشت اسلات → فرم
// اطلاعات + کد یک‌بارمصرف → پرداخت آنلاین → بازگشت از درگاه به /booking/result.
import {
  Alert, Avatar, Box, Button, Chip, CircularProgress, Container, Divider, FormControl,
  InputLabel, LinearProgress, MenuItem, Paper, Select, Stack, TextField, Typography,
} from "@mui/material";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  createBookingHold, fetchBookingSlots, fetchCounselorReviews, fetchPublicCounselor,
  fetchPublicServices, postConsultation, postCounselorReview, releaseBookingHold,
  requestOtp, verifyOtp,
} from "../api";
import type {
  BookingHold, CounselorReviewsResponse, PublicCounselor, PublicService, SlotDay,
} from "../api";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { texts } from "../content/texts";

function faDayLabel(iso: string): string {
  try {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString("fa-IR", { weekday: "long", day: "numeric", month: "long" });
  } catch {
    return iso;
  }
}

function faParts(iso: string): { weekday: string; day: string; month: string } {
  try {
    const d = new Date(iso + "T00:00:00");
    return {
      weekday: d.toLocaleDateString("fa-IR", { weekday: "long" }),
      day: d.toLocaleDateString("fa-IR", { day: "numeric" }),
      month: d.toLocaleDateString("fa-IR", { month: "long" }),
    };
  } catch {
    return { weekday: iso, day: "", month: "" };
  }
}

function faNum(n: number | string): string {
  return Number(n).toLocaleString("fa-IR");
}

function fmtPrice(amount: number | null, currency: string | null): string {
  if (amount == null) return "توافق در پذیرش";
  return `${faNum(amount)} ${currency === "IRR" ? "ریال" : currency || ""}`;
}

function fmtCountdown(total: number): string {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m.toLocaleString("fa-IR")}:${s.toString().padStart(2, "0").replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)])}`;
}

function Stars({ value, size = 18 }: { value: number | null; size?: number }) {
  const v = value ?? 0;
  return (
    <Stack direction="row" spacing={0.25} alignItems="center" aria-label={`امتیاز ${faNum(v)} از ۵`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Box
          key={i}
          component="svg"
          viewBox="0 0 24 24"
          sx={{ width: size, height: size, display: "block" }}
          aria-hidden
        >
          <path
            d="M12 2.6l2.9 5.9 6.5.95-4.7 4.6 1.1 6.5L12 17.5l-5.8 3.05 1.1-6.5-4.7-4.6 6.5-.95z"
            fill={i <= Math.round(v) ? "#f0b429" : "#eadfe3"}
          />
        </Box>
      ))}
    </Stack>
  );
}

export default function SpecialistPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [profile, setProfile] = useState<(PublicCounselor & { degree: string | null }) | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [days, setDays] = useState<SlotDay[] | null>(null);
  const [day, setDay] = useState<SlotDay | null>(null);
  const [slot, setSlot] = useState<{ start_at: string; label: string } | null>(null);
  const [services, setServices] = useState<PublicService[]>([]);
  const [serviceId, setServiceId] = useState<string>("");
  const [reviews, setReviews] = useState<CounselorReviewsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [infoStep, setInfoStep] = useState(false);

  // فرم اطلاعات
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [topic, setTopic] = useState("");
  const [message, setMessage] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [busy, setBusy] = useState(false);
  const [redirecting, setRedirecting] = useState(false);

  // نگهداشت اسلات
  const [hold, setHold] = useState<BookingHold | null>(null);
  const [remaining, setRemaining] = useState(0);
  const holdRef = useRef<BookingHold | null>(null);
  const countdownReadyRef = useRef(false);

  // کد یک‌بارمصرف
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [otpToken, setOtpToken] = useState<string | null>(null);
  const [otpDevCode, setOtpDevCode] = useState<string | null>(null);
  const [otpBusy, setOtpBusy] = useState(false);

  // فرم ثبت نظر
  const [rvToken, setRvToken] = useState("");
  const [rvRating, setRvRating] = useState(0);
  const [rvComment, setRvComment] = useState("");
  const [rvMsg, setRvMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [rvBusy, setRvBusy] = useState(false);

  const loadSlots = async (counselorId: string) => {
    setDays(null); setDay(null); setSlot(null);
    try {
      setDays(await fetchBookingSlots(counselorId));
    } catch {
      setDays([]);
    }
  };

  const loadReviews = (counselorId: string) => {
    fetchCounselorReviews(counselorId).then(setReviews).catch(() => setReviews(null));
  };

  useEffect(() => {
    if (!id) { setNotFound(true); return; }
    fetchPublicCounselor(id)
      .then((p) => { setProfile(p); loadSlots(p.id); loadReviews(p.id); })
      .catch(() => setNotFound(true));
    fetchPublicServices().then(setServices).catch(() => setServices([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // شمارش معکوس نگهداشت
  useEffect(() => {
    if (!hold) { countdownReadyRef.current = false; return; }
    countdownReadyRef.current = true;
    setRemaining(hold.remaining_seconds);
    const deadline = Date.now() + hold.remaining_seconds * 1000;
    const iv = setInterval(() => {
      const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      setRemaining(left);
      if (left <= 0) clearInterval(iv);
    }, 1000);
    return () => clearInterval(iv);
  }, [hold]);

  // انقضای نگهداشت در فرم اطلاعات
  useEffect(() => {
    if (infoStep && hold && countdownReadyRef.current && remaining <= 0) {
      setError("زمان نگهداشت نوبت به پایان رسید؛ لطفاً اسلات را دوباره انتخاب کنید");
      holdRef.current = null;
      countdownReadyRef.current = false;
      setHold(null);
      setOtpSent(false); setOtpCode(""); setOtpToken(null); setOtpDevCode(null);
      setInfoStep(false);
      if (profile) loadSlots(profile.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, infoStep, hold]);

  const dropHold = () => {
    const h = holdRef.current;
    if (h) releaseBookingHold(h.hold_token).catch(() => undefined);
    holdRef.current = null;
    countdownReadyRef.current = false;
    setHold(null);
    setRemaining(0);
  };

  const slotGroups = useMemo(() => {
    if (!day) return [];
    const morning = day.slots.filter((s) => (parseInt(s.label.slice(0, 2), 10) || 0) < 12);
    const evening = day.slots.filter((s) => (parseInt(s.label.slice(0, 2), 10) || 0) >= 12);
    const groups: { title: string; items: typeof morning }[] = [];
    if (morning.length) groups.push({ title: "☀ صبح", items: morning });
    if (evening.length) groups.push({ title: "◐ بعدازظهر و عصر", items: evening });
    return groups.length ? groups : [{ title: "بازه‌های آزاد", items: day.slots }];
  }, [day]);

  const selectedService = services.find((s) => s.id === serviceId) ?? null;

  const proceedToInfo = async () => {
    if (!profile || !slot) return;
    setError(null);
    if (holdRef.current) { setInfoStep(true); return; }
    try {
      const h = await createBookingHold(profile.id, slot.start_at);
      holdRef.current = h;
      setHold(h);
      setRemaining(h.remaining_seconds);
      setInfoStep(true);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      const raw = (err as Error).message || "";
      setError(
        raw.includes("در دسترس نیست") || raw.includes("نگه")
          ? "این زمان در دسترس نیست؛ بازه‌های تازه بارگذاری شد — لطفاً زمان دیگری انتخاب کنید"
          : raw,
      );
      await loadSlots(profile.id);
    }
  };

  const sendOtp = async () => {
    if (!/09\d{9}/.test(mobile.trim())) {
      setError("شماره موبایل را به قالب 09121234567 وارد کنید");
      return;
    }
    setError(null); setOtpBusy(true);
    try {
      const res = await requestOtp(mobile.trim());
      setOtpSent(true);
      setOtpDevCode(res.dev_code ?? null);
      setOtpToken(null);
    } catch (err) {
      setError((err as Error).message || "خطا در ارسال کد تأیید");
    } finally {
      setOtpBusy(false);
    }
  };

  const checkOtp = async () => {
    if (!otpCode.trim()) return;
    setError(null); setOtpBusy(true);
    try {
      const res = await verifyOtp(mobile.trim(), otpCode.trim());
      setOtpToken(res.verify_token);
    } catch (err) {
      setError((err as Error).message || "کد تأیید نامعتبر است");
    } finally {
      setOtpBusy(false);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!profile || !slot || !holdRef.current) return;
    if (!serviceId) { setError("برای رزرو آنلاین، انتخاب خدمت الزامی است"); return; }
    if (!otpToken) {
      setError("لطفاً موبایل خود را با کد یک‌بارمصرف تأیید کنید");
      return;
    }
    setError(null); setBusy(true);
    try {
      const res = await postConsultation({
        full_name: fullName.trim(),
        mobile: mobile.trim(),
        topic,
        counselor_id: profile.id,
        start_at: slot.start_at,
        hold_token: holdRef.current.hold_token,
        otp_token: otpToken,
        service_id: serviceId,
        pay_online: true,
        message: message.trim() || undefined,
        website: honeypot,
      });
      holdRef.current = null;
      countdownReadyRef.current = false;
      if (res.payment && res.payment.redirect_url) {
        setRedirecting(true);
        // انتقال به درگاه پرداخت (زرین‌پال یا شبیه‌ساز در توسعه)
        window.location.href = res.payment.redirect_url;
        return;
      }
      if (res.payment_error) {
        setError(`نوبت شما ثبت شد (کد ${res.request_id.slice(0, 8).toUpperCase()}) اما اتصال به درگاه ناموفق بود: ${res.payment_error}`);
      }
    } catch (err) {
      const msg = (err as Error).message || "خطا در ثبت رزرو";
      setError(msg);
      if (msg.includes("منقضی") || msg.includes("در دسترس نیست") || msg.includes("رزرو شد")) {
        dropHold();
        await loadSlots(profile.id);
        setInfoStep(false);
      }
    } finally {
      setBusy(false);
    }
  };

  const submitReview = async (e: FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    if (!rvToken.trim()) { setRvMsg({ kind: "err", text: "توکن ثبت نظر (از صفحهٔ نتیجهٔ پرداخت) را وارد کنید" }); return; }
    if (rvRating < 1) { setRvMsg({ kind: "err", text: "امتیاز ستاره‌ها را انتخاب کنید" }); return; }
    setRvBusy(true); setRvMsg(null);
    try {
      await postCounselorReview(profile.id, {
        review_token: rvToken.trim(),
        rating: rvRating,
        comment: rvComment.trim() || undefined,
      });
      setRvMsg({ kind: "ok", text: "نظر شما ثبت شد؛ سپاس از همراهی‌تان" });
      setRvToken(""); setRvRating(0); setRvComment("");
      loadReviews(profile.id);
    } catch (err) {
      setRvMsg({ kind: "err", text: (err as Error).message || "خطا در ثبت نظر" });
    } finally {
      setRvBusy(false);
    }
  };

  const backToBooking = () => {
    dropHold();
    setInfoStep(false);
    setError(null);
    if (profile) loadSlots(profile.id);
  };

  if (notFound) {
    return (
      <Box>
        <Header />
        <Container sx={{ py: 10, textAlign: "center", minHeight: "50vh" }}>
          <Typography variant="h6" fontWeight={800} mb={2}>مشاور یافت نشد یا فعال نیست</Typography>
          <Button variant="contained" onClick={() => navigate("/booking")}>بازگشت به فهرست مشاوران</Button>
        </Container>
        <Footer />
      </Box>
    );
  }

  if (!profile) {
    return (
      <Box>
        <Header />
        <Stack alignItems="center" py={12}><CircularProgress sx={{ color: "primary.main" }} /></Stack>
        <Footer />
      </Box>
    );
  }

  return (
    <Box>
      <Header />
      <Box sx={{ background: "linear-gradient(180deg,#fdf3f5 0%,#ffffff 100%)", pb: 6 }}>
        <Container sx={{ py: { xs: 3, md: 5 } }}>

          {/* ---------------- هدر پروفایل ---------------- */}
          <Paper elevation={0} sx={{
            p: { xs: 2.5, md: 4 }, borderRadius: 4, border: "1px solid #f3dce2",
            boxShadow: "0 18px 44px rgba(124,39,64,.10)", mb: 3,
          }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={{ xs: 2, md: 3 }} alignItems={{ md: "center" }}>
              {profile.photo_url ? (
                <Box
                  component="img"
                  src={profile.photo_url}
                  alt={profile.name}
                  sx={{
                    width: { xs: 96, md: 128 }, height: { xs: 96, md: 128 }, borderRadius: "50%",
                    objectFit: "cover", border: "5px solid #fff",
                    boxShadow: "0 10px 26px rgba(168,58,84,.20)", flexShrink: 0,
                  }}
                />
              ) : (
                <Avatar sx={{
                  width: { xs: 96, md: 128 }, height: { xs: 96, md: 128 }, fontSize: 52,
                  background: "linear-gradient(135deg,#b34460,#8a2f47)", border: "5px solid #fff",
                  boxShadow: "0 10px 26px rgba(168,58,84,.20)", flexShrink: 0,
                }}>
                  {profile.name.charAt(0)}
                </Avatar>
              )}
              <Box sx={{ flex: 1, textAlign: { xs: "center", md: "right" } }}>
                <Typography variant="h5" fontWeight={800} color="primary.main">{profile.name}</Typography>
                {profile.professional_title && (
                  <Typography variant="body1" color="text.secondary" mt={0.5}>{profile.professional_title}</Typography>
                )}
                <Stack direction="row" spacing={1} justifyContent={{ xs: "center", md: "flex-start" }} flexWrap="wrap" useFlexGap sx={{ mt: 1.2 }}>
                  {profile.specialty && (
                    <Chip size="small" label={profile.specialty} sx={{ bgcolor: "#faeef1", color: "primary.main", fontWeight: 700 }} />
                  )}
                  {profile.degree && (
                    <Chip size="small" label={profile.degree} variant="outlined" sx={{ fontWeight: 600 }} />
                  )}
                  {profile.province_name && (
                    <Chip size="small" label={`کلینیک رز — ${profile.province_name}`} variant="outlined" sx={{ fontWeight: 600 }} />
                  )}
                </Stack>
                <Stack direction="row" spacing={1} alignItems="center" justifyContent={{ xs: "center", md: "flex-start" }} sx={{ mt: 1.4 }}>
                  <Stars value={profile.rating_avg} />
                  <Typography variant="body2" fontWeight={700}>
                    {profile.rating_avg ? faNum(profile.rating_avg) : "بدون امتیاز"}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    ({faNum(profile.review_count)} نظر)
                  </Typography>
                </Stack>
              </Box>
              <Box sx={{ textAlign: "center", flexShrink: 0 }}>
                <Button variant="contained" size="large" sx={{ borderRadius: 99, px: 4, fontWeight: 800 }}
                  onClick={() => document.getElementById("booking-panel")?.scrollIntoView({ behavior: "smooth" })}>
                  رزرو نوبت
                </Button>
              </Box>
            </Stack>
          </Paper>

          {error && <Alert severity="warning" sx={{ mb: 2, borderRadius: 2 }} onClose={() => setError(null)} role="alert">{error}</Alert>}

          {/* ---------------- پنل رزرو نوبت ---------------- */}
          <Paper id="booking-panel" elevation={0} sx={{
            p: { xs: 2.5, md: 4 }, borderRadius: 4, border: "1px solid #f3dce2", mb: 3,
          }}>
            <Typography variant="h6" fontWeight={800} mb={2}>
              📅 {infoStep ? "اطلاعات شما" : "انتخاب زمان و خدمت"}
            </Typography>

            {redirecting && (
              <Stack spacing={2} py={4} alignItems="center">
                <CircularProgress sx={{ color: "primary.main" }} />
                <Typography fontWeight={700}>در حال انتقال به درگاه پرداخت…</Typography>
                <Typography variant="body2" color="text.secondary">پس از تکمیل پرداخت، به صفحهٔ نتیجهٔ رزرو بازمی‌گردید.</Typography>
              </Stack>
            )}

            {!redirecting && !infoStep && (
              <>
                {/* نوار روزها */}
                <Typography variant="body2" fontWeight={700} color="text.secondary" mb={1}>۱. روز را انتخاب کنید</Typography>
                {days === null ? (
                  <Stack alignItems="center" py={3}><CircularProgress size={28} sx={{ color: "primary.main" }} /></Stack>
                ) : days.length === 0 ? (
                  <Typography color="text.secondary" py={2}>در حال حاضر نوبت آزادی برای این مشاور نیست.</Typography>
                ) : (
                  <Stack direction="row" spacing={1} sx={{ overflowX: "auto", pb: 1, mb: 2 }}>
                    {days.map((d) => {
                      const p = faParts(d.date);
                      const active = day?.date === d.date;
                      return (
                        <Paper key={d.date} elevation={0} onClick={() => { setDay(d); setSlot(null); }}
                          sx={{
                            cursor: "pointer", px: 2, py: 1.2, minWidth: 86, textAlign: "center",
                            borderRadius: 3, flexShrink: 0,
                            border: active ? "2px solid primary.main" : "1.5px solid #f0dfe5",
                            borderColor: active ? "primary.main" : "#f0dfe5",
                            bgcolor: active ? "#faeef1" : "#fff",
                            transition: "all .2s", "&:hover": { borderColor: "primary.main" },
                          }}>
                          <Typography sx={{ fontSize: 12, fontWeight: 700, color: active ? "primary.main" : "text.secondary" }}>{p.weekday}</Typography>
                          <Typography sx={{ fontSize: 18, fontWeight: 800, color: active ? "primary.main" : "text.primary" }}>{p.day}</Typography>
                          <Typography sx={{ fontSize: 11, color: "text.secondary" }}>{p.month}</Typography>
                          <Chip size="small" label={`${faNum(d.slots.length)} نوبت`} sx={{ mt: 0.5, height: 20, fontSize: 10.5, bgcolor: active ? "primary.main" : "#f6eef1", color: active ? "#fff" : "text.secondary" }} />
                        </Paper>
                      );
                    })}
                  </Stack>
                )}

                {/* بازه‌های ساعتی */}
                {day && (
                  <>
                    <Typography variant="body2" fontWeight={700} color="text.secondary" mb={1}>
                      ۲. ساعت را انتخاب کنید — {faDayLabel(day.date)}
                    </Typography>
                    <Stack spacing={1.5} mb={2.5}>
                      {slotGroups.map((g) => (
                        <Box key={g.title}>
                          <Typography sx={{ fontSize: 12.5, fontWeight: 700, color: "text.secondary", mb: 0.8 }}>{g.title}</Typography>
                          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                            {g.items.map((s) => {
                              const active = slot?.start_at === s.start_at;
                              return (
                                <Box
                                  key={s.start_at}
                                  onClick={() => setSlot(s)}
                                  sx={{
                                    cursor: "pointer", px: 2, py: 0.9, borderRadius: 99, fontSize: 14,
                                    fontWeight: 700, transition: "all .15s",
                                    border: active ? "2px solid" : "1.5px solid #f0dfe5",
                                    borderColor: active ? "primary.main" : "#f0dfe5",
                                    bgcolor: active ? "primary.main" : "#fff",
                                    color: active ? "#fff" : "text.primary",
                                    boxShadow: active ? "0 4px 14px rgba(124,39,64,.30)" : "none",
                                    "&:hover": { borderColor: "primary.main" },
                                  }}
                                >
                                  {s.label}
                                </Box>
                              );
                            })}
                          </Stack>
                        </Box>
                      ))}
                    </Stack>
                  </>
                )}

                {/* انتخاب خدمت */}
                <Typography variant="body2" fontWeight={700} color="text.secondary" mb={1}>۳. خدمت موردنظر</Typography>
                {services.length === 0 ? (
                  <Typography color="text.secondary" mb={2}>فهرست خدمات بارگذاری نشده است.</Typography>
                ) : (
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }} mb={2}>
                    <FormControl size="small" sx={{ minWidth: 280 }}>
                      <InputLabel>انتخاب خدمت</InputLabel>
                      <Select value={serviceId} label="انتخاب خدمت" onChange={(e) => setServiceId(e.target.value)}>
                        {services.map((s) => (
                          <MenuItem key={s.id} value={s.id}>{s.title}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    {selectedService && (
                      <Typography variant="body2" fontWeight={800} color="primary.main">
                        مبلغ: {fmtPrice(selectedService.price_amount, selectedService.price_currency)}
                        {selectedService.duration_minutes ? ` — ${faNum(selectedService.duration_minutes)} دقیقه` : ""}
                      </Typography>
                    )}
                  </Stack>
                )}

                <Divider sx={{ my: 2 }} />
                <Button
                  variant="contained" size="large" fullWidth sx={{ borderRadius: 99, fontWeight: 800, py: 1.4 }}
                  disabled={!slot || !serviceId || days === null || days.length === 0}
                  onClick={proceedToInfo}
                >
                  ادامه و پرداخت آنلاین
                </Button>
                {!slot && (
                  <Typography variant="caption" color="text.secondary" display="block" textAlign="center" mt={1}>
                    ابتدا روز و ساعت و سپس خدمت را انتخاب کنید
                  </Typography>
                )}
              </>
            )}

            {/* فرم اطلاعات + پرداخت */}
            {!redirecting && infoStep && profile && slot && (
              <Box component="form" onSubmit={submit}>
                <Paper variant="outlined" sx={{ p: 2, borderRadius: 3, bgcolor: "#fdf7f8", borderColor: "#f0d9df", mb: 2.5 }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap>
                    <Box>
                      <Typography fontWeight={800}>{profile.name} — {faDayLabel(day?.date ?? slot.start_at.slice(0, 10))} ساعت {slot.label}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {selectedService ? `${selectedService.title} — ${fmtPrice(selectedService.price_amount, selectedService.price_currency)}` : "خدمت انتخاب نشده"}
                      </Typography>
                    </Box>
                    <Stack direction="row" spacing={1} alignItems="center">
                      {hold && (
                        <Chip size="small" color="warning" variant="outlined"
                          label={`نگهداشت: ${fmtCountdown(remaining)}`} />
                      )}
                      <Button size="small" onClick={backToBooking}>تغییر زمان</Button>
                    </Stack>
                  </Stack>
                  {hold && <LinearProgress variant="determinate" value={(remaining / (hold.hold_minutes * 60)) * 100} sx={{ mt: 1.5, borderRadius: 99, height: 6 }} />}
                </Paper>

                <Stack spacing={2}>
                  <TextField required label="نام و نام خانوادگی" value={fullName}
                    onChange={(e) => setFullName(e.target.value)} inputProps={{ maxLength: 200 }} />
                  <TextField required label="شماره موبایل" value={mobile} dir="ltr"
                    onChange={(e) => setMobile(e.target.value)} placeholder="09121234567"
                    inputProps={{ maxLength: 11, inputMode: "numeric", pattern: "09[0-9]{9}" }} />

                  {/* کد یک‌بارمصرف */}
                  <Paper variant="outlined" sx={{ p: 2, borderRadius: 3 }}>
                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
                      <Button type="button" variant="outlined" onClick={sendOtp} disabled={otpBusy}
                        sx={{ whiteSpace: "nowrap" }}>
                        {otpSent ? "ارسال مجدد کد" : "ارسال کد تأیید"}
                      </Button>
                      <TextField size="small" label="کد یک‌بارمصرف" value={otpCode} dir="ltr"
                        onChange={(e) => setOtpCode(e.target.value)} inputProps={{ maxLength: 6, inputMode: "numeric" }}
                        sx={{ maxWidth: 180 }} />
                      {otpToken ? (
                        <Chip size="small" color="success" label="موبایل تأیید شد ✓" />
                      ) : (
                        <Button type="button" size="small" onClick={checkOtp} disabled={otpBusy || !otpSent}>بررسی کد</Button>
                      )}
                    </Stack>
                    {otpDevCode && (
                      <Alert severity="info" sx={{ mt: 1.5, borderRadius: 2 }}>
                        کد توسعه: {otpDevCode}
                      </Alert>
                    )}
                  </Paper>

                  <FormControl size="small">
                    <InputLabel>موضوع مشاوره</InputLabel>
                    <Select required value={topic} label="موضوع مشاوره" onChange={(e) => setTopic(e.target.value)}>
                      {texts.topics.map((t) => (
                        <MenuItem key={t} value={t}>{t}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <TextField label="توضیح (اختیاری)" value={message} multiline minRows={2}
                    onChange={(e) => setMessage(e.target.value)} inputProps={{ maxLength: 2000 }} />
                  {/* هانی‌پات ضدربات */}
                  <TextField label="وب‌سایت" value={honeypot} onChange={(e) => setHoneypot(e.target.value)}
                    sx={{ display: "none" }} />

                  <Button type="submit" variant="contained" size="large" disabled={busy || !otpToken}
                    sx={{ borderRadius: 99, fontWeight: 800, py: 1.4 }}>
                    {busy ? "در حال ثبت…" : `پرداخت آنلاین و ثبت نهایی${selectedService?.price_amount ? ` (${fmtPrice(selectedService.price_amount, selectedService.price_currency)})` : ""}`}
                  </Button>
                  <Typography variant="caption" color="text.secondary" textAlign="center">
                    پرداخت از طریق درگاه امن زرین‌پال انجام می‌شود؛ پس از پرداخت موفق، نوبت شما قطعی می‌شود.
                  </Typography>
                </Stack>
              </Box>
            )}
          </Paper>

          {/* ---------------- نظرات کاربران ---------------- */}
          <Paper elevation={0} sx={{ p: { xs: 2.5, md: 4 }, borderRadius: 4, border: "1px solid #f3dce2" }} id="reviews">
            <Typography variant="h6" fontWeight={800} mb={2}>⭐ نظرات کاربران</Typography>

            {reviews && (
              <Stack direction={{ xs: "column", sm: "row" }} spacing={3} mb={3}>
                <Box sx={{ textAlign: "center", minWidth: 150 }}>
                  <Typography variant="h3" fontWeight={800} color="primary.main">
                    {reviews.summary.rating_avg ? faNum(reviews.summary.rating_avg) : "—"}
                  </Typography>
                  <Stars value={reviews.summary.rating_avg} size={22} />
                  <Typography variant="body2" color="text.secondary" mt={0.5}>
                    از مجموع {faNum(reviews.summary.review_count)} نظر
                  </Typography>
                </Box>
                <Box sx={{ flex: 1 }}>
                  {[5, 4, 3, 2, 1].map((k) => {
                    const cnt = reviews.summary.breakdown[String(k)] ?? 0;
                    const pct = reviews.summary.review_count ? (cnt / reviews.summary.review_count) * 100 : 0;
                    return (
                      <Stack key={k} direction="row" spacing={1} alignItems="center" mb={0.6}>
                        <Typography sx={{ fontSize: 12, width: 24, color: "text.secondary" }}>{faNum(k)}★</Typography>
                        <Box sx={{ flex: 1, bgcolor: "#f6eef1", borderRadius: 99, height: 8 }}>
                          <Box sx={{ width: `${pct}%`, bgcolor: "#f0b429", borderRadius: 99, height: 8, transition: "width .4s" }} />
                        </Box>
                        <Typography sx={{ fontSize: 12, width: 28, color: "text.secondary" }}>{faNum(cnt)}</Typography>
                      </Stack>
                    );
                  })}
                </Box>
              </Stack>
            )}

            <Divider sx={{ mb: 2 }} />

            {reviews === null ? (
              <Typography color="text.secondary">نظرات بارگذاری نشده است.</Typography>
            ) : reviews.items.length === 0 ? (
              <Typography color="text.secondary" mb={3}>
                هنوز نظری برای این مشاور ثبت نشده است؛ اولین نفر باشید.
              </Typography>
            ) : (
              <Stack spacing={2} mb={3}>
                {reviews.items.map((r) => (
                  <Paper key={r.id} variant="outlined" sx={{ p: 2, borderRadius: 3, borderColor: "#f3e2e7" }}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Avatar sx={{ width: 34, height: 34, fontSize: 15, bgcolor: "#f3e2e8", color: "primary.main", fontWeight: 800 }}>
                          {r.author.charAt(0)}
                        </Avatar>
                        <Typography fontWeight={700}>{r.author}</Typography>
                      </Stack>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Stars value={r.rating} size={15} />
                        {r.created_at && (
                          <Typography variant="caption" color="text.secondary">
                            {new Date(r.created_at).toLocaleDateString("fa-IR")}
                          </Typography>
                        )}
                      </Stack>
                    </Stack>
                    {r.comment && (
                      <Typography variant="body2" color="text.primary" mt={1} whiteSpace="pre-wrap">
                        {r.comment}
                      </Typography>
                    )}
                  </Paper>
                ))}
              </Stack>
            )}

            {/* فرم ثبت نظر (توکن از صفحهٔ نتیجهٔ پرداخت) */}
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3, bgcolor: "#fdf7f8", borderColor: "#f0d9df" }}>
              <Typography fontWeight={800} mb={1.5}>ثبت نظر و امتیاز شما</Typography>
              <Typography variant="body2" color="text.secondary" mb={2}>
                فقط کاربرانی که رزرو پرداخت‌شده دارند می‌توانند نظر ثبت کنند. توکن دعوت پس از پرداخت موفق، در صفحهٔ نتیجه نمایش داده می‌شود.
              </Typography>
              <Box component="form" onSubmit={submitReview}>
                <Stack spacing={2}>
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <Typography variant="body2" fontWeight={700} mr={1}>امتیاز شما:</Typography>
                    {[1, 2, 3, 4, 5].map((i) => (
                      <Box
                        key={i}
                        component="svg" viewBox="0 0 24 24"
                        onClick={() => setRvRating(i)}
                        sx={{ width: 30, height: 30, cursor: "pointer", "&:hover": { transform: "scale(1.15)" }, transition: "transform .15s" }}
                        aria-label={`${i} ستاره`}
                      >
                        <path
                          d="M12 2.6l2.9 5.9 6.5.95-4.7 4.6 1.1 6.5L12 17.5l-5.8 3.05 1.1-6.5-4.7-4.6 6.5-.95z"
                          fill={i <= rvRating ? "#f0b429" : "#eadfe3"}
                        />
                      </Box>
                    ))}
                  </Stack>
                  <TextField size="small" label="توکن ثبت نظر" value={rvToken} dir="ltr"
                    onChange={(e) => setRvToken(e.target.value)} inputProps={{ maxLength: 64 }} />
                  <TextField label="متن نظر (اختیاری)" value={rvComment} multiline minRows={2}
                    onChange={(e) => setRvComment(e.target.value)} inputProps={{ maxLength: 1000 }} />
                  {rvMsg && (
                    <Alert severity={rvMsg.kind === "ok" ? "success" : "warning"} sx={{ borderRadius: 2 }}>
                      {rvMsg.text}
                    </Alert>
                  )}
                  <Button type="submit" variant="outlined" disabled={rvBusy} sx={{ alignSelf: "flex-start", borderRadius: 99, fontWeight: 700 }}>
                    ثبت نظر
                  </Button>
                </Stack>
              </Box>
            </Paper>
          </Paper>
        </Container>
      </Box>
      <Footer />
    </Box>
  );
}
