// فاز ۵۸ - پنل آزمون‌های سازمانی: فهرست برنامه‌های ارزیابی + ساخت برنامهٔ جدید
// هر برنامه متعلق به یک سازمان است (مثلاً شرکت نفت پارس) و کارتابل اختصاصی دارد.
import {
  Alert, Box, Button, Card, CardActionArea, CardContent, Chip, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControl, Grid, InputLabel, MenuItem, Paper, Select,
  Snackbar, Stack, TextField, Tooltip, Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import AssignmentTurnedInRoundedIcon from "@mui/icons-material/AssignmentTurnedInRounded";
import CorporateFareRoundedIcon from "@mui/icons-material/CorporateFareRounded";
import Diversity3RoundedIcon from "@mui/icons-material/Diversity3Rounded";
import GroupRoundedIcon from "@mui/icons-material/GroupRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import OpenInNewRoundedIcon from "@mui/icons-material/OpenInNewRounded";
import { errDetail } from "../api/client";
import { menuLevel } from "../api/auth";
import { useAuth } from "../auth/AuthContext";
import {
  OrgProgramSummary, OrgProgramStatus,
  createOrgProgram, fetchOrgPrograms,
} from "../api/orgPrograms";
import { fetchOrganizations, type Organization } from "../api/organizations";
import { fetchPublicPsychTests } from "../api/psych";
import { EmptyState } from "../components/FormKit";

const statusChip = (s: OrgProgramStatus) =>
  s === "active"
    ? { label: "فعال", color: "success" as const }
    : s === "draft"
      ? { label: "پیش‌نویس", color: "default" as const }
      : { label: "پایان‌یافته", color: "warning" as const };

export default function OrgProgramsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user: me } = useAuth();
  // فاز ۷۴: دکمهٔ ساخت فقط برای سطح «ویرایش» ماتریس منوها — سطح دیدن/خواندن فقط فهرست می‌بیند
  const canManage = menuLevel(me, "org-programs") === "edit";
  const [search, setSearch] = useState("");
  const [orgFilter, setOrgFilter] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [snack, setSnack] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // فرم ساخت برنامه
  const [fOrg, setFOrg] = useState("");
  const [fTitle, setFTitle] = useState("");
  const [fDesc, setFDesc] = useState("");
  const [fTests, setFTests] = useState<string[]>([]);

  const programs = useQuery({
    queryKey: ["org-programs"],
    queryFn: () => fetchOrgPrograms(),
  });
  // فاز ۷۴: فهرست سازمان‌ها فقط برای سطح ویرایش لود می‌شود — عضو عادی/فقط-دیدن
  // بدون ۴۰۳ اضافه (اعضا فهرست برنامه‌های خودشان را بدون فیلتر سازمان می‌بینند)
  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: fetchOrganizations,
    enabled: canManage,
  });
  const catalog = useQuery({ queryKey: ["public-psych-tests"], queryFn: fetchPublicPsychTests });

  const filtered = (programs.data ?? []).filter((p) => {
    const okSearch = !search || p.title.includes(search) || (p.organization_name ?? "").includes(search);
    const okOrg = !orgFilter || p.organization_id === orgFilter;
    return okSearch && okOrg;
  });

  const createMut = useMutation({
    mutationFn: () =>
      createOrgProgram({
        organization_id: fOrg,
        title: fTitle.trim(),
        description: fDesc.trim() || null,
        status: "active",
        test_ids: fTests,
      }),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["org-programs"] });
      setCreateOpen(false);
      setFOrg(""); setFTitle(""); setFDesc(""); setFTests([]);
      setSnack("برنامهٔ آزمون سازمانی ساخته شد");
      navigate(`/org-programs/${p.id}`);
    },
    onError: (e) => setErr(errDetail(e)),
  });

  return (
    <Stack spacing={2.5}>
      <Box>
        <Typography variant="h5" fontWeight={800}>آزمون‌های سازمانی</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          برای هر سازمان (کارفرما) یک برنامهٔ ارزیابی تعریف کنید: آزمون‌های موردنیاز از بانک آزمون،
          اعضا و کارکنان، مشاوران پروژه، راهنما و سوالات پرتکرار — همه در کارتابل اختصاصی همان سازمان.
        </Typography>
      </Box>

      {err && <Alert severity="error" onClose={() => setErr(null)}>{err}</Alert>}

      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap alignItems="center">
        <TextField
          size="small" sx={{ minWidth: 240 }}
          placeholder="جست‌وجوی برنامه…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{ startAdornment: <SearchRoundedIcon fontSize="small" sx={{ mr: 1, color: "text.secondary" }} /> }}
        />
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel>سازمان</InputLabel>
          <Select label="سازمان" value={orgFilter} onChange={(e) => setOrgFilter(e.target.value)}>
            <MenuItem value="">همهٔ سازمان‌ها</MenuItem>
            {(orgs.data ?? []).map((o) => (
              <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>
            ))}
          </Select>
        </FormControl>
        <Box flex={1} />
        {canManage && (
          <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={() => setCreateOpen(true)}>
            برنامهٔ آزمون جدید
          </Button>
        )}
      </Stack>

      {programs.isLoading ? (
        <Paper sx={{ p: 4, textAlign: "center", color: "text.secondary" }}>در حال بارگذاری…</Paper>
      ) : filtered.length === 0 ? (
        <Paper sx={{ p: 4 }}>
          <EmptyState
            title="هنوز برنامه‌ای تعریف نشده"
            desc="با دکمهٔ «برنامهٔ آزمون جدید» نخستین پروژهٔ ارزیابی سازمانی را بسازید؛ مثلاً «شرکت نفت پارس» با آزمون‌های سلامت روان و فرسودگی شغلی."
          />
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {filtered.map((p) => (
            <Grid item xs={12} sm={6} md={4} key={p.id}>
              <ProgramCard p={p} onOpen={() => navigate(`/org-programs/${p.id}`)} />
            </Grid>
          ))}
        </Grid>
      )}

      {/* ساخت برنامهٔ جدید */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>برنامهٔ آزمون سازمانی جدید</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl size="small" fullWidth required error={!fOrg && createMut.isError}>
              <InputLabel>سازمان</InputLabel>
              <Select label="سازمان" value={fOrg} onChange={(e) => setFOrg(e.target.value)}>
                {(orgs.data ?? []).filter((o) => o.is_active).map((o: Organization) => (
                  <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            {(orgs.data ?? []).length === 0 && (
              <Alert severity="info" sx={{ py: 1 }}>
                ابتدا از منوی «سازمان‌ها» سازمان را ثبت کنید، سپس برنامه بسازید.
              </Alert>
            )}
            <TextField
              size="small" label="عنوان برنامه" required fullWidth
              placeholder="مثلاً: پروژهٔ ارزیابی سلامت روان کارکنان ۱۴۰۵"
              value={fTitle} onChange={(e) => setFTitle(e.target.value)}
            />
            <TextField
              size="small" label="توضیح کوتاه" fullWidth multiline minRows={2}
              value={fDesc} onChange={(e) => setFDesc(e.target.value)}
            />
            <Box>
              <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>
                آزمون‌های موردنیاز (اختیاری — بعداً هم قابل افزودن است)
              </Typography>
              <Typography variant="caption" color="text.secondary">
                از بانک آزمون‌های منتشرشدهٔ مرکز آزمون انتخاب کنید
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1, maxHeight: 200, overflowY: "auto" }}>
                {(catalog.data ?? []).map((t) => {
                  const on = fTests.includes(t.id);
                  return (
                    <Chip
                      key={t.id}
                      size="small"
                      label={t.title}
                      color={on ? "primary" : "default"}
                      variant={on ? "filled" : "outlined"}
                      onClick={() => setFTests(on ? fTests.filter((x) => x !== t.id) : [...fTests, t.id])}
                    />
                  );
                })}
              </Box>
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>انصراف</Button>
          <Button
            variant="contained" disabled={!fOrg || fTitle.trim().length < 3 || createMut.isPending}
            onClick={() => createMut.mutate()}
          >
            ساخت برنامه و ورود به کارتابل
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={!!snack} autoHideDuration={3500} onClose={() => setSnack(null)} message={snack ?? ""} />
    </Stack>
  );
}

function ProgramCard({ p, onOpen }: { p: OrgProgramSummary; onOpen: () => void }) {
  const st = statusChip(p.status);
  return (
    <Card sx={{ height: "100%", borderRadius: 3 }}>
      <CardActionArea onClick={onOpen} sx={{ height: "100%" }}>
        <CardContent>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
            <CorporateFareRoundedIcon fontSize="small" color="primary" />
            <Typography variant="body2" color="text.secondary" noWrap>
              {p.organization_name ?? "—"}
            </Typography>
            <Box flex={1} />
            <Chip size="small" {...st} />
          </Stack>
          <Typography variant="subtitle1" fontWeight={800} sx={{ mb: 1, minHeight: 44 }}>
            {p.title}
          </Typography>
          <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap sx={{ color: "text.secondary" }}>
            <Tooltip title="آزمون‌های برنامه">
              <Chip size="small" icon={<AssignmentTurnedInRoundedIcon />} label={p.tests_count} variant="outlined" />
            </Tooltip>
            <Tooltip title="اعضا">
              <Chip size="small" icon={<GroupRoundedIcon />} label={p.members_count} variant="outlined" />
            </Tooltip>
            <Tooltip title="مشاوران پروژه">
              <Chip size="small" icon={<Diversity3RoundedIcon />} label={p.counselors_count} variant="outlined" />
            </Tooltip>
            {p.due_date && (
              <Tooltip title="مهلت انجام">
                <Chip size="small" label={`مهلت: ${p.due_date}`} variant="outlined" />
              </Tooltip>
            )}
          </Stack>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 1.5 }}>
            <Box sx={{ flex: 1, height: 6, borderRadius: 3, bgcolor: "action.hover", overflow: "hidden" }}>
              <Box sx={{ width: `${p.progress_percent}%`, height: "100%", bgcolor: "primary.main" }} />
            </Box>
            <Typography variant="caption" color="text.secondary">
              پیشرفت {p.progress_percent}٪
            </Typography>
            <OpenInNewRoundedIcon fontSize="small" color="action" />
          </Stack>
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
