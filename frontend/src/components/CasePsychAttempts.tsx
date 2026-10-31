// فاز ۷۰ - تب «نتایج آزمون» صفحهٔ پرونده — آزمون‌های روان‌شناسی متصل به پرونده
import {
  Alert, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent,
  DialogTitle, Paper, Snackbar, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { errDetail } from "../api/client";
import { PsychAttempt, fetchCasePsychAttempts } from "../api/psych";
import PsychResultReport from "../components/PsychResultReport";
import { formatJalaliDateTime } from "../utils/jalali";

export default function CasePsychAttempts({ caseId }: { caseId: string }) {
  const [report, setReport] = useState<PsychAttempt | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const q = useQuery({
    queryKey: ["case-psych-attempts", caseId],
    queryFn: () => fetchCasePsychAttempts(caseId),
  });

  if (q.isLoading) return <CircularProgress size={22} />;
  if (q.error) return <Alert severity="error">{errDetail(q.error)}</Alert>;
  const rows = q.data ?? [];

  return (
    <Stack spacing={1}>
      {rows.length === 0 && (
        <Alert severity="info" icon={false}>
          آزمونی به این پرونده متصل نشده است. از صفحهٔ «آزمون‌های برگزارشده» با «ایجاد پرونده»
          نتایج آزمون‌دهنده را به پروندهٔ او متصل کنید.
        </Alert>
      )}
      {rows.length > 0 && (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>ابزار</TableCell>
                <TableCell>نمره</TableCell>
                <TableCell>تفسیر</TableCell>
                <TableCell>زمان اجرا</TableCell>
                <TableCell>دیده‌شده</TableCell>
                <TableCell>گزارش</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((a) => (
                <TableRow key={a.id} hover>
                  <TableCell>{a.test_title}</TableCell>
                  <TableCell>{a.score.toLocaleString("fa-IR")}</TableCell>
                  <TableCell>{a.interpretation_label}</TableCell>
                  <TableCell>{formatJalaliDateTime(a.created_at)}</TableCell>
                  <TableCell>
                    {a.viewed_at
                      ? <Chip size="small" color="success" variant="outlined" label="✓" />
                      : <Chip size="small" variant="outlined" label="—" />}
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
      <Typography variant="caption" color="text.secondary">
        آزمون‌دهنده: {rows[0]?.user_display_name ?? "—"}
      </Typography>

      <Dialog open={!!report} onClose={() => setReport(null)} maxWidth="md" fullWidth
        PaperProps={{ sx: { borderRadius: 3 } }}>
        <DialogTitle sx={{ fontWeight: 800 }}>گزارش کامل — {report?.test_title}</DialogTitle>
        <DialogContent dividers>
          {report?.result_payload && (
            <PsychResultReport payload={report.result_payload} attempt={report}
              testTitle={report.test_title ?? undefined} />
          )}
        </DialogContent>
        <DialogActions><Button onClick={() => setReport(null)}>بستن</Button></DialogActions>
      </Dialog>
      <Snackbar open={!!err} autoHideDuration={6000} onClose={() => setErr(null)}>
        <Alert severity="error" onClose={() => setErr(null)}>{err}</Alert>
      </Snackbar>
    </Stack>
  );
}
