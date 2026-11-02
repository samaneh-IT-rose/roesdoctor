// کارتابل مشاور — نوبت‌های امروز و آینده + روزها و ساعت‌های مشاوره (فاز ۷۴)
// مشاور بازه‌های هفتگی‌اش را همین‌جا تعریف می‌کند؛ پس از آن ثبت/جابه‌جایی
// نوبت و رزرو آنلاین فقط در همین بازه‌ها پذیرفته می‌شود.
import { useEffect, useMemo, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, Divider, Grid, IconButton, Paper,
  Stack, Switch, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TextField, Typography,
} from "@mui/material";
import AddCircleOutlineRoundedIcon from "@mui/icons-material/AddCircleOutlineRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import EventAvailableRoundedIcon from "@mui/icons-material/EventAvailableRounded";
import SaveRoundedIcon from "@mui/icons-material/SaveRounded";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { errDetail } from "../api/client";
import {
  fetchCounselorAppointments, fetchMyAvailability, saveMyAvailability,
  type AvailabilityWindow,
} from "../api/schedule";
import type { CounselorAppointmentRow } from "../api/schedule";
import { formatJalaliDateTime } from "../utils/jalali";

// هفتهٔ ایرانی: شنبه … جمعه (کد weekday مطابق date.weekday() در بک‌اند)
const WEEK_ORDER: Array<{ code: number; name: string }> = [
  { code: 5, name: "شنبه" },
  { code: 6, name: "یکشنبه" },
  { code: 0, name: "دوشنبه" },
  { code: 1, name: "سه‌شنبه" },
  { code: 2, name: "چهارشنبه" },
  { code: 3, name: "پنجشنبه" },
  { code: 4, name: "جمعه" },
];

interface DraftWindow extends AvailabilityWindow {
  _key: string;
}

