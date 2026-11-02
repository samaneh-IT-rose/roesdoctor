import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { errDetail } from "../api/client";
import { startImpersonation } from "../auth/impersonation";
import { useAuth } from "../auth/AuthContext";
import {
  ROLE_OPTIONS,
  createActivationToken,
  createUser,
  fetchUsers,
  impersonateUser,
  resetUserPassword,
  roleTitle,
  setUserRoles,
  updateUserOrganization,
  updateUserStatus,
} from "../api/auth";
import { fetchRoles } from "../api/rbac";
import { fetchOrganizations } from "../api/organizations";
import type { UserRow } from "../api/auth";
import { formatJalaliDateTime } from "../utils/jalali";
import { useLocation, useNavigate } from "react-router-dom";

const STATUS_META: Record<string, { label: string; color: "success" | "warning" | "default" }> = {
  active: { label: "فعال", color: "success" },
  pending_activation: { label: "در انتظار فعال‌سازی", color: "warning" },
  disabled: { label: "غیرفعال", color: "default" },
};

export default function UsersPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const { user: me } = useAuth();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [tokenInfo, setTokenInfo] = useState<{ username: string; token: string; expires_at: string } | null>(null);
  const [rolesTarget, setRolesTarget] = useState<UserRow | null>(null);
  const [pwTarget, setPwTarget] = useState<UserRow | null>(null);
  const [pwResult, setPwResult] = useState<string | null>(null);
  // فاز ۷۴: فهرست سازمان‌ها برای نمایش/انتساب ستون سازمان
  const orgsQ = useQuery({ queryKey: ["organizations"], queryFn: fetchOrganizations });
  const orgName = (id: string | null) =>
    id ? orgsQ.data?.find((o) => o.id === id)?.name ?? "—" : "—";

  const { data, isLoading } = useQuery({
    queryKey: ["users", page, search],
    queryFn: () => fetchUsers({ page: page + 1, page_size: 10, search: search || undefined }),
  });

  const toggleStatus = useMutation({
    mutationFn: (row: UserRow) =>
      updateUserStatus(row.id, row.status === "disabled" ? "active" : "disabled"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
    onError: (e) => setError(errDetail(e)),
  });

  const makeToken = useMutation({
    mutationFn: (row: UserRow) => createActivationToken(row.id),
    onSuccess: (res, row) =>
      setTokenInfo({ username: row.username, token: res.token, expires_at: res.expires_at }),
    onError: (e) => setError(errDetail(e)),
  });

  // فاز ۶۰: «ورود به کارتابل» = ورود واقعی با هویت کاربر (impersonation) —
  // کل پنل با نقش و دسترسی‌های همان کاربر بالا می‌آید؛ منوها، داده‌ها، همه‌چیز.
  const impersonate = useMutation({
    mutationFn: (row: UserRow) => impersonateUser(row.id),
    onSuccess: (res, row) => {
      startImpersonation({
        token: res.access_token,
        userId: row.id,
        username: row.username,
        displayName: row.display_name,
        returnPath: location.pathname + location.search,
        startedAt: new Date().toISOString(),
      });
      // reload کامل — AuthContext با توکن جدید /auth/me همان کاربر را می‌گیرد
      const base = import.meta.env.BASE_URL.replace(/\/$/, "");
      window.location.assign(`${base}/`);
    },
    onError: (e) => setError(errDetail(e)),
  });

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2}>
        <Typography variant="h6" fontWeight={700}>
          مدیریت حساب‌ها و نقش‌ها
        </Typography>
        <TextField
          size="small"
          label="جست‌وجو (نام کاربری یا نام نمایشی)"
          value={search}
          onChange={(e) => {
            setPage(0);
            setSearch(e.target.value);
          }}
          sx={{ width: 320 }}
        />
        <Button variant="contained" onClick={() => setCreateOpen(true)}>
          حساب جدید
        </Button>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>نام کاربری</TableCell>
              <TableCell>نام نمایشی</TableCell>
              <TableCell>نقش‌ها</TableCell>
              <TableCell>سازمان</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>آخرین ورود</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <CircularProgress size={24} />
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((row) => {
              const meta = STATUS_META[row.status] ?? { label: row.status, color: "default" as const };
              return (
                <TableRow key={row.id}>
                  <TableCell>{row.username}</TableCell>
                  <TableCell>{row.display_name}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      {row.roles.length === 0 && <Typography variant="caption">—</Typography>}
                      {row.roles.map((r) => (
                        <Chip key={r} label={roleTitle(r)} size="small" variant="outlined" />
                      ))}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    {row.organization_id ? (
                      <Chip size="small" color="info" variant="outlined" label={orgName(row.organization_id)} />
                    ) : (
                      <Typography variant="caption" color="text.disabled">همهٔ داده‌ها</Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip label={meta.label} color={meta.color} size="small" />
                  </TableCell>
                  <TableCell>
                    {row.last_login_at ? formatJalaliDateTime(row.last_login_at) : "—"}
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      {/* فاز ۶۰: ورود واقعی با هویت این کاربر — کل پنل از نقطهٔ نظر او */}
                      <Tooltip title="ورود با هویت این کاربر — همهٔ بخش‌ها از نقطهٔ نظر خودش">
                        <span>
                          <Button
                            size="small"
                            color="primary"
                            variant="contained"
                            disabled={
                              impersonate.isPending ||
                              row.status !== "active" ||
                              row.id === me?.id
                            }
                            onClick={() => impersonate.mutate(row)}
                          >
                            {impersonate.isPending ? "در حال ورود…" : "ورود به کارتابل"}
                          </Button>
                        </span>
                      </Tooltip>
                      {/* نمای خلاصهٔ فقط-مشاهده (نسخهٔ قبل) همچنان در دسترس است */}
                      <Button size="small" onClick={() => navigate(`/cartable/${row.id}`)}>
                        خلاصه
                      </Button>
                      <Button
                        size="small"
                        onClick={() => {
                          if (window.confirm("تغییر وضعیت این حساب؟")) toggleStatus.mutate(row);
                        }}
                      >
                        {row.status === "disabled" ? "فعال‌سازی" : "غیرفعال"}
                      </Button>
                      <Button size="small" onClick={() => makeToken.mutate(row)}>
                        توکن فعال‌سازی
                      </Button>
                      <Button size="small" onClick={() => setRolesTarget(row)}>
                        نقش‌ها/سازمان
                      </Button>
                      <Button size="small" color="warning" onClick={() => setPwTarget(row)}>
                        بازنشانی رمز
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={data?.total ?? 0}
          page={page}
          onPageChange={(_, p) => setPage(p)}
          rowsPerPage={10}
          rowsPerPageOptions={[10]}
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
        />
      </TableContainer>

      <CreateUserDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onError={setError}
      />

      {/* فاز ۵۲: ویرایش نقش‌های کاربر (نقش‌های سیستمی + سفارشی از /rbac/roles) */}
      <UserRolesDialog
        target={rolesTarget}
        onClose={() => setRolesTarget(null)}
        onError={setError}
      />

      {/* فاز ۵۲: بازنشانی رمز توسط مدیر (تعیین رمز جدید همان‌جا) */}
      <ResetPasswordDialog
        target={pwTarget}
        onClose={() => setPwTarget(null)}
        onDone={(username, password) => {
          setPwTarget(null);
          setPwResult(`${username}:${password}`);
        }}
        onError={setError}
      />

      <Dialog open={pwResult !== null} onClose={() => setPwResult(null)} maxWidth="sm" fullWidth>
        <DialogTitle>رمز جدید ثبت شد</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            این رمز فقط یک بار نمایش داده می‌شود؛ آن را به کاربر اعلام کنید.
          </Alert>
          <TextField fullWidth multiline value={pwResult ?? ""} InputProps={{ readOnly: true }} />
          <Button sx={{ mt: 1 }} onClick={() => pwResult && navigator.clipboard.writeText(pwResult)}>
            کپی
          </Button>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPwResult(null)}>بستن</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={tokenInfo !== null} onClose={() => setTokenInfo(null)} maxWidth="sm" fullWidth>
        <DialogTitle>توکن فعال‌سازی — {tokenInfo?.username}</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            این توکن فقط یک بار نمایش داده می‌شود. آن را به روش مورد تأیید سازمان برای کاربر ارسال کنید.
            انقضا: {tokenInfo ? formatJalaliDateTime(tokenInfo.expires_at) : ""}
          </Alert>
          <TextField
            fullWidth
            multiline
            value={tokenInfo?.token ?? ""}
            InputProps={{ readOnly: true }}
          />
          <Button
            sx={{ mt: 1 }}
            onClick={() => tokenInfo && navigator.clipboard.writeText(tokenInfo.token)}
          >
            کپی توکن
          </Button>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTokenInfo(null)}>بستن</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

function CreateUserDialog({
  open,
  onClose,
  onError,
}: {
  open: boolean;
  onClose: () => void;
  onError: (msg: string) => void;
}) {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [organizationId, setOrganizationId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  // فاز ۵۲: نقش‌ها از سرور (سیستمی + سفارشی) — نه لیست ثابت
  const rolesQ = useQuery({ queryKey: ["rbac-roles"], queryFn: fetchRoles });
  const roleItems = (rolesQ.data ?? []).map((r) => ({ code: r.code, title: r.title }));
  // فاز ۷۴: انتخاب سازمان برای ایزولاسیون دادهٔ سازمانی
  const orgsQ = useQuery({ queryKey: ["organizations"], queryFn: fetchOrganizations });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setBusy(true);
    try {
      await createUser({
        username: username.trim(),
        display_name: displayName.trim(),
        email: email.trim() || undefined,
        mobile: mobile.trim() || undefined,
        roles,
        organization_id: organizationId || undefined,
      });
      await queryClient.invalidateQueries({ queryKey: ["users"] });
      setUsername("");
      setDisplayName("");
      setEmail("");
      setMobile("");
      setRoles([]);
      setOrganizationId("");
      onClose();
    } catch (err) {
      setFormError(errDetail(err));
      onError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={submit}>
        <DialogTitle>ایجاد حساب جدید</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            حساب جدید «در انتظار فعال‌سازی» ایجاد می‌شود؛ رمز عبور در این مرحله تعیین نمی‌شود.
          </Typography>
          {formError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {formError}
            </Alert>
          )}
          <Stack spacing={2} mt={1}>
            <TextField label="نام کاربری" value={username} onChange={(e) => setUsername(e.target.value)} required />
            <TextField label="نام نمایشی" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />
            <TextField label="ایمیل (اختیاری)" value={email} onChange={(e) => setEmail(e.target.value)} />
            <TextField label="موبایل (اختیاری)" value={mobile} onChange={(e) => setMobile(e.target.value)} />
            {/* فاز ۷۴: سازمان کاربر — هر منتسب‌شده فقط داده‌های سازمان خودش را می‌بیند */}
            <TextField
              select
              label="سازمان (اختیاری)"
              value={organizationId}
              onChange={(e) => setOrganizationId(e.target.value)}
              helperText="اگر انتخاب شود، کاربر فقط اطلاعات همین سازمان را می‌بیند"
            >
              <MenuItem value="">— بدون سازمان (همهٔ داده‌ها) —</MenuItem>
              {(orgsQ.data ?? []).map((o) => (
                <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>
              ))}
            </TextField>
            <Box>
              <Typography variant="body2" sx={{ mb: 1 }}>
                نقش‌ها:
              </Typography>
              {(roleItems.length ? roleItems : ROLE_OPTIONS).map((r) => (
                <FormControlLabel
                  key={r.code}
                  control={
                    <Checkbox
                      checked={roles.includes(r.code)}
                      onChange={(e) =>
                        setRoles((prev) =>
                          e.target.checked ? [...prev, r.code] : prev.filter((c) => c !== r.code)
                        )
                      }
                    />
                  }
                  label={r.title}
                />
              ))}
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>انصراف</Button>
          <Button type="submit" variant="contained" disabled={busy}>
            {busy ? "در حال ثبت…" : "ایجاد"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// فاز ۵۲ - ویرایش نقش‌های کاربر: نقش‌های سیستمی + سفارشی از /rbac/roles
// ---------------------------------------------------------------------------
function UserRolesDialog({
  target,
  onClose,
  onError,
}: {
  target: UserRow | null;
  onClose: () => void;
  onError: (msg: string) => void;
}) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const [initialized, setInitialized] = useState<string | null>(null);
  // فاز ۷۴: انتساب سازمان در همین دیالوگ
  const [orgId, setOrgId] = useState<string>("");

  const rolesQ = useQuery({ queryKey: ["rbac-roles"], queryFn: fetchRoles, enabled: target !== null });
  const orgsQ = useQuery({ queryKey: ["organizations"], queryFn: fetchOrganizations, enabled: target !== null });

  if (target && initialized !== target.id) {
    setInitialized(target.id);
    setSelected(target.roles);
    setOrgId(target.organization_id ?? "");
  }

  const save = useMutation({
    mutationFn: async () => {
      await setUserRoles(target!.id, selected);
      // فاز ۷۴: تغییر سازمان فقط وقتی لازم است که مقدار عوض شده باشد
      if (orgId !== (target!.organization_id ?? "")) {
        await updateUserOrganization(target!.id, orgId || null);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["rbac-roles"] });
      onClose();
      setInitialized(null);
    },
    onError: (e) => onError(errDetail(e)),
  });

  const roleItems = rolesQ.data ?? [];

  return (
    <Dialog open={target !== null} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>نقش‌ها و سازمان — {target?.display_name}</DialogTitle>
      <DialogContent>
        {roleItems.map((r) => (
          <FormControlLabel
            key={r.code}
            control={
              <Checkbox
                checked={selected.includes(r.code)}
                onChange={(e) =>
                  setSelected((prev) =>
                    e.target.checked ? [...prev, r.code] : prev.filter((c) => c !== r.code)
                  )
                }
              />
            }
            label={`${r.title} (${r.code})`}
          />
        ))}
        {roleItems.length === 0 && <Typography variant="body2">در حال دریافت نقش‌ها…</Typography>}

        {/* فاز ۷۴: سازمان کاربر — هر منتسب‌شده فقط داده‌های سازمان خودش را می‌بیند */}
        <TextField
          select
          fullWidth
          size="small"
          sx={{ mt: 2 }}
          label="سازمان کاربر"
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
          helperText="خالی = همهٔ داده‌ها؛ با انتخاب سازمان، کاربر فقط اطلاعات همان سازمان را می‌بیند"
        >
          <MenuItem value="">— بدون سازمان (همهٔ داده‌ها) —</MenuItem>
          {(orgsQ.data ?? []).map((o) => (
            <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>
          ))}
        </TextField>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={() => {
            onClose();
            setInitialized(null);
          }}
        >
          انصراف
        </Button>
        <Button variant="contained" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "در حال ذخیره…" : "ذخیره"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// فاز ۵۲ - بازنشانی رمز عبور کاربر توسط مدیر (تعیین رمز جدید در همین دیالوگ)
// ---------------------------------------------------------------------------
function ResetPasswordDialog({
  target,
  onClose,
  onDone,
  onError,
}: {
  target: UserRow | null;
  onClose: () => void;
  onDone: (username: string, password: string) => void;
  onError: (msg: string) => void;
}) {
  const [newPw, setNewPw] = useState("");
  const [mustChange, setMustChange] = useState(false);

  const reset = useMutation({
    mutationFn: () => resetUserPassword(target!.id, newPw, mustChange),
    onSuccess: () => {
      onDone(target!.username, newPw);
      setNewPw("");
      setMustChange(false);
    },
    onError: (e) => onError(errDetail(e)),
  });

  return (
    <Dialog open={target !== null} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>بازنشانی رمز — {target?.username}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          <TextField
            label="رمز عبور جدید (حداقل ۸ نویسه)"
            type="text"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
          />
          <FormControlLabel
            control={<Checkbox checked={mustChange} onChange={(e) => setMustChange(e.target.checked)} />}
            label="کاربر در ورود بعدی مجبور به تغییر رمز شود"
          />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button
          variant="contained"
          color="warning"
          disabled={newPw.length < 8 || reset.isPending}
          onClick={() => reset.mutate()}
        >
          {reset.isPending ? "در حال ثبت…" : "بازنشانی"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
