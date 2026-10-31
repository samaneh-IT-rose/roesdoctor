// فاز ۳۵ - B25/B26/B27: دستیار هوشمند (D07 پلاگین‌پذیر)
// فاز ۵۳ - عامل هوشمند (الگوی deepseek-harness): چت با حلقهٔ عامل، چیپ ابزارها و نشست‌های ماندگار
import {
  Alert, Box, Button, Chip, CircularProgress, IconButton, List, ListItem, ListItemButton, ListItemText,
  Paper, Snackbar, Stack, Tab, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TextField, Tooltip, Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { errDetail } from "../api/client";
import {
  AgentChatResult, AgentMessageItem, AgentSessionItem, NoShowRiskItem, RecommendationItem,
  agentChat, deleteAgentSession, fetchAgentConfig, fetchAgentMessages, fetchAgentSessions,
  fetchAiConfig, fetchNoShowRisk, fetchRecommendations,
} from "../api/ai";

type ChatBubble =
  | { kind: "user"; text: string }
  | { kind: "ai"; text: string; provider?: string; steps?: { tool_title: string; summary: string }[] };

export default function AssistantPage() {
  const [tab, setTab] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatBubble[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const qc = useQueryClient();

  const config = useQuery({ queryKey: ["ai-config"], queryFn: fetchAiConfig });
  const agentCfg = useQuery({ queryKey: ["agent-config"], queryFn: fetchAgentConfig });
  const sessions = useQuery({
    queryKey: ["agent-sessions"],
    queryFn: () => fetchAgentSessions(1, 20),
    enabled: tab === 0,
  });
  const recs = useQuery({ queryKey: ["ai-recs"], queryFn: fetchRecommendations, enabled: tab === 1 });
  const risk = useQuery({ queryKey: ["ai-noshow"], queryFn: () => fetchNoShowRisk(7), enabled: tab === 2 });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const openSession = async (s: AgentSessionItem) => {
    setSessionId(s.id);
    setBusy(true);
    try {
      const hist = await fetchAgentMessages(s.id);
      const bubbles: ChatBubble[] = [];
      for (const m of hist.items as AgentMessageItem[]) {
        if (m.role === "user") bubbles.push({ kind: "user", text: m.content });
        else if (m.role === "assistant") bubbles.push({ kind: "ai", text: m.content, provider: m.provider ?? undefined });
      }
      setMessages(bubbles);
    } catch (e) {
      setError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const newSession = () => {
    setSessionId(null);
    setMessages([]);
  };

  const removeSession = async (id: string) => {
    try {
      await deleteAgentSession(id);
      if (sessionId === id) newSession();
      void qc.invalidateQueries({ queryKey: ["agent-sessions"] });
    } catch (e) {
      setError(errDetail(e));
    }
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setMessages((m) => [...m, { kind: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const res: AgentChatResult = await agentChat(text, sessionId);
      setSessionId(res.session_id);
      setMessages((m) => [
        ...m,
        {
          kind: "ai",
          text: `${res.response}\n\n— ${res.disclaimer}`,
          provider: res.fallback_used ? `${res.provider} (پاسخ قاعده‌محور)` : res.provider,
          steps: (res.steps ?? []).map((s) => ({ tool_title: s.tool_title, summary: JSON.stringify(s.result).slice(0, 120) })),
        },
      ]);
      void qc.invalidateQueries({ queryKey: ["agent-sessions"] });
    } catch (e) {
      setError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const active = config.data;
  const acfg = agentCfg.data;

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800}>دستیار هوشمند (عامل فاز ۵۳)</Typography>
        {active && (
          <Chip size="small" variant="outlined"
            color={active.fallback_applied ? "warning" : "success"}
            label={`سرویس فعال: ${active.active_provider}${active.fallback_applied ? " (fallback)" : ""}`} />
        )}
        {acfg && (
          <Chip size="small" color={acfg.llm_ready ? "primary" : "secondary"}
            label={acfg.llm_ready
              ? `حلقهٔ عامل فعال — ${acfg.tools.length} ابزار`
              : "حالت اقدام‌محور (قاعده‌محور — بدون کلید LLM)"} />
        )}
      </Box>
      {active && (
        <Alert severity="info">
          D07 — سرویس پلاگین‌پذیر؛ پیکربندی: {active.configured_provider}، فعال: {active.active_provider}؛
          سقف {active.rate_limit_per_minute} پیام در دقیقه. {active.disclaimer}
          {acfg && !acfg.llm_ready &&
            " حالت قاعده‌محور هم اقدام‌محور است: رزرو، نتایج آزمون، پرونده، سفارش‌ها و کیف پول را از دل همین گفتگو انجام می‌دهد. برای پاسخ‌های آزادتر می‌توانید AI_API_KEY و AI_API_BASE_URL را در .env تنظیم کنید."}
        </Alert>
      )}
      <Paper sx={{ p: 1.5 }}>
        <Stack direction="row" spacing={1}>
          <Tab label="گفتگو با عامل" onClick={() => setTab(0)} />
          <Tab label="پیشنهاد خدمات (B26)" onClick={() => setTab(1)} />
          <Tab label="ریسک عدم‌حضور (B27)" onClick={() => setTab(2)} />
        </Stack>
      </Paper>

      {tab === 0 && (
        <Stack direction="row" spacing={2} alignItems="flex-start">
          {/* نشست‌ها */}
          <Paper variant="outlined" sx={{ width: 260, flexShrink: 0, p: 1, display: { xs: "none", md: "block" } }}>
            <Button fullWidth variant="contained" size="small" onClick={newSession}>+ گفتگوی جدید</Button>
            <List dense>
              {(sessions.data?.items ?? []).map((s) => (
                <ListItem
                  key={s.id}
                  disablePadding
                  secondaryAction={
                    <Tooltip title="حذف نشست">
                      <IconButton edge="end" size="small" onClick={() => void removeSession(s.id)}>✕</IconButton>
                    </Tooltip>
                  }
                >
                  <ListItemButton selected={sessionId === s.id} onClick={() => void openSession(s)} dense>
                    <ListItemText primary={s.title} primaryTypographyProps={{ noWrap: true, fontSize: 13 }}
                      secondary={s.updated_at ? new Date(s.updated_at).toLocaleDateString("fa-IR") : undefined} />
                  </ListItemButton>
                </ListItem>
              ))}
              {!(sessions.data?.items ?? []).length && (
                <Typography variant="caption" color="text.secondary" sx={{ px: 2 }}>
                  هنوز نشستی ندارید
                </Typography>
              )}
            </List>
          </Paper>
          {/* گفتگو */}
          <Paper variant="outlined" sx={{ p: 2, minHeight: 380, flexGrow: 1, display: "flex", flexDirection: "column" }}>
            <Stack spacing={1} flexGrow={1}>
              {messages.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  بپرسید یا بخواهید: «می‌خواهم نوبت رزرو کنم»، «نتایج آزمون‌هام را بگو»،
                  «پروندهٔ مشاورهٔ من»، «سفارش‌های اخیرم را بگو»، «شعب تهران را لیست کن»،
                  «مانده کیف پولم»
                  {acfg?.tools.some((t) => t.staff_only) &&
                    "، «خلاصهٔ پرونده‌ها را بده»، «ثبت درخواست مشاوره برای نام مراجع 09xxxxxxxxx»"} …
                </Typography>
              )}
              {messages.map((m, i) => (
                <Stack key={i} spacing={0.5} alignItems={m.kind === "user" ? "flex-end" : "flex-start"}>
                  {"steps" in m && m.steps && m.steps.length > 0 && (
                    <Stack direction="row" spacing={0.5} flexWrap="wrap">
                      {m.steps.map((s, j) => (
                        <Tooltip key={j} title={s.summary}>
                          <Chip size="small" variant="outlined" color="info" label={`🔧 ${s.tool_title}`} />
                        </Tooltip>
                      ))}
                    </Stack>
                  )}
                  <Paper variant="outlined" sx={{
                    p: 1, maxWidth: "85%", alignSelf: m.kind === "user" ? "flex-end" : "flex-start",
                    bgcolor: m.kind === "user" ? "action.hover" : "background.paper",
                  }}>
                    <Typography variant="caption">
                      {m.kind === "user" ? "شما" : `دستیار${m.provider ? ` (${m.provider})` : ""}`}
                    </Typography>
                    <Typography sx={{ whiteSpace: "pre-wrap" }}>{m.text}</Typography>
                  </Paper>
                </Stack>
              ))}
              {busy && <CircularProgress size={18} sx={{ alignSelf: "flex-start", mx: 1 }} />}
              <div ref={bottomRef} />
            </Stack>
            <Stack direction="row" spacing={1} mt={1}>
              <TextField size="small" fullWidth placeholder="پیام شما…" value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }} />
              <Button variant="contained" onClick={() => void send()} disabled={busy || !input.trim()}>
                ارسال
              </Button>
            </Stack>
          </Paper>
        </Stack>
      )}

      {tab === 1 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead><TableRow><TableCell>خدمت پیشنهادی (هم‌دسته آخرین سفارش شما)</TableCell></TableRow></TableHead>
            <TableBody>
              {(recs.data as RecommendationItem[] ?? []).map((r) => (
                <TableRow key={r.service_id}><TableCell>{r.title}</TableCell></TableRow>
              ))}
              {!(recs.data ?? []).length && (
                <TableRow><TableCell>هنوز پیشنهادی برای شما نیست (نیازمند حداقل یک سفارش)</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {tab === 2 && (
        <TableContainer component={Paper}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>نوبت</TableCell><TableCell>ریسک</TableCell><TableCell>سطح</TableCell><TableCell>عوامل</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(risk.data?.items ?? []).map((it: NoShowRiskItem) => (
                <TableRow key={it.appointment_id}>
                  <TableCell dir="ltr" sx={{ fontSize: 11 }}>
                    {it.scheduled_at ? new Date(it.scheduled_at).toLocaleString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>{it.risk_score}٪</TableCell>
                  <TableCell>{it.risk_level}</TableCell>
                  <TableCell>{it.factors.join("، ")}</TableCell>
                </TableRow>
              ))}
              {!(risk.data?.items ?? []).length && (
                <TableRow><TableCell colSpan={4}>نوبت آینده‌ای در پنجره ۷ روز نیست</TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
    </Stack>
  );
}
