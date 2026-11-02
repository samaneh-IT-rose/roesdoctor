import {
  Alert, Box, Button, Card, CardContent, Divider, Link, Stack, Tab, Tabs, TextField, Typography,
} from "@mui/material";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errDetail } from "../api/client";
import { requestOtp } from "../api/auth";
import type { OtpRequestResponse } from "../api/auth";

// ورود یکپارچه (SSO) با رز هاب — Rose Hub
// فاز ۷۲: مقصد دکمهٔ SSO صفحهٔ ورود خودِ درگاه رز هاب روی نشانی عمومی
// (130.185.73.157:8082) است با next= مسیر launch؛ رز هاب پس از ورود، خودش
// به /api/sso/launch برمی‌گردد و توکن را به رز سای می‌فرستد. مقصد قبلی
// (launch مستقیم) برای کاربرِ واردنشده در رز هاب 307 به localhost:8082
// می‌داد که در مرورگر کاربر باز نمی‌شود — همان «SSO وارد برنامه نمی‌شود».
const ROSE_HUB_PORTAL_URL = "http://130.185.73.157:8082";
const ROSE_HUB_LAUNCH_URL =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_ROSE_HUB_LAUNCH_URL ||
  "http://130.185.73.157:8082/login?next=%2Fapi%2Fsso%2Flaunch%3FclientId%3Drose-psy-5c3f9b";

type LoginMode = "password" | "otp";

export default function LoginPage() {
  const { login, loginOtp } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<LoginMode>("password");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  // فاز ۶۴: ورود دو عاملی پیامکی
  const [mobile, setMobile] = useState("");
  const [code, setCode] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpInfo, setOtpInfo] = useState<OtpRequestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [otpBusy, setOtpBusy] = useState(false);

  const afterLogin = (mustChange: boolean) => {
    if (mustChange) navigate("/change-password");
    else navigate("/");
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me = await login(username.trim(), password);
      afterLogin(me.must_change_password);
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setBusy(false);
    }
  };

  const sendCode = async () => {
    setError(null);
    setOtpBusy(true);
    try {
      const res = await requestOtp(mobile.trim());
      setOtpInfo(res);
      setOtpSent(true);
      setCode("");
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setOtpBusy(false);
    }
  };

  const onOtpVerify = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setOtpBusy(true);
    try {
      const me = await loginOtp(mobile.trim(), code.trim());
      afterLogin(me.must_change_password);
    } catch (err) {
      setError(errDetail(err));
    } finally {
      setOtpBusy(false);
    }
  };

  return (
    <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh" bgcolor="grey.100">
      <Card sx={{ minWidth: 380 }}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h5" fontWeight={700} gutterBottom>
            Rosepsy
          </Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            ورود به سامانه مشاوره روان‌شناختی سازمانی
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
          <Tabs
            value={mode}
            onChange={(_, v: LoginMode) => { setMode(v); setError(null); }}
            variant="fullWidth"
            sx={{ mt: 2 }}
          >
            <Tab value="password" label="نام کاربری و رمز عبور" />
            <Tab value="otp" label="کد پیامکی" />
          </Tabs>

          {mode === "password" && (
            <form onSubmit={onSubmit}>
              <Stack spacing={2} mt={2}>
                <TextField
                  label="نام کاربری (کد ملی)"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoFocus
                  required
                />
                <TextField
                  label="رمز عبور"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <Button type="submit" variant="contained" disabled={busy}>
                  {busy ? "در حال ورود…" : "ورود"}
                </Button>
              </Stack>
            </form>
          )}

          {mode === "otp" && (
            <form onSubmit={onOtpVerify}>
              <Stack spacing={2} mt={2}>
                <Stack direction="row" spacing={1} alignItems="flex-start">
                  <TextField
                    label="شماره موبایل"
                    placeholder="09121234567"
                    value={mobile}
                    onChange={(e) => setMobile(e.target.value)}
                    slotProps={{ htmlInput: { dir: "ltr" } }}
                    required
                    fullWidth
                  />
                  <Button variant="outlined" onClick={sendCode} disabled={otpBusy || mobile.trim().length < 10} sx={{ mt: 0.5, whiteSpace: "nowrap" }}>
                    ارسال کد
                  </Button>
                </Stack>
                {otpSent && otpInfo?.dev_code && (
                  <Alert severity="info">
                    تا اتصال درگاه پیامک، کد به‌صورت آزمایشی نمایش داده می‌شود:{" "}
                    <strong dir="ltr">{otpInfo.dev_code}</strong>
                    <Typography variant="caption" display="block" color="text.secondary">
                      اعتبار: {Math.round(otpInfo.expires_in / 60)} دقیقه
                    </Typography>
                  </Alert>
                )}
                {otpSent && (
                  <TextField
                    label="کد یک‌بارمصرف"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    slotProps={{ htmlInput: { dir: "ltr", maxLength: 8 } }}
                    required
                    autoFocus
                  />
                )}
                <Button type="submit" variant="contained" disabled={otpBusy || !otpSent || code.trim().length < 4}>
                  {otpBusy ? "در حال بررسی…" : "ورود با کد"}
                </Button>
              </Stack>
            </form>
          )}

          <Divider sx={{ mt: 3 }}>
            <Typography variant="caption" color="text.secondary">یا</Typography>
          </Divider>
          <Button
            variant="outlined"
            color="secondary"
            fullWidth
            sx={{ mt: 2 }}
            onClick={() => { window.location.href = ROSE_HUB_LAUNCH_URL; }}
          >
            ورود یکپارچه با رز هاب (SSO)
          </Button>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block", textAlign: "center" }}>
            درگاه رز هاب:{" "}
            <Link
              href={ROSE_HUB_PORTAL_URL}
              target="_blank"
              rel="noopener noreferrer"
              underline="hover"
              sx={{ direction: "ltr", display: "inline-block" }}
            >
              130.185.73.157:8082
            </Link>
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
