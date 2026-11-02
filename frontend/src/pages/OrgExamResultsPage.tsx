// فاز ۷۴ - آزمون‌های برگزارشده سازمانی
// فهرست برنامه‌های ارزیابی سازمان + نتایج تک‌تک اعضا در هر آزمون.
// مدیر سازمان (منتسب به یک سازمان) به‌صورت خودکار فقط برنامه‌های سازمان
// خودش را می‌بیند؛ اعضای عادی فقط برنامه‌هایی که عضو آن‌ها هستند.
import { useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Dialog, DialogContent, DialogTitle,
  IconButton, InputAdornment, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Tooltip, Typography,
} from "@mui/material";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import VisibilityRoundedIcon from "@mui/icons-material/VisibilityRounded";
import TaskAltRoundedIcon from "@mui/icons-material/TaskAltRounded";
import RadioButtonUncheckedRoundedIcon from "@mui/icons-material/RadioButtonUncheckedRounded";
import { useQuery } from "@tanstack/react-query";
import { errDetail } from "../api/client";
import {
  fetchOrgExamResultDetail, fetchOrgExamResults,
  type OrgExamResultSummary,
} from "../api/orgExamResults";
import { formatJalali } from "../utils/jalali";

const STATUS_META: Record<string, { label: string; color: "default" | "info" | "success" }> = {
  draft: { label: "پیش‌نویس", color: "default" },
  active: { label: "در حال برگزاری", color: "info" },
  closed: { label: "برگزارشده/پایان‌یافته", color: "success" },
};

function ProgramCard({ p, onOpen }: { p: OrgExamResultSummary; onOpen: () => void }) {
  const st = STATUS_META[p.status] ?? STATUS_META.draft;
  return (
    <Paper
      sx={{
        p: 2, borderRadius: 3, height: "100%", display: "flex", flexDirection: "column", gap: 1.25,
        transition: "box-shadow .2s, transform .2s",
        "&:hover": { boxShadow: 6, transform: "translateY(-2px)" },
      }}
    >
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography variant="subtitle1" fontWeight={800} sx={{ flex: 1 }}>{p.title}</Typography>
        <Chip size="small" color={st.color} label={st.label} />
      </Stack>
      <Typography variant="caption" color="text.secondary">
        {p.organization_name ?? "—"}
        {p.due_date ? ` · مهلت: ${formatJalali(p.due_date)}` : ""}
      </Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 1 }}>
        <Stat label="آزمون‌ها" value={p.tests_count} />
        <Stat label="اعضا" value={p.members_count} />
        <Stat label="تکمیل کامل" value={p.completed_members} />
      </Box>
      <Box>
        <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
          <Typography variant="caption" color="text.secondary">میانگین پیشرفت</Typography>
          <Typography variant="caption" fontWeight={800} dir="ltr">{p.progress_percent}٪</Typography>
        </Box>
        <Box sx={{ height: 8, borderRadius: 4, bgcolor: "grey.200", overflow: "hidden" }}>
          <Box sx={{ height: "100%", width: `${Math.min(100, p.progress_percent)}%`, bgcolor: "success.main" }} />
        </Box>
      </Box>
      <Box sx={{ flex: 1 }} />
      <Stack direction="row" justifyContent="flex-end">
        <Chip
          size="small" clickable color="primary" variant="outlined"
          icon={<VisibilityRoundedIcon />} label="مشاهده نتایج" onClick={onOpen}
        />
      </Stack>
    </Paper>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Paper variant="outlined" sx={{ p: 1, textAlign: "center", borderRadius: 2 }}>
      <Typography variant="subtitle1" fontWeight={800}>{value.toLocaleString("fa-IR")}</Typography>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Paper>
  );
}

