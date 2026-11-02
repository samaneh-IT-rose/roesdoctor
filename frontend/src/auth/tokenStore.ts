// بند ۴.۲ سند: Access Token فقط در حافظه برنامه نگهداری می‌شود (نه localStorage)
export const tokenStore: { accessToken: string | null } = { accessToken: null };

// ---------------------------------------------------------------------------
// فاز ۷۱ — نشانهٔ «کاربر قبلاً وارد شده است» (فقط یک پرچم بی‌محتوا در
// localStorage؛ هیچ توکنی اینجا ذخیره نمی‌شود). هدف: حذف خطای 401 بی‌مصرف در
// کنسول مرورگر — وقتی کاربر اصلاً وارد نشده، /auth/me اصلاً صدا زده نمی‌شود.
// پرچم با ورود ست، با خروج یا 401 نهایی پاک می‌شود.
// ---------------------------------------------------------------------------
const SESSION_FLAG_KEY = "rosepsy.session.active";

export const sessionFlag = {
  set(): void {
    try {
      localStorage.setItem(SESSION_FLAG_KEY, "1");
    } catch {
      /* حالت خصوصی مرورگر — بی‌اهمیت */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(SESSION_FLAG_KEY);
    } catch {
      /* بی‌اهمیت */
    }
  },
  has(): boolean {
    try {
      return localStorage.getItem(SESSION_FLAG_KEY) === "1";
    } catch {
      return false;
    }
  },
};
