import { Box, CircularProgress, Typography } from "@mui/material";
import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { NAV_GROUPS } from "../components/Layout";

// فاز ۷۴ — نگاشت مسیر → کلید منو (از همان نقشهٔ منوی پنل) برای گیت ماتریس‌آگاه
const MENU_PREFIXES: Array<{ prefix: string; menuKey: string }> = NAV_GROUPS.flatMap((g) =>
  g.items
    .filter((it) => !!it.menuKey)
    .map((it) => ({ prefix: it.path, menuKey: it.menuKey as string }))
).sort((a, b) => b.prefix.length - a.prefix.length);

function resolveMenuKey(pathname: string): string | null {
  for (const { prefix, menuKey } of MENU_PREFIXES) {
    if (pathname === prefix || pathname.startsWith(prefix + "/")) return menuKey;
  }
  return null;
}

export default function ProtectedRoute({
  children,
  roles,
}: {
  children: ReactNode;
  roles?: string[];
}) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="50vh">
        <CircularProgress />
      </Box>
    );
  }
  if (!user) return <Navigate to="/login" replace />;

  if (roles && !roles.some((r) => user.roles.includes(r))) {
    // فاز ۷۴ — ماتریس منوها بر نقش‌های ثابت اولویت دارد: هر مجازی که مدیر
    // سامانه در «نقش‌ها و دسترسی‌ها» به نقش کاربر داده باشد، همین‌جا صفحه
    // باز می‌شود (هم‌راستا با دروازهٔ API) و دیگر «دسترسی مجاز نیست» با
    // وجود مجوز ماتریس دیده نمی‌شود.
    const menuKey = resolveMenuKey(location.pathname);
    const level = menuKey ? user.menu_permissions?.[menuKey] : undefined;
    if (level) return <>{children}</>;
    return (
      <Box p={4}>
        <Typography color="error">دسترسی مجاز نیست.</Typography>
      </Box>
    );
  }
  return <>{children}</>;
}