function AvailabilityEditor() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["counselor-availability"],
    queryFn: fetchMyAvailability,
  });

  const [rows, setRows] = useState<DraftWindow[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    if (data && !loaded) {
      setRows(
        (data.items ?? []).map((w, i) => ({ ...w, _key: `w${i}` }))
      );
      setLoaded(true);
    }
  }, [data, loaded]);

  const saveMutation = useMutation({
    mutationFn: () =>
      saveMyAvailability({
        items: rows.map(({ weekday, start_time, end_time, is_active }) => ({
          weekday, start_time, end_time, is_active,
        })),
      }),
    onSuccess: () => {
      setSaveError(null);
      setSavedAt(new Date().toLocaleTimeString("fa-IR"));
      qc.invalidateQueries({ queryKey: ["counselor-availability"] });
    },
    onError: (e) => setSaveError(errDetail(e)),
  });

  const configured = !!data?.configured;

  const addRow = (weekday: number) => {
    setRows((prev) => [
      ...prev,
      { weekday, start_time: "09:00", end_time: "17:00", is_active: true, _key: `n${Date.now()}${prev.length}` },
    ]);
  };
  const updateRow = (key: string, patch: Partial<DraftWindow>) =>
    setRows((prev) => prev.map((r) => (r._key === key ? { ...r, ...patch } : r)));
  const removeRow = (key: string) => setRows((prev) => prev.filter((r) => r._key !== key));

  const rowsByDay = useMemo(() => {
    const m = new Map<number, DraftWindow[]>();
    for (const r of rows) {
      const list = m.get(r.weekday) ?? [];
      list.push(r);
      m.set(r.weekday, list);
    }
    return m;
  }, [rows]);

  if (isLoading) return <Box display="flex" justifyContent="center" py={3}><CircularProgress size={28} /></Box>;
  if (error) return <Alert severity="error">{errDetail(error)}</Alert>;

  return (
    <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
      <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
        <EventAvailableRoundedIcon color="primary" />
        <Typography variant="subtitle1" fontWeight={800} sx={{ flex: 1 }}>
          روزها و ساعت‌های مشاوره
        </Typography>
        {!configured && rows.length === 0 && (
          <Chip size="small" label="هنوز تعریف نشده — ساعت‌های پیش‌فرض سامانه ملاک است" variant="outlined" />
        )}
        {configured && (
          <Chip size="small" color="success" variant="outlined" label="برنامهٔ مشاوره ثبت شده است" />
        )}
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
        روزها و بازه‌های زمانی که می‌توانید مشاوره بدهید را مشخص کنید؛ بعد از ذخیره،
        ثبت و جابه‌جایی نوبت‌ها و رزرو آنلاین فقط در همین بازه‌ها پذیرفته می‌شود.
      </Typography>

      <Divider sx={{ my: 1.5 }} />

      <Grid container spacing={1.5}>
        {WEEK_ORDER.map(({ code, name }) => {
          const dayRows = rowsByDay.get(code) ?? [];
          return (
            <Grid item xs={12} sm={6} md={4} key={code}>
              <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2, height: "100%" }}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Typography variant="body2" fontWeight={800} sx={{ flex: 1 }}>{name}</Typography>
                  <IconButton size="small" color="primary" onClick={() => addRow(code)} aria-label={`افزودن بازه ${name}`}>
                    <AddCircleOutlineRoundedIcon fontSize="small" />
                  </IconButton>
                </Stack>
                {dayRows.length === 0 && (
                  <Typography variant="caption" color="text.disabled">بدون بازه — غیرفعال</Typography>
                )}
                <Stack spacing={0.75} sx={{ mt: dayRows.length ? 0.5 : 0 }}>
                  {dayRows.map((r) => (
                    <Stack key={r._key} direction="row" alignItems="center" spacing={0.75}>
                      <Switch
                        size="small" checked={r.is_active}
                        onChange={(e) => updateRow(r._key, { is_active: e.target.checked })}
                        inputProps={{ "aria-label": "فعال" }}
                      />
                      <TextField
                        type="time" size="small" value={r.start_time}
                        onChange={(e) => updateRow(r._key, { start_time: e.target.value })}
                        sx={{ width: 96 }} inputProps={{ step: 300 }}
                      />
                      <Typography variant="caption">تا</Typography>
                      <TextField
                        type="time" size="small" value={r.end_time}
                        onChange={(e) => updateRow(r._key, { end_time: e.target.value })}
                        sx={{ width: 96 }} inputProps={{ step: 300 }}
                      />
                      <IconButton size="small" color="error" onClick={() => removeRow(r._key)}>
                        <DeleteOutlineRoundedIcon fontSize="small" />
                      </IconButton>
                    </Stack>
                  ))}
                </Stack>
              </Paper>
            </Grid>
          );
        })}
      </Grid>

      {saveError && <Alert severity="error" sx={{ mt: 1.5 }}>{saveError}</Alert>}
      {savedAt && !saveError && (
        <Alert severity="success" sx={{ mt: 1.5 }}>
          برنامهٔ مشاوره ذخیره شد ({savedAt}) — از این پس نوبت‌ها فقط در بازه‌های بالا پذیرفته می‌شوند.
        </Alert>
      )}
      <Stack direction="row" justifyContent="flex-end" sx={{ mt: 1.5 }}>
        <Button
          variant="contained" startIcon={<SaveRoundedIcon />}
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending}
        >
          {saveMutation.isPending ? "در حال ذخیره…" : "ذخیرهٔ برنامهٔ مشاوره"}
        </Button>
      </Stack>
    </Paper>
  );
}

export default function CounselorWorklistPage() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["worklist-counselor-appointments"],
    queryFn: fetchCounselorAppointments,
  });
  const rows: CounselorAppointmentRow[] = data?.items ?? [];

  return (
    <Stack spacing={3}>
      <Box display="flex" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1}>
        <Typography variant="h6" fontWeight={700}>کارتابل مشاور — نوبت‌های امروز و آینده</Typography>
        <Button variant="outlined" onClick={() => navigate("/my-assessments")}>
          ارزیابی‌های من (پیش‌نویس/برگشتی)
        </Button>
      </Box>
      {error && <Alert severity="error">{errDetail(error)}</Alert>}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>پرونده</TableCell>
              <TableCell>متقاضی</TableCell>
              <TableCell>زمان</TableCell>
              <TableCell>مدت (دقیقه)</TableCell>
              <TableCell>محل</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow><TableCell colSpan={6} align="center"><CircularProgress size={24} /></TableCell></TableRow>
            )}
            {rows.length === 0 && (
              <TableRow><TableCell colSpan={6}>نوبتی در امروز و آینده وجود ندارد.</TableCell></TableRow>
            )}
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.case_number}</TableCell>
                <TableCell>{row.applicant_name}</TableCell>
                <TableCell>{formatJalaliDateTime(row.scheduled_at)}</TableCell>
                <TableCell>{row.duration_minutes ?? "—"}</TableCell>
                <TableCell>{row.location ?? "—"}</TableCell>
                <TableCell>
                  <Button size="small" onClick={() => navigate(`/cases/${row.case_id}`)}>باز کردن پرونده</Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* فاز ۷۴: تعریف روزها و ساعت‌های مشاوره توسط خود مشاور */}
      <AvailabilityEditor />
    </Stack>
  );
}
