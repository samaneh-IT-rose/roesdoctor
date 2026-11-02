import { useMemo, useState } from "react";
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
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { errDetail } from "../api/client";
import {
  DATA_SCOPE_OPTIONS,
  MENU_LEVEL_OPTIONS,
  createRole,
  deleteRole,
  fetchMenuCatalog,
  fetchPermissionCatalog,
  fetchRoleMenus,
  fetchRoles,
  saveRoleMenus,
  saveRolePermissions,
  type MenuLevel,
  type RoleMenus,
} from "../api/rbac";

/**
 * فاز ۵۲ + ۷۱ - صفحهٔ «نقش‌ها و دسترسی‌ها»:
 * - تب «منوها و زیرمنوها»: ماتریس سه‌سطحی (هیچ/دیدن/فقط خواندن/ویرایش) برای
 *   همهٔ منوها و زیرمنوهای پنل — هر سلول برای هر نقش قابل تغییر است؛
 * - تب «دسترسی‌های عملیاتی»: ماتریس تیک‌های ریزدانهٔ عملیاتی (فاز ۵۲)؛
 * - «سطح دسترسی روی داده» نقش با همان رابط تیک/لیست انتخاب می‌شود؛
 * - اعمال عملی: سمت سرور (MenuAccessMiddleware + require_perm) و سمت پنل
 *   (فیلتر منوی Layout با menu_permissions کاربر).
 */

export default function RolesPermissionsPage() {
  const queryClient = useQueryClient();
  const [selectedCode, setSelectedCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [tab, setTab] = useState(0);

  const catalog = useQuery({ queryKey: ["rbac-catalog"], queryFn: fetchPermissionCatalog });
  const roles = useQuery({ queryKey: ["rbac-roles"], queryFn: fetchRoles });

  const selected = useMemo(() => {
    const items = roles.data ?? [];
    if (!items.length) return null;
    return items.find((r) => r.code === selectedCode) ?? items[0];
  }, [roles.data, selectedCode]);

  const save = useMutation({
    mutationFn: (p: { code: string; title: string; data_scope: string; permissions: string[] }) =>
      saveRolePermissions(p.code, {
        title: p.title,
        data_scope: p.data_scope,
        permissions: p.permissions,
      }),
    onSuccess: (_r, p) => {
      setSuccess(`ماتریس دسترسی «${p.title}» ذخیره شد`);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["rbac-roles"] });
    },
    onError: (e) => {
      setError(errDetail(e));
      setSuccess(null);
    },
  });

  const removeRole = useMutation({
    mutationFn: deleteRole,
    onSuccess: () => {
      setSuccess("نقش حذف شد");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["rbac-roles"] });
    },
    onError: (e) => {
      setError(errDetail(e));
      setSuccess(null);
    },
  });

  const saveMenus = useMutation({
    mutationFn: (p: { code: string; menus: Record<string, MenuLevel | null> }) =>
      saveRoleMenus(p.code, p.menus),
    onSuccess: (r: RoleMenus) => {
      setSuccess("ماتریس منوها ذخیره شد و از همین لحظه اعمال می‌شود");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["rbac-role-menus", r.role_code] });
    },
    onError: (e) => {
      setError(errDetail(e));
      setSuccess(null);
    },
  });

  if (catalog.isLoading || roles.isLoading) {
    return <CircularProgress sx={{ mx: "auto", display: "block", mt: 8 }} />;
  }

  return (
    <Stack spacing={2}>
      <Box display="flex" justifyContent="space-between" alignItems="center" gap={2}>
        <Typography variant="h6" fontWeight={700}>
          نقش‌ها و دسترسی‌ها
        </Typography>
        <Button variant="contained" onClick={() => setCreateOpen(true)}>
          نقش جدید
        </Button>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" onClose={() => setSuccess(null)}>{success}</Alert>}

      <Tabs value={tab} onChange={(_e, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tab label="منوها و زیرمنوها (دیدن / خواندن / ویرایش)" />
        <Tab label="دسترسی‌های عملیاتی" />
      </Tabs>

      <Stack direction="row" spacing={2} alignItems="flex-start">
        {/* ستون نقش‌ها */}
        <Paper sx={{ width: 320, flexShrink: 0 }} variant="outlined">
          <Box sx={{ p: 1.5, borderBottom: 1, borderColor: "divider" }}>
            <Typography variant="subtitle2" color="text.secondary">
              نقش‌ها
            </Typography>
          </Box>
          <Box>
            {(roles.data ?? []).map((r) => (
              <Box
                key={r.code}
                onClick={() => setSelectedCode(r.code)}
                sx={{
                  px: 1.5,
                  py: 1.2,
                  cursor: "pointer",
                  bgcolor: selected?.code === r.code ? "action.selected" : "transparent",
                  "&:hover": { bgcolor: "action.hover" },
                }}
              >
                <Typography variant="body2" fontWeight={600}>
                  {r.title}
                </Typography>
                <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} flexWrap="wrap" useFlexGap>
                  <Chip size="small" variant="outlined" label={r.code} sx={{ fontSize: 11 }} />
                  <Chip
                    size="small"
                    label={r.is_system ? "سیستمی" : "سفارشی"}
                    color={r.is_system ? "primary" : "default"}
                    sx={{ fontSize: 11 }}
                  />
                  <Chip size="small" variant="outlined" label={`${r.member_count ?? 0} کاربر`} sx={{ fontSize: 11 }} />
                </Stack>
              </Box>
            ))}
          </Box>
        </Paper>

        {/* ماتریس دسترسی */}
        {selected && tab === 0 && (
          <MenuMatrix
            key={`menus-${selected.code}`}
            role={selected}
            saving={saveMenus.isPending}
            onSave={(menus) => saveMenus.mutate({ code: selected.code, menus })}
          />
        )}
        {selected && tab === 1 && (
          <PermissionMatrix
            key={selected.code}
            role={selected}
            sections={catalog.data ?? []}
            saving={save.isPending}
            onSave={(dataScope, permissions) =>
              save.mutate({
                code: selected.code,
                title: selected.title,
                data_scope: dataScope,
                permissions,
              })
            }
            onDelete={
              selected.is_system
                ? undefined
                : () => {
                    if (window.confirm(`حذف نقش «${selected.title}»؟`)) removeRole.mutate(selected.code);
                  }
            }
          />
        )}
      </Stack>

      <CreateRoleDialog
        open={createOpen}
        existingCodes={(roles.data ?? []).map((r) => r.code)}
        onClose={() => setCreateOpen(false)}
        onError={setError}
        onCreated={(code) => {
          setCreateOpen(false);
          setSelectedCode(code);
          queryClient.invalidateQueries({ queryKey: ["rbac-roles"] });
        }}
      />
    </Stack>
  );
}


