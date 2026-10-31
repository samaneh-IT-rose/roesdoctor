// فاز ۷۰ - «پرونده‌های مشاوره» کاربران — فهرست + خط زمانی تاریخچهٔ آزمون‌ها و مشاوره‌ها
import {
  Alert, Box, Button, Chip, CircularProgress, Divider, InputAdornment, Paper, Stack,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import ScienceRoundedIcon from "@mui/icons-material/ScienceRounded";
import ForumRoundedIcon from "@mui/icons-material/ForumRounded";
import EventRoundedIcon from "@mui/icons-material/EventRounded";
import { errDetail } from "../api/client";
import {
  CounselingFileItem, CounselingFileOut, fetchCounselingFileDetail, fetchCounselingFiles,
} from "../api/counseling";
import { formatJalaliDateTime } from "../utils/jalali";

const KIND_META: Record<CounselingFileItem["kind"], { label: string; color: "primary" | "secondary" | "info" }> = {
  psych_test: { label: "آزمون", color: "primary" },
  consultation: { label: "مشاوره", color: "secondary" },
  appointment: { label: "نوبت", color: "info" },
};

function Timeline({ data }: { data: CounselingFileOut }) {
  return (
    <Stack spacing={0.5}>
      {data.items.length === 0 && (
        <Typography variant="body2" color="text.secondary">فعالیتی ثبت نشده است.</Typography>
      )}
      {data.items.map((it) => {
        const m = KIND_META[it.kind];
        return (
          <Stack key={`${it.kind}-${it.id}`} direction="row" spacing={1} alignItems="center"
            sx={{ border: 1, borderColor: "divider", borderRadius: 1.5, p: 1 }}>
            {it.kind === "psych_test" && <ScienceRoundedIcon fontSize="small" color="primary" />}
            {it.kind === "consultation" && <ForumRoundedIcon fontSize="small" color="secondary" />}
            {it.kind === "appointment" && <EventRoundedIcon fontSize="small" color="info" />}
            <Chip size="small" color={m.color} variant="outlined" label={m.label} sx={{ minWidth: 64 }} />
            <Box flexGrow={1} minWidth={120}>
              <Typography variant="body2" fontWeight={700}>{it.title}</Typography>
              <Typography variant="caption" color="text.secondary">
                {it.kind === "psych_test" && `نمره ${it.score?.toLocaleString("fa-IR")} — ${it.interpretation_label ?? ""}`}
                {it.kind === "consultation" &&
                  `وضعیت: ${it.status ?? "—"}${it.payment_status === "paid" ? " — پرداخت‌شده" : ""}`}
                {it.kind === "appointment" && `${it.case_number ?? ""} ${it.location ? `— ${it.location}` : ""}`}
              </Typography>
            </Box>
            <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
              {formatJalaliDateTime(it.at)}
            </Typography>
          </Stack>
        );
      })}
    </Stack>
  );
}

export default function CounselingFilesPage() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const files = useQuery({
    queryKey: ["counseling-files", q],
    queryFn: () => fetchCounselingFiles(q.trim()),
  });
  const detail = useQuery({
    queryKey: ["counseling-file", selected],
    queryFn: () => fetchCounselingFileDetail(selected as string),
    enabled: !!selected,
  });

  return (
    <Stack spacing={2}>
      <Typography variant="h6" fontWeight={800}>پرونده‌های مشاوره کاربران</Typography>
      <Alert severity="info" icon={false}>
        برای هر کاربر یک پروندهٔ مشاوره نگه داشته می‌شود: تاریخچهٔ آزمون‌ها، درخواست‌ها و
        نوبت‌های مشاوره به همراه زمان دقیق هر رخداد. با اولین آزمون یا رزرو، پرونده خودکار ساخته می‌شود.
      </Alert>

      <TextField
        size="small" placeholder="جست‌وجو بر نام، موبایل یا شمارهٔ پرونده (UF-…)…"
        value={q} onChange={(e) => setQ(e.target.value)}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment>
          ),
        }}
        sx={{ maxWidth: 420 }}
      />

      {files.isLoading && <CircularProgress sx={{ alignSelf: "center", mt: 3 }} />}
      {files.error && <Alert severity="error">{errDetail(files.error)}</Alert>}

      {files.data && files.data.length === 0 && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography color="text.secondary">پرونده‌ای یافت نشد؛ با اولین آزمون یا رزرو ساخته می‌شود.</Typography>
        </Paper>
      )}

      {files.data && files.data.length > 0 && (
        <Stack direction="row" spacing={2} alignItems="flex-start" flexWrap="wrap" useFlexGap>
          <TableContainer component={Paper} variant="outlined" sx={{ minWidth: 380, flex: "1 1 380px" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>کاربر</TableCell>
                  <TableCell>شمارهٔ پرونده</TableCell>
                  <TableCell>آزمون‌ها</TableCell>
                  <TableCell>آخرین فعالیت</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {files.data.map((f) => (
                  <TableRow key={f.user_id} hover selected={selected === f.user_id}>
                    <TableCell>
                      <Typography variant="body2" fontWeight={700}>{f.display_name}</Typography>
                      <Typography variant="caption" color="text.secondary" dir="ltr">
                        {f.username}{f.mobile ? ` — ${f.mobile}` : ""}
                      </Typography>
                    </TableCell>
                    <TableCell dir="ltr" sx={{ fontSize: 12 }}>{f.file_code}</TableCell>
                    <TableCell>{f.attempt_count.toLocaleString("fa-IR")}</TableCell>
                    <TableCell>{formatJalaliDateTime(f.last_activity_at)}</TableCell>
                    <TableCell>
                      <Button size="small" variant="outlined"
                        onClick={() => setSelected(f.user_id)}>
                        مشاهده
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {selected && (
            <Paper variant="outlined" sx={{ p: 2, flex: "1 1 420px", minWidth: 320 }}>
              {detail.isLoading && <CircularProgress size={22} />}
              {detail.error && <Alert severity="error">{errDetail(detail.error)}</Alert>}
              {detail.data && (
                <Stack spacing={1.5}>
                  <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
                    <Typography variant="subtitle1" fontWeight={800} flexGrow={1}>
                      {detail.data.user.display_name}
                    </Typography>
                    <Chip size="small" variant="outlined" dir="ltr" label={detail.data.file.file_code} />
                    {detail.data.user.mobile && (
                      <Chip size="small" variant="outlined" dir="ltr" label={detail.data.user.mobile} />
                    )}
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    {detail.data.counts.psych_tests.toLocaleString("fa-IR")} آزمون —{" "}
                    {detail.data.counts.consultations.toLocaleString("fa-IR")} درخواست/رزرو مشاوره —{" "}
                    {detail.data.counts.appointments.toLocaleString("fa-IR")} نوبت
                  </Typography>
                  <Divider />
                  <Timeline data={detail.data} />
                  <Button size="small" variant="text" onClick={() => navigate("/psych-attempts")}>
                    رفتن به آزمون‌های برگزارشده
                  </Button>
                </Stack>
              )}
            </Paper>
          )}
        </Stack>
      )}
    </Stack>
  );
}