function ResultDetailDialog({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["org-exam-result", id],
    queryFn: () => fetchOrgExamResultDetail(id as string),
    enabled: !!id,
  });

  return (
    <Dialog open={!!id} onClose={onClose} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <Box sx={{ flex: 1 }}>
          نتایج: {data?.title ?? "…"}
          {data?.organization_name ? (
            <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
              {data.organization_name}
            </Typography>
          ) : null}
        </Box>
        <IconButton onClick={onClose}><CloseRoundedIcon /></IconButton>
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error">{errDetail(error)}</Alert>}
        {isLoading && <Box display="flex" justifyContent="center" py={4}><CircularProgress /></Box>}
        {data && (
          <Stack spacing={2}>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>عضو</TableCell>
                    <TableCell>کد پرسنلی</TableCell>
                    <TableCell>واحد</TableCell>
                    {data.tests.map((t) => (
                      <TableCell key={t.test_id} align="center">{t.title}</TableCell>
                    ))}
                    <TableCell align="center">پیشرفت</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.members.length === 0 && (
                    <TableRow><TableCell colSpan={4 + data.tests.length}>عضوی ثبت نشده است.</TableCell></TableRow>
                  )}
                  {data.members.map((m) => (
                    <TableRow key={m.id}>
                      <TableCell>
                        <Typography variant="body2" fontWeight={700}>{m.full_name}</Typography>
                        {m.username && (
                          <Typography variant="caption" color="text.secondary" dir="ltr">@{m.username}</Typography>
                        )}
                      </TableCell>
                      <TableCell>{m.employee_code ?? "—"}</TableCell>
                      <TableCell>{m.unit ?? "—"}</TableCell>
                      {data.tests.map((t) => {
                        const r = m.tests.find((x) => x.test_id === t.test_id);
                        const done = !!r?.done;
                        return (
                          <TableCell key={t.test_id} align="center">
                            <Tooltip title={done ? `${r?.interpretation_label ?? "انجام‌شده"}${r?.score != null ? ` — نمره: ${r.score}` : ""}` : "انجام‌نشده"}>
                              <Chip
                                size="small"
                                color={done ? "success" : "default"}
                                variant={done ? "filled" : "outlined"}
                                icon={done ? <TaskAltRoundedIcon /> : <RadioButtonUncheckedRoundedIcon />}
                                label={done ? (r?.score != null ? `${r.score}` : "انجام‌شده") : "—"}
                              />
                            </Tooltip>
                          </TableCell>
                        );
                      })}
                      <TableCell align="center">
                        <Typography variant="body2" fontWeight={800} dir="ltr">{m.progress_percent}٪</Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <Typography variant="caption" color="text.secondary">
              نمره‌ها از آخرین اجرای هر آزمون (مرکز آزمون روان‌شناسی) محاسبه می‌شود.
            </Typography>
          </Stack>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function OrgExamResultsPage() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["org-exam-results", status, q],
    queryFn: () => fetchOrgExamResults({ status: status || undefined, q: q || undefined }),
  });
  const rows = data ?? [];

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
        <Typography variant="h6" fontWeight={700}>آزمون‌های برگزارشده سازمانی</Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <TextField
            size="small" placeholder="جستجو…" value={q}
            onChange={(e) => setQ(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment>
              ),
            }}
            sx={{ width: 220 }}
          />
          <TextField
            size="small" select label="وضعیت" value={status}
            onChange={(e) => setStatus(e.target.value)}
            SelectProps={{ native: true }} sx={{ minWidth: 150 }}
          >
            <option value="">همه</option>
            <option value="active">در حال برگزاری</option>
            <option value="closed">برگزارشده/پایان‌یافته</option>
            <option value="draft">پیش‌نویس</option>
          </TextField>
        </Stack>
      </Box>
      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      {isLoading && <Box display="flex" justifyContent="center" py={4}><CircularProgress /></Box>}
      {!isLoading && !error && rows.length === 0 && (
        <Alert severity="info">برنامهٔ آزمون سازمانی ثبت‌شده‌ای برای نمایش وجود ندارد.</Alert>
      )}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "minmax(0,1fr)", md: "repeat(2, minmax(0,1fr))", lg: "repeat(3, minmax(0,1fr))" }, gap: 2 }}>
        {rows.map((p) => (
          <ProgramCard key={p.id} p={p} onOpen={() => setOpenId(p.id)} />
        ))}
      </Box>
      <ResultDetailDialog id={openId} onClose={() => setOpenId(null)} />
    </Stack>
  );
}