function MenuMatrix({
  role,
  saving,
  onSave,
}: {
  role: { code: string; title: string; is_system: boolean };
  saving: boolean;
  onSave: (menus: Record<string, MenuLevel | null>) => void;
}) {
  // فاز ۷۱ — ماتریس «منو × نقش» با چهار حالت: هیچ / دیدن / فقط خواندن / ویرایش
  const catalog = useQuery({ queryKey: ["rbac-menu-catalog"], queryFn: fetchMenuCatalog });
  const current = useQuery({
    queryKey: ["rbac-role-menus", role.code],
    queryFn: () => fetchRoleMenus(role.code),
  });

  // فاز ۷۱: مقدار null صریح = «هیچ» (حذف ردیف سمت سرور) — کلیدِ غایب یعنی
  // دست‌نخورده از مقدار فعلی؛ تا مدیر بتواند سطح هر منو را واقعاً پس بگیرد.
  const [levels, setLevels] = useState<Record<string, MenuLevel | null> | null>(null);
  const menus: Record<string, MenuLevel | null> = levels ?? current.data?.menus ?? {};
  const locked = current.data?.locked ?? role.code === "SYSTEM_ADMIN";

  const setLevel = (key: string, level: MenuLevel | null) => {
    setLevels((prev) => {
      const base = { ...(prev ?? current.data?.menus ?? {}) } as Record<string, MenuLevel | null>;
      base[key] = level; // null هم ثبت می‌شود تا در PUT «هیچ» اعمال شود
      return base;
    });
  };

  const setGroup = (keys: string[], level: MenuLevel | null) => {
    setLevels((prev) => {
      const base = { ...(prev ?? current.data?.menus ?? {}) } as Record<string, MenuLevel | null>;
      keys.forEach((k) => {
        base[k] = level;
      });
      return base;
    });
  };

  if (catalog.isLoading || current.isLoading) {
    return <CircularProgress sx={{ mx: "auto", display: "block", mt: 6 }} />;
  }

  const groups = catalog.data?.groups ?? [];
  const grantedCount = Object.values(menus).filter((lv) => !!lv).length;

  return (
    <Paper variant="outlined" sx={{ flex: 1, minWidth: 0 }}>
      <Box sx={{ p: 1.5, borderBottom: 1, borderColor: "divider", display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap" }}>
        <Typography variant="subtitle1" fontWeight={700}>
          منوهای «{role.title}»
        </Typography>
        <Chip label={role.code} size="small" variant="outlined" />
        <Chip size="small" color="primary" variant="outlined" label={`${grantedCount} منوی فعال`} />
        <Box sx={{ flex: 1 }} />
        <Button
          variant="contained"
          disabled={saving || locked}
          onClick={() => onSave(menus)}
        >
          {saving ? "در حال ذخیره…" : "ذخیرهٔ ماتریس منوها"}
        </Button>
      </Box>

      {locked ? (
        <Alert severity="info" sx={{ m: 1.5 }}>
          مدیر سامانه (SYSTEM_ADMIN) همیشه به همهٔ منوها با سطح «ویرایش» دسترسی دارد؛
          این ماتریس برای اطمینان از قفل‌نشدن سامانه قابل تغییر نیست.
        </Alert>
      ) : (
        <Alert severity="info" sx={{ m: 1.5 }}>
          <b>دیدن</b> = منو نمایش داده می‌شود و فهرست/صفحهٔ اصلی بخش باز است؛{" "}
          <b>فقط خواندن</b> = جزئیات رکوردها هم قابل مشاهده است ولی تغییری نمی‌تواند بدهد؛{" "}
          <b>ویرایش</b> = ثبت/ویرایش/حذف کامل در آن بخش. «هیچ» یعنی منو پنهان و
          مسیرهای API آن بخش روی سرور هم مسدود است. تغییرها بعد از ذخیره از
          ورودِ بعدی کاربران اعمال می‌شود.
        </Alert>
      )}

      <TableContainer sx={{ maxHeight: "58vh" }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: 260 }}>منو / زیرمنو</TableCell>
              <TableCell align="center" sx={{ width: 320 }}>
                سطح دسترسی (هیچ / دیدن / فقط خواندن / ویرایش)
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {groups.map((g) => {
              const keys = g.items.map((it) => it.key);
              const allSame = keys.every((k) => menus[k] === menus[keys[0]]);
              return (
                <FragmentRow
                  key={g.key}
                  groupTitle={g.title}
                  keys={keys}
                  allSame={allSame && keys.length > 0}
                  groupLevel={allSame ? menus[keys[0]] ?? null : null}
                  locked={locked}
                  onGroup={(lv) => setGroup(keys, lv)}
                  rows={g.items.map((it) => ({
                    key: it.key,
                    title: it.title,
                    path: it.path,
                    selfService: it.self_service,
                    level: menus[it.key],
                  }))}
                  onRow={setLevel}
                />
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      <Box sx={{ p: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          بخش‌های دارای نشان «شخصی» داده‌های خودِ کاربر است (کیف پول، گفتگو، پشتیبانی و…)؛
          برای این بخش‌ها ماتریس فقط «نمایش منو» را کنترل می‌کند و دسترسی به داده‌ها با
          مالکیت رکورد تضمین می‌شود.
        </Typography>
      </Box>
    </Paper>
  );
}

function FragmentRow({
  groupTitle,
  keys,
  allSame,
  groupLevel,
  locked,
  onGroup,
  rows,
  onRow,
}: {
  groupTitle: string;
  keys: string[];
  allSame: boolean;
  groupLevel: MenuLevel | null;
  locked: boolean;
  onGroup: (level: MenuLevel | null) => void;
  rows: { key: string; title: string; path: string; selfService: boolean; level: MenuLevel | null }[];
  onRow: (key: string, level: MenuLevel | null) => void;
}) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <TableRow sx={{ bgcolor: "action.hover" }}>
        <TableCell colSpan={2}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Button size="small" onClick={() => setOpen((o) => !o)} sx={{ minWidth: 0, px: 1 }}>
              {open ? "▾" : "▸"} {groupTitle}
            </Button>
            <Typography variant="caption" color="text.secondary">
              ({keys.length} زیرمنو)
            </Typography>
            <Box sx={{ flex: 1 }} />
            <Typography variant="caption" color="text.secondary">
              اعمال روی کل منو:
            </Typography>
            <LevelPicker
              value={allSame ? groupLevel ?? null : null}
              indeterminate={!allSame}
              disabled={locked}
              onChange={(lv) => onGroup(lv)}
            />
          </Stack>
        </TableCell>
      </TableRow>
      {open &&
        rows.map((r) => (
          <TableRow key={r.key} hover>
            <TableCell>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="body2" fontWeight={600} sx={{ pr: 2 }}>
                  {r.title}
                </Typography>
                <Chip size="small" variant="outlined" sx={{ fontSize: 10, height: 18 }} label={r.path} />
                {r.selfService && (
                  <Tooltip title="داده‌های شخصی خود کاربر — ماتریس فقط نمایش منو را کنترل می‌کند">
                    <Chip size="small" sx={{ fontSize: 10, height: 18 }} color="default" label="شخصی" />
                  </Tooltip>
                )}
              </Stack>
            </TableCell>
            <TableCell align="center">
              <LevelPicker value={r.level ?? null} disabled={locked} onChange={(lv) => onRow(r.key, lv)} />
            </TableCell>
          </TableRow>
        ))}
    </>
  );
}

function LevelPicker({
  value,
  disabled,
  onChange,
  indeterminate = false,
}: {
  value: MenuLevel | null;
  disabled?: boolean;
  onChange: (level: MenuLevel | null) => void;
  indeterminate?: boolean;
}) {
  return (
    <ToggleButtonGroup
      exclusive
      size="small"
      value={value ?? ""}
      disabled={disabled}
      onChange={(_e, v: string | null) => onChange(v === "" || v === null ? null : (v as MenuLevel))}
      sx={{ "& .MuiToggleButton-root": { px: 1.2, py: 0.2, fontSize: 12 } }}
    >
      {MENU_LEVEL_OPTIONS.map((o) => (
        <ToggleButton key={o.value} value={o.value === "none" ? "" : o.value} title={o.hint}>
          {o.value === "none" && indeterminate ? "–" : o.title}
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}

function PermissionMatrix({
  role,
  sections,
  saving,
  onSave,
  onDelete,
}: {
  role: { code: string; title: string; data_scope: string; permissions: string[]; is_system: boolean };
  sections: { section: string; permissions: { code: string; title: string }[] }[];
  saving: boolean;
  onSave: (dataScope: string, permissions: string[]) => void;
  onDelete?: () => void;
}) {
  const [checked, setChecked] = useState<Set<string>>(new Set(role.permissions));
  const [scope, setScope] = useState<string>(role.data_scope);
  const scopeMeta = DATA_SCOPE_OPTIONS.find((o) => o.value === scope);

  const toggle = (code: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const toggleSection = (codes: string[], on: boolean) => {
    setChecked((prev) => {
      const next = new Set(prev);
      codes.forEach((c) => (on ? next.add(c) : next.delete(c)));
      return next;
    });
  };

  return (
    <Paper variant="outlined" sx={{ flex: 1, minWidth: 0 }}>
      <Box sx={{ p: 1.5, borderBottom: 1, borderColor: "divider", display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap" }}>
        <Typography variant="subtitle1" fontWeight={700}>
          {role.title}
        </Typography>
        <Chip label={role.code} size="small" variant="outlined" />
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel>سطح دسترسی روی داده</InputLabel>
          <Select value={scope} label="سطح دسترسی روی داده" onChange={(e) => setScope(e.target.value)}>
            {DATA_SCOPE_OPTIONS.map((o) => (
              <MenuItem key={o.value} value={o.value}>
                {o.title}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Box sx={{ flex: 1 }} />
        {onDelete && <Button color="error" onClick={onDelete}>حذف نقش</Button>}
        <Button variant="contained" disabled={saving} onClick={() => onSave(scope, Array.from(checked))}>
          {saving ? "در حال ذخیره…" : "ذخیرهٔ ماتریس"}
        </Button>
      </Box>

      {scopeMeta && (
        <Alert severity="info" sx={{ mx: 1.5, mt: 1.5 }}>
          سطح داده: {scopeMeta.title} — {scopeMeta.hint}
        </Alert>
      )}

      <TableContainer sx={{ maxHeight: "60vh" }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ width: 220 }}>بخش</TableCell>
              {sections[0]?.permissions.map((_, i) => (
                <TableCell key={i} align="center">
                  <Typography variant="caption" sx={{ fontSize: 11 }}>
                    {i === 0 ? "مجوزها" : ""}
                  </Typography>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {sections.map((sec) => {
              const allOn = sec.permissions.every((p) => checked.has(p.code));
              const someOn = sec.permissions.some((p) => checked.has(p.code));
              return (
                <TableRow key={sec.section} hover>
                  <TableCell>
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Checkbox
                        size="small"
                        checked={allOn}
                        indeterminate={!allOn && someOn}
                        onChange={(e) => toggleSection(sec.permissions.map((p) => p.code), e.target.checked)}
                        title="انتخاب/لغو کل بخش"
                      />
                      <Typography variant="body2" fontWeight={600}>
                        {sec.section}
                      </Typography>
                    </Stack>
                  </TableCell>
                  {sec.permissions.map((p) => (
                    <TableCell key={p.code} align="center">
                      <Tooltip title={p.title} arrow>
                        <Checkbox size="small" checked={checked.has(p.code)} onChange={() => toggle(p.code)} />
                      </Tooltip>
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      <Box sx={{ p: 1.5 }}>
        <Typography variant="caption" color="text.secondary">
          هر ستون یک دسترسی است (عنوان با نگه‌داشتن نشانگر نمایش داده می‌شود)؛ تیک سرِ بخش = انتخاب همهٔ دسترسی‌های آن بخش.
          {role.is_system ? " — نقش سیستمی قابل حذف نیست ولی ماتریسش قابل ویرایش است." : ""}
        </Typography>
      </Box>
    </Paper>
  );
}

function CreateRoleDialog({
  open,
  existingCodes,
  onClose,
  onError,
  onCreated,
}: {
  open: boolean;
  existingCodes: string[];
  onClose: () => void;
  onError: (msg: string) => void;
  onCreated: (code: string) => void;
}) {
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [scope, setScope] = useState("assigned");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async () => {
    setFormError(null);
    setBusy(true);
    try {
      await createRole(code.trim().toUpperCase(), {
        title: title.trim(),
        data_scope: scope,
        permissions: [],
      });
      onCreated(code.trim().toUpperCase());
      setCode("");
      setTitle("");
      setScope("assigned");
    } catch (e) {
      setFormError(errDetail(e));
      onError(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const duplicate = existingCodes.includes(code.trim().toUpperCase());
  const codeValid = /^[A-Z][A-Z0-9_]{2,49}$/.test(code.trim().toUpperCase());

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>ساخت نقش جدید</DialogTitle>
      <DialogContent>
        {formError && <Alert severity="error" sx={{ mb: 2, mt: 1 }}>{formError}</Alert>}
        <Stack spacing={2} mt={1}>
          <TextField
            label="کد نقش (لاتین، مثل HR_MANAGER)"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            error={code.length > 0 && (!codeValid || duplicate)}
            helperText={
              code.length > 0 && duplicate
                ? "این کد قبلاً ثبت شده است"
                : "۳ تا ۵۰ نویسه؛ حروف بزرگ/عدد/زیرخط"
            }
          />
          <TextField label="عنوان نقش (فارسی)" value={title} onChange={(e) => setTitle(e.target.value)} />
          <FormControl size="small">
            <InputLabel>سطح دسترسی روی داده</InputLabel>
            <Select value={scope} label="سطح دسترسی روی داده" onChange={(e) => setScope(e.target.value)}>
              {DATA_SCOPE_OPTIONS.map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.title}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Alert severity="info">
            پس از ساخت، ماتریس دسترسی نقش را در همین صفحه تیک بزنید و ذخیره کنید؛ سپس نقش را از صفحهٔ «مدیریت حساب‌ها» به کاربران اختصاص دهید.
          </Alert>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" onClick={submit} disabled={busy || !codeValid || duplicate || !title.trim()}>
          {busy ? "در حال ساخت…" : "ساخت نقش"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
