// فاز ۷۰ - «آزمون‌های برگزارشده» — چه کسی، کدام آزمون، چه زمانی، چه نمره‌ای
// + ایجاد پرونده برای آزمون‌دهنده + بازکردن گزارش کامل هر اجرا
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, IconButton, InputAdornment, Paper, Snackbar, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PrintRoundedIcon from "@mui/icons-material/PrintRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import { errDetail } from "../api/client";
import {
  PsychAttempt, createCaseFromAttempt, fetchPsychAttemptsAll,
} from "../api/psych";
import PsychResultReport from "../components/PsychResultReport";
import { formatJalaliDateTime } from "../utils/jalali";

export default function PsychAttemptsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [okMsg, setOkMsg] = useState<string | null>(null);
  const [report, setReport] = useState<PsychAttempt | null>(null);

  const attempts = useQuery({
    queryKey: ["psych-attempts-all", term],
    queryFn: () => fetchPsychAttemptsAll(term ? { q: term } : undefined),
  });

  const createCaseMut = useMutation({
    mutationFn: createCaseFromAttempt,
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: ["psych-attempts-all"] });
      setOkMsg(
        d.case_created
          ? `پروندهٔ ${d.case_number} ساخته شد و ${d.linked_attempts} آزمون به آن متصل شد.`
          : `${d.linked_attempts} آزمون به پروندهٔ موجود ${d.case_number} متصل شد.`,
      );
    },
    onError: (e) => setError(errDetail(e)),
  });

  const rows = attempts.data ?? [];

  return (
    <Stack spacing={2}>
      <Box display="flex" alignItems="center" gap={1.5} flexWrap="wrap">
        <Typography variant="h6" fontWeight={800} flexGrow={1}>آزمون‌های برگزارشده</Typography>
        <TextField
          size="small" placeholder="جست‌وجو: نام، نام کاربری، موبایل یا نام آزمون…"
          value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") setTerm(q.trim()); }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <IconButton size="small" onClick={() => setTerm(q.trim())}>
                  <SearchRoundedIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ),
          }}
          sx={{ minWidth: 300 }}
        />
      </Box>
      <Alert severity="info" icon={false}>
        فهرست همهٔ اجراهای آزمون با هویت آزمون‌دهنده. برای هر آزمون‌دهنده می‌توانید با
        «ایجاد پرونده» پروندهٔ مشاوره بسازید — همهٔ آزمون‌های او به همان پرونده متصل می‌شود.
      </Alert>

      {attempts.isLoading && <CircularProgress sx={{ alignSelf: "center", mt: 4 }} />}
      {attempts.error && <Alert severity="error">{errDetail(attempts.error)}</Alert>}

      {!attempts.isLoading && !attempts.error && (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>آزمون‌دهنده</TableCell>
                <TableCell>موبایل</TableCell>
                <TableCell>ابزار</TableCell>
                <TableCell>نمره</TableCell>
                <TableCell>تفسیر</TableCell>
                <TableCell>زمان اجرا</TableCell>
                <TableCell>دیده‌شده</TableCell>
                <TableCell>پرونده</TableCell>
                <TableCell>گزارش</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.length === 0 && (
                <TableRow><TableCell colSpan={9}>هنوز آزمونی برگزار نشده است.</TableCell></TableRow>
              )}
              {rows.map((a) => (
                <TableRow key={a.id} hover>
                  <TableCell>
                    <Typography variant="body2" fontWeight={700}>{a.user_display_name ?? "—"}</Typography>
                    <Typography variant="caption" color="text.secondary" dir="ltr">
                      {a.user_username}
                    </Typography>
                  </TableCell>
                  <TableCell dir="ltr" sx={{ fontSize: 12 }}>{a.user_mobile ?? "—"}</TableCell>
                  <TableCell>{a.test_title}</TableCell>
                  <TableCell>{a.score.toLocaleString("fa-IR")}</TableCell>
                  <TableCell>{a.interpretation_label}</TableCell>
                  <TableCell>{formatJalaliDateTime(a.created_at)}</TableCell>
                  <TableCell>
                    {a.viewed_at
                      ? <Chip size="small" color="success" variant="outlined" label={`✓ ${formatJalaliDateTime(a.viewed_at)}`} />
                      : <Chip size="small" variant="outlined" label="دیده‌نشده" />}
                  </TableCell>
                  <TableCell>
                    {a.case_number ? (
                      <Button size="small" variant="text"
                        onClick={() => a.case_id && navigate(`/cases/${a.case_id}`)}>
                        {a.case_number}
                      </Button>
                    ) : a.case_id === undefined || a.case_id === null ? (
                      <Button size="small" variant="contained"
                        loading={createCaseMut.isPending}
                        onClick={() => createCaseMut.mutate(a.id)}>
                        ایجاد پرونده
                      </Button>
                    ) : "—"}
                  </TableCell>
                  <TableCell>
                    {a.result_payload && (
                      <Button size="small" variant="outlined" onClick={() => setReport(a)}>
                        گزارش
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={!!report} onClose={() => setReport(null)} maxWidth="md" fullWidth
        PaperProps={{ sx: { borderRadius: 3 } }}>
        <DialogTitle sx={{ fontWeight: 800 }}>
          گزارش کامل — {report?.test_title}
          {report?.user_display_name && ` — ${report.user_display_name}`}
        </DialogTitle>
        <DialogContent dividers>
          {report?.result_payload && (
            <PsychResultReport payload={report.result_payload} attempt={report}
              testTitle={report.test_title ?? undefined} />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => window.print()} startIcon={<PrintRoundedIcon />}>چاپ</Button>
          <Button onClick={() => setReport(null)}>بستن</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!okMsg} autoHideDuration={6000} onClose={() => setOkMsg(null)}>
        <Alert severity="success" onClose={() => setOkMsg(null)}>{okMsg}</Alert>
      </Snackbar>
      <Snackbar open={!!error} autoHideDuration={6000} onClose={() => setError(null)}>
        <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>
      </Snackbar>
    </Stack>
  );
}
