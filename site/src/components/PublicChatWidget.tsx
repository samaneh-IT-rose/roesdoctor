import {
  Box, Button, Chip, Fab, IconButton, InputBase, Paper, Stack,
  TextField, Tooltip, Typography,
} from "@mui/material";
import { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// فاز ۵۴ - ویجت چت آنلاین عمومی — روی همهٔ صفحات سایت فعال است.
// - هویت لایه‌لایه: توکن نشست در localStorage (تداوم گفتگو برای همان مرورگر)؛
//   اگر بازدیدکننده در سامانه لاگین باشد، بک‌اند نشست را به کاربر متصل می‌کند؛
//   در غیر این صورت IP سرور ثبت می‌شود؛ نام اختیاری هم قابل معرفی است؛
// - کارت‌های اقدام (دکمه‌های رزرو/ورود/مشاوران/خدمات) به صفحهٔ مرتبط منتقل
//   می‌کنند؛ دکمهٔ «رزرو از مشاور X» به /booking?counselor=<id> می‌رود و
//   صفحهٔ رزرو همان مشاور را پیش‌انتخاب می‌کند؛
// - نظر کاربر دربارهٔ خودِ گفتگو: ستارهٔ ۱ تا ۵ + توضیح اختیاری.
// ---------------------------------------------------------------------------

const TOKEN_KEY = "rosepsy_livechat_token";
const NAME_KEY = "rosepsy_livechat_name";

interface ChatAction { label: string; url: string; kind?: string }
interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "operator"; // فاز ۵۶: operator = پاسخ زندهٔ پذیرش
  content: string;
  sender_name?: string | null;
  actions?: ChatAction[] | null;
  quick_replies?: string[] | null;
  created_at?: string | null;
}
interface SessionInfo {
  identity: "user" | "guest";
  display_name: string;
  is_registered: boolean;
  // فاز ۶۲: وضعیت نشست — open/closed؛ بسته = باید دکمهٔ گفتگوی جدید بدهیم
  status?: string;
  rating: number | null;
  disclaimer: string;
  message_count: number;
}

function clientToken(): string {
  let t = "";
  try {
    t = localStorage.getItem(TOKEN_KEY) || "";
  } catch { /* حالت خصوصی مرورگر */ }
  if (!t || !/^[A-Za-z0-9_-]{8,64}$/.test(t)) {
    t = (crypto.randomUUID ? crypto.randomUUID() : `w${Date.now()}${Math.random().toString(36).slice(2, 10)}`).replace(/-/g, "");
    try { localStorage.setItem(TOKEN_KEY, t); } catch { /* ignore */ }
  }
  return t;
}

// فاز ۶۲: توکن تازه برای «گفتگوی جدید» — نشست بستهٔ قبلی کنار گذاشته می‌شود
function freshToken(): string {
  const t = (crypto.randomUUID ? crypto.randomUUID() : `w${Date.now()}${Math.random().toString(36).slice(2, 10)}`).replace(/-/g, "");
  try { localStorage.setItem(TOKEN_KEY, t); } catch { /* ignore */ }
  return t;
}

function loadStoredName(): string {
  try { return localStorage.getItem(NAME_KEY) || ""; } catch { return ""; }
}

function ChatBubbleIcon() {
  return (
    <Box component="svg" viewBox="0 0 24 24" sx={{ width: 26, height: 26, fill: "currentColor" }} aria-hidden>
      <path d="M12 3C6.9 3 2.8 6.6 2.8 11c0 2.5 1.3 4.7 3.4 6.2-.2 1-.7 2.2-1.6 3.1 1.9-.2 3.5-.9 4.6-1.7.9.2 1.8.4 2.8.4 5.1 0 9.2-3.6 9.2-8S17.1 3 12 3zm-4 9a1.3 1.3 0 1 1 0-2.6A1.3 1.3 0 0 1 8 12zm4 0a1.3 1.3 0 1 1 0-2.6A1.3 1.3 0 0 1 12 12zm4 0a1.3 1.3 0 1 1 0-2.6A1.3 1.3 0 0 1 16 12z" />
    </Box>
  );
}

function SendIcon() {
  // فلش ارسال — بدون وابستگی به @mui/icons-material
  return (
    <Box component="svg" viewBox="0 0 24 24" sx={{ width: 20, height: 20, fill: "currentColor", transform: "scaleX(-1)" }} aria-hidden>
      <path d="M2.5 21 23 12 2.5 3l.01 7L17 12 2.51 14z" />
    </Box>
  );
}

export default function PublicChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rating, setRating] = useState(0);
  const [ratingComment, setRatingComment] = useState("");
  const [rated, setRated] = useState(false);
  const [visitorName, setVisitorName] = useState(loadStoredName);
  const [nameDraft, setNameDraft] = useState("");
  const [showNameField, setShowNameField] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const tokenRef = useRef<string>("");
  const busyRef = useRef(false); // برای جلوگیری از تداخل polling با ارسال در جریان
  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
    });
  }, []);

  const openSession = useCallback(async (tok?: string) => {
    setOpening(true);
    setError(null);
    tokenRef.current = tok || clientToken();
    try {
      const r = await fetch("/api/v1/public/chat/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: tokenRef.current,
          first_page: window.location.pathname,
          visitor_name: loadStoredName() || undefined,
        }),
      });
      if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || "خطا در شروع گفتگو");
      const d = await r.json();
      setSession(d.session);
      setMessages(d.messages || []);
      if (d.session?.rating) setRated(true);
      // اگر گفتگو هنوز خالی است، پیام خوش‌آمد محلی نشان بده
      if ((d.messages || []).length === 0) {
        setMessages([{
          id: "welcome",
          role: "assistant",
          content:
            "سلام! به Rosepsy خوش آمدید. من دستیار آنلاین هستم؛ دربارهٔ نوبت‌دهی، مشاوران، خدمات و قیمت‌ها یا ورود به سامانه می‌توانم راهنمایی کنم.",
          quick_replies: [
            "می‌خواهم نوبت رزرو کنم",
            "مشاوران شما چه کسانی هستند؟",
            "خدمات و قیمت‌ها",
            "چطور وارد سامانه شوم؟",
          ],
        }]);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setOpening(false);
    }
  }, []);

  const handleOpen = () => {
    setOpen(true);
    if (!session && messages.length === 0) openSession();
  };

  // فاز ۶۲: شروع گفتگوی جدید — توکن تازه + پاک‌سازی وضعیت + بازکردن نشست نو
  const startNewChat = useCallback(() => {
    tokenRef.current = freshToken();
    setMessages([]);
    setSession(null);
    setRating(0);
    setRatingComment("");
    setRated(false);
    setError(null);
    setInput("");
    void openSession(tokenRef.current);
  }, [openSession]);

  useEffect(() => {
    if (open) scrollToBottom();
  }, [messages, open, scrollToBottom]);

  // فاز ۵۶ - polling زنده: پیام‌های جدید (از جمله پاسخ اپراتور پذیرش) هر ۴ ثانیه
  // از سرور خوانده می‌شود؛ هنگام ارسال در جریان، polling رد می‌شود تا optimistic
  // دوباره‌نویسی نشود؛ پیام موفق جایگزین optimistic می‌شود و تداخلی نیست.
  useEffect(() => {
    if (!open || !tokenRef.current) return;
    const iv = setInterval(async () => {
      if (busyRef.current) return;
      try {
        const r = await fetch(`/api/v1/public/chat/${encodeURIComponent(tokenRef.current)}/messages`);
        if (!r.ok) return;
        const d = await r.json();
        const items: ChatMessage[] = d.items || [];
        setMessages((prev) => {
          if (items.length > 0) return items;
          // گفتگو هنوز خالی است: پیام خوش‌آمد محلی و optimisticهای در راه حفظ شوند
          const locals = prev.filter((m) => m.id.startsWith("local-") || m.id === "welcome");
          return locals.length ? locals : items;
        });
      } catch { /* بی‌صدا - بار بعد */ }
    }, 4000);
    return () => clearInterval(iv);
  }, [open]);

  const send = useCallback(async (raw: string) => {
    const content = raw.trim();
    if (!content || busy || !tokenRef.current) return;
    setInput("");
    setError(null);
    const optimistic: ChatMessage = { id: `local-${Date.now()}`, role: "user", content };
    setMessages((m) => [...m, optimistic]);
    busyRef.current = true;
    setBusy(true);
    try {
      const r = await fetch(`/api/v1/public/chat/${encodeURIComponent(tokenRef.current)}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => null);
        throw new Error(d?.detail || "ارسال پیام ممکن نشد؛ لطفاً چند لحظه بعد دوباره تلاش کنید.");
      }
      const d = await r.json();
      // فاز ۵۶: وقتی اپراتور پذیرش در گفتگو فعال است، دستیار خودکار پاسخ نمی‌دهد
      // و message می‌تواند null باشد — فقط پیام خود کاربر روی سرور تثبیت می‌شود.
      setMessages((m) => [...m.filter((x) => x.id !== optimistic.id), optimistic, ...(d.message ? [d.message] : [])]);
      if (d.session) setSession(d.session);
    } catch (err) {
      // فاز ۷۰: متن پیام گم نشود — به کادر بازگردانده می‌شود تا کاربر فقط «ارسال» بزند
      setInput(content);
      const msg = (err as Error).message;
      setError(
        msg === "Failed to fetch"
          ? "ارتباط با سرور برقرار نشد؛ اتصال اینترنت را بررسی کنید و دوباره تلاش کنید."
          : msg,
      );
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, [busy]);

  const submitRating = async () => {
    if (!rating || !tokenRef.current) return;
    try {
      const r = await fetch(`/api/v1/public/chat/${encodeURIComponent(tokenRef.current)}/rating`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, comment: ratingComment.trim() || undefined }),
      });
      if (!r.ok) throw new Error("خطا در ثبت نظر");
      setRated(true);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const saveName = () => {
    const n = nameDraft.trim().slice(0, 100);
    if (!n) return;
    setVisitorName(n);
    try { localStorage.setItem(NAME_KEY, n); } catch { /* ignore */ }
    setShowNameField(false);
    // پس‌زمینه: نشست را با نام جدید به‌روزرسانی کن
    fetch("/api/v1/public/chat/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: tokenRef.current || clientToken(), visitor_name: n, first_page: window.location.pathname }),
    }).then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d?.session) setSession(d.session); })
      .catch(() => undefined);
  };

  const lastQuick = [...messages].reverse().find((m) => m.role === "assistant" && m.quick_replies?.length)?.quick_replies ?? null;
  const assistantCount = messages.filter((m) => m.role === "assistant").length;
  const showRateInline = !rated && assistantCount >= 2;
  // فاز ۶۲: گفتگوی بسته — ورودی غیرفعال + بنر «شروع گفتگوی جدید»
  const closed = !!session && session.status != null && session.status !== "open";

  return (
    <>
      {/* دکمهٔ شناور — پایین چپ (سایت راست‌به‌چپ) */}
      <Box sx={{ position: "fixed", left: 18, bottom: 18, zIndex: 1400 }}>
        {open ? (
          <IconButton
            onClick={() => setOpen(false)}
            aria-label="بستن گفتگو"
            sx={{ bgcolor: "primary.main", color: "#fff", "&:hover": { bgcolor: "primary.dark" }, width: 52, height: 52, boxShadow: 4 }}
          >
            <Box component="span" sx={{ fontSize: 22, lineHeight: 1 }}>✕</Box>
          </IconButton>
        ) : (
          <Tooltip title="گفتگوی آنلاین با ما" placement="top">
            <Fab color="primary" onClick={handleOpen} aria-label="باز کردن گفتگوی آنلاین"
              sx={{ width: 56, height: 56, boxShadow: 4 }}>
              <ChatBubbleIcon />
            </Fab>
          </Tooltip>
        )}
      </Box>

      {/* پنجرهٔ گفتگو */}
      {open && (
        <Paper
          elevation={8}
          sx={{
            position: "fixed", left: 16, bottom: 84, zIndex: 1400,
            width: { xs: "calc(100vw - 32px)", sm: 380 },
            height: { xs: "calc(100dvh - 130px)", sm: 540 },
            maxHeight: 640, display: "flex", flexDirection: "column",
            overflow: "hidden", borderRadius: 3, border: "1px solid #f3dce2",
          }}
          role="dialog"
          aria-label="گفتگوی آنلاین"
        >
          {/* سرصفحه */}
          <Box sx={{ background: "linear-gradient(90deg,#7c2740,#a83a54 55%,#5c4a6e)", color: "#fff", px: 2, py: 1.5 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              <Stack direction="row" spacing={1} alignItems="center">
                <Box component="span" sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: "#7CFC9B", display: "inline-block", boxShadow: "0 0 6px #7CFC9B" }} />
                <Box>
                  <Typography sx={{ fontWeight: 800, fontSize: 15 }}>گفتگوی آنلاین Rosepsy</Typography>
                  <Typography sx={{ fontSize: 11.5, opacity: 0.85 }}>
                    {session?.is_registered
                      ? `کاربر: ${session.display_name}`
                      : visitorName
                        ? `مهمان: ${visitorName}`
                        : "پاسخ‌گویی فوری — همه‌روزه"}
                  </Typography>
                </Box>
              </Stack>
              <Stack direction="row" spacing={0.5} alignItems="center">
                {/* فاز ۶۲: گفتگوی جدید همیشه در دسترس سرصفحه */}
                <Tooltip title="گفتگوی جدید" placement="bottom">
                  <IconButton
                    size="small"
                    onClick={startNewChat}
                    disabled={opening || (!session && messages.length === 0)}
                    aria-label="شروع گفتگوی جدید"
                    sx={{ color: "#fff", opacity: 0.9 }}
                  >
                    <Box component="span" sx={{ fontSize: 15, lineHeight: 1, fontWeight: 800 }}>＋</Box>
                  </IconButton>
                </Tooltip>
                {!session?.is_registered && (
                  <IconButton size="small" onClick={() => setShowNameField((v) => !v)}
                    aria-label="معرفی خودم" sx={{ color: "#fff", opacity: 0.9 }}>
                    <Box component="span" sx={{ fontSize: 15, fontWeight: 800 }}>✎</Box>
                  </IconButton>
                )}
              </Stack>
            </Stack>
          </Box>

          {/* معرفی نام اختیاری */}
          {showNameField && (
            <Box sx={{ px: 2, pt: 1.5, bgcolor: "#fdf6f7" }}>
              <Stack direction="row" spacing={1}>
                <TextField
                  size="small" fullWidth label="نام شما (اختیاری)" value={nameDraft}
                  onChange={(e) => setNameDraft(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); saveName(); } }}
                  inputProps={{ maxLength: 100 }}
                />
                <Button variant="contained" onClick={saveName} sx={{ whiteSpace: "nowrap" }}>ثبت</Button>
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                گفتگوی شما برای همین مرورگر ذخیره می‌شود؛ اگر وارد سامانه شوید به حساب شما متصل خواهد شد.
              </Typography>
            </Box>
          )}

          {/* پیام‌ها */}
          <Box ref={listRef} sx={{ flex: 1, overflowY: "auto", px: 1.5, py: 2, bgcolor: "#faf7f8" }}>
            {opening && (
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", textAlign: "center", py: 2 }}>
                در حال بازکردن گفتگو…
              </Typography>
            )}
            {messages.map((m) => {
              const isOperator = m.role === "operator"; // فاز ۵۶ - پاسخ زندهٔ پذیرش
              return (
                <Stack
                  key={m.id}
                  alignItems={m.role === "user" ? "flex-end" : "flex-start"}
                  sx={{ mb: 1.2 }}
                >
                  {isOperator && (
                    <Typography sx={{ fontSize: 10.5, fontWeight: 800, color: "#2e7d46", px: 0.5, mb: 0.3 }}>
                      پذیرش{m.sender_name ? ` — ${m.sender_name}` : ""}
                    </Typography>
                  )}
                  <Box
                    sx={{
                      maxWidth: "86%", px: 1.6, py: 1.1, borderRadius: 2.5,
                      borderBottomRightRadius: m.role === "user" ? 0.8 : 2.5,
                      borderBottomLeftRadius: m.role === "user" ? 2.5 : 0.8,
                      bgcolor: m.role === "user" ? "primary.main" : isOperator ? "#eef7f0" : "#fff",
                      color: m.role === "user" ? "#fff" : "text.primary",
                      border: m.role === "user" ? "none" : isOperator ? "1px solid #cfe8d6" : "1px solid #f0dde2",
                      whiteSpace: "pre-wrap", fontSize: 13.5, lineHeight: 1.9,
                      boxShadow: "0 1px 2px rgba(124,39,64,.08)",
                    }}
                  >
                    {m.content}
                  </Box>
                  {/* کارت‌های اقدام */}
                  {m.actions && m.actions.length > 0 && (
                    <Stack sx={{ maxWidth: "92%", mt: 0.8 }} spacing={0.8} alignItems="flex-start">
                      {m.actions.map((a, i) => (
                        <Button
                          key={`${m.id}-a-${i}`}
                          href={a.url}
                          size="small"
                          variant={a.kind === "primary" ? "contained" : "outlined"}
                          sx={{
                            textTransform: "none", fontSize: 12.5, py: 0.4, borderRadius: 2,
                            minWidth: 0, px: 1.4,
                          }}
                        >
                          {a.label}
                        </Button>
                      ))}
                    </Stack>
                  )}
                </Stack>
              );
            })}
            {busy && (
              <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
                در حال نوشتن…
              </Typography>
            )}
            {error && (
              <Typography variant="caption" color="error" sx={{ px: 1, display: "block" }}>
                {error}
              </Typography>
            )}
          </Box>

          {/* فاز ۶۲: بنر گفتگوی بسته + دکمهٔ شروع گفتگوی جدید */}
          {closed && (
            <Box sx={{ px: 1.5, pt: 1 }}>
              <Paper
                variant="outlined"
                sx={{ p: 1.4, bgcolor: "#fff8f0", borderColor: "#f0d9b8", textAlign: "center" }}
              >
                <Typography sx={{ fontSize: 12.5, fontWeight: 700, color: "#8a5a1e", mb: 1 }}>
                  این گفتگو بسته شده است؛ برای ادامه، گفتگوی تازه‌ای شروع کنید.
                </Typography>
                <Button
                  size="small"
                  variant="contained"
                  onClick={startNewChat}
                  disabled={opening}
                  sx={{ borderRadius: 2 }}
                >
                  {opening ? "در حال بازکردن…" : "شروع گفتگوی جدید"}
                </Button>
              </Paper>
            </Box>
          )}

          {/* پاسخ‌های پیشنهادی */}
          {!busy && lastQuick && (
            <Stack direction="row" sx={{ flexWrap: "wrap", gap: 0.6, px: 1.5, pb: 0.8 }} useFlexGap>
              {lastQuick.slice(0, 4).map((q) => (
                <Chip
                  key={q}
                  label={q}
                  size="small"
                  onClick={() => send(q)}
                  sx={{ fontSize: 11.5, bgcolor: "#fff", border: "1px solid #eed4db", cursor: "pointer" }}
                />
              ))}
            </Stack>
          )}

          {/* نظر دربارهٔ گفتگو */}
          {session && showRateInline && !rated && (
            <Box sx={{ px: 1.5, pb: 1 }}>
              <Paper variant="outlined" sx={{ p: 1.2, bgcolor: "#fffdf5", borderColor: "#f0e2c0" }}>
                <Typography sx={{ fontSize: 12, fontWeight: 700, mb: 0.5 }}>
                  نظر شما دربارهٔ این گفتگو چیست؟
                </Typography>
                <Stack direction="row" spacing={0.4} alignItems="center">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <Box
                      key={n}
                      component="button"
                      onClick={() => setRating(n)}
                      aria-label={`امتیاز ${n} از ۵`}
                      sx={{
                        border: "none", background: "none", cursor: "pointer", p: 0,
                        fontSize: 20, lineHeight: 1,
                        color: n <= (rating || 0) ? "#f5b301" : "#d8c9ce",
                      }}
                    >
                      ★
                    </Box>
                  ))}
                  {rating > 0 && (
                    <Button size="small" variant="contained" onClick={submitRating} sx={{ mr: 1, py: 0.2, fontSize: 12 }}>
                      ثبت نظر
                    </Button>
                  )}
                </Stack>
                {rating > 0 && (
                  <InputBase
                    fullWidth
                    multiline
                    maxRows={2}
                    placeholder="توضیح شما (اختیاری)"
                    value={ratingComment}
                    onChange={(e) => setRatingComment(e.target.value)}
                    sx={{ fontSize: 12, mt: 0.8, bgcolor: "#fff", border: "1px solid #eee0c8", borderRadius: 1.5, px: 1, py: 0.5 }}
                    inputProps={{ maxLength: 500 }}
                  />
                )}
              </Paper>
            </Box>
          )}
          {rated && (
            <Typography variant="caption" color="text.secondary" sx={{ px: 2, pb: 0.5, display: "block" }}>
              ✓ نظر شما ثبت شد؛ ممنون از بازخوردتان.
            </Typography>
          )}

          {/* ورودی پیام */}
          <Stack
            direction="row"
            spacing={1}
            alignItems="center"
            sx={{ borderTop: "1px solid #f3dce2", p: 1.2, bgcolor: "#fff" }}
          >
            <InputBase
              fullWidth
              placeholder={closed ? "این گفتگو بسته شده — گفتگوی جدیدی شروع کنید" : "پیام خود را بنویسید…"}
              value={input}
              disabled={closed}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
              inputProps={{ maxLength: 1000, "aria-label": "متن پیام" }}
              sx={{ bgcolor: "#faf7f8", borderRadius: 2.5, px: 1.5, py: 0.8, fontSize: 13.5, border: "1px solid #f0dde2" }}
            />
            <IconButton
              color="primary"
              onClick={() => send(input)}
              disabled={busy || closed || !input.trim()}
              aria-label="ارسال پیام"
              sx={{ bgcolor: "primary.main", color: "#fff", "&:hover": { bgcolor: "primary.dark" }, "&.Mui-disabled": { bgcolor: "#e8d7dd", color: "#fff" } }}
            >
              <SendIcon />
            </IconButton>
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ px: 2, pb: 1, bgcolor: "#fff", display: "block" }}>
            {session?.disclaimer || "این گفتگو جایگزین مشاورهٔ حرفه‌ای نیست."}
          </Typography>
        </Paper>
      )}
    </>
  );
}
