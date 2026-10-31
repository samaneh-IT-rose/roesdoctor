from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rosepsy"
    app_version: str = "0.54.0"
    api_prefix: str = "/api/v1"
    environment: str = "production"

    database_url: str = "postgresql+psycopg://rosepsy:change_me@localhost:5432/rosepsy"

    # احراز هویت - بند ۴.۲ سند
    auth_secret_key: str = "dev-only-insecure-key-change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    # فاز ۶۰ - ورود مدیر با هویت کاربر (impersonation): توکن مستقل با انقضای طولانی‌تر
    # (نشست refresh مدیر دست‌نخورده می‌ماند؛ هیچ AuthSession برای کاربر ساخته نمی‌شود)
    impersonation_token_expire_minutes: int = 480
    activation_token_expire_hours: int = 24
    login_max_attempts: int = 5
    login_attempt_window_minutes: int = 15

    # ورود یکپارچه (SSO) با رز هاب — Rose Hub (BASIC flow)
    # clientSecret اختصاصی این سامانه در رز هاب؛ در استقرار واقعی با env بازنویسی شود
    rose_hub_client_id: str = "rose-psy-5c3f9b"
    rose_hub_client_secret: str = "1d5f9b3e7a0c4e82f6b0d2a8c4e1f735a9d0c6e2b8f4a0d6c2e8b1f5a3d7c940"
    rose_hub_launch_url: str = "http://130.185.73.157:8082/api/sso/launch?clientId=rose-psy-5c3f9b"


    # فاز ۳۷ - ADR-04: Object Storage پلاگین‌پذیر (تصمیم سند: MinIO/S3)
    # همان الگوی D02/D03/D07/B28:
    # storage_backend = "s3" (پیش‌فرض از فاز ۴۰ - گام ۳ طرح مهاجرت ADR-04) | "local"
    # آداپتور s3 فقط با endpoint + bucket + access_key + secret_key فعال می‌شود؛
    # نبود هر کدام، نبود کتابخانه boto3 یا خطای سرویس → fallback شفاف به local
    # (سپر خرابی fail-soft)؛ کلیدها هرگز به کلاینت/لاگ/پاسخ API نمی‌روند.
    storage_backend: str = "s3"
    s3_endpoint_url: str = ""   # نمونه تولید: http://minio:9000
    s3_bucket: str = "rosepsy-files"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_connect_timeout_seconds: float = 3.0

    # فاز ۴۱ - ADR-03 گام ۴: انقضای اعلام‌شده v1
    # warn (پیش‌فرض): فقط هدرهای Deprecation/Sunset/Warning روی پاسخ‌های /api/v1
    # readonly: کلید اضطراری چرخه حذف — متدهای نوشتاری v1 با 410 رد می‌شوند؛
    # فعال‌سازی فقط پس از یک چرخه انتشار کامل با حالت warn (پایش مصرف‌کننده جامانده)
    v1_deprecation_mode: str = "warn"
    # تاریخ پیشنهادی قطع v1 (YYYY-MM-DD) — در هدر Sunset به شکل HTTP-date می‌رود
    v1_sunset_date: str = "2027-04-20"

    # فاز ۴۳ - ADR-05 گام‌های ۱–۲: سقف نرخ سراسری دو لایه‌ای (لایه سرویس Redis)
    # لایه قاعده (تلاش ورود/OTP/نگهداشت/دستیار) سر جایش است؛ این لایه محافظ اضافه است
    rate_limit_enabled: bool = True
    # خالی = غیرفعال (پیش‌فرض توسعه/آزمون)؛ در compose مقدار redis://redis:6379/0
    # نبود Redis/خطای آن → fail-open با هشدار (بند ۶ ADR-05: دسترس‌پذیری مقدم است)
    rate_limit_redis_url: str = ""
    # سقف پیش‌فرض (بند گام ۲ طرح): ۱۲۰/دقیقه ناشناس (کلید route,ip) و ۶۰/دقیقه احرازشده
    rate_limit_public_per_minute: int = 120
    rate_limit_auth_per_minute: int = 60
    # override per-route: JSON مثل
    #   {"POST /api/v1/auth/login": 10, "GET /api/v1/public/*": 300}
    # کلید: "METHOD مسیر-نرمال‌شده" (شناسه‌ها :id) یا "* مسیر" یا با "*" پایانی برای پیشوند
    rate_limit_overrides: str = ""
    # user_idهای بی‌سقف (توکن‌های سرویس/مشتریان اداری SLA-دار) با کاما جدا می‌شوند
    rate_limit_whitelist_user_ids: str = ""
    # نرخ نمونه‌برداری ثبت ۴۲۹ در audit (۱.۰ = همیشه؛ کمتر = کنترل سیل در حمله)
    rate_limit_audit_sample_rate: float = 0.2

    # فاز ۴۲ - ADR-05 گام ۳: Idempotency-Key واقعی عملیات مالی
    # رزرو بدون پاسخ (سقوط سرور بین دو فاز) پس از این TTL کهنه و جایگزین می‌شود
    idempotency_pending_ttl_seconds: int = 600
    # عمر نگهداری ردیف‌های ثبت‌شده (طرح ADR-05: پاک‌سازی ۲۴ ساعته) — purge ادمین/تنبل
    idempotency_retention_hours: int = 24
    # حداقل فاصله پاک‌سازی تنبل خودکار داخل reserve (بدون نیاز به beat)
    idempotency_lazy_purge_interval_seconds: int = 3600

    # فاز ۲۶ - B09: نگهداشت موقت اسلات
    booking_hold_minutes: int = 10
    booking_hold_max_per_ip: int = 5

    # فاز ۲۶ - B02-lite: کد یک‌بارمصرف
    # در حالت توسعه کد در پاسخ API و لاگ نمایش داده می‌شود (آماده‌سازی D04)
    otp_dev_mode: bool = True
    otp_code_ttl_seconds: int = 180
    otp_max_attempts: int = 3
    otp_request_max: int = 3
    otp_request_window_seconds: int = 600
    otp_verify_token_seconds: int = 600
    booking_require_otp: bool = False  # سخت‌گیری کامل پس از تصمیم D04

    # فاز ۲۷ - B39-plus: آنتی‌ویروس واقعی ClamAV
    # clamav_host خالی = غیرفعال؛ در docker compose مقدار «clamav» است
    clamav_enabled: bool = True
    clamav_host: str = ""
    clamav_port: int = 3310
    clamav_timeout_seconds: float = 10.0
    # حذف EXIF/GPS و فراداده تصاویر پیش از ذخیره
    strip_image_metadata: bool = True

    # فاز ۲۷ - B12+: خروجی اعلان به ایمیل (تصمیم D04 - SMTP)
    # smtp_enabled=False → صف ایمیل ساخته می‌شود ولی «غیرفعال» علامت می‌خورد
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "rosepsy@clinic.local"
    smtp_use_tls: bool = True   # STARTTLS
    smtp_use_ssl: bool = False  # SMTPS 465
    email_outbox_max_attempts: int = 5
    notifications_email_enabled: bool = True

    # B39 سند جامع - فایل امن (با آداپتور ADR-04: local پیش‌فرض، s3 برای تولید)
    upload_dir: str = "./uploads"
    max_upload_mb: int = 10
    download_ticket_seconds: int = 120

    # فاز ۲۹ - B10/B11: سفارش و پرداخت (تصمیم D02: درگاه پلاگین‌پذیر)
    # sandbox = درگاه شبیه‌ساز توسعه/آزمون؛ zarinpal = درگاه پیشنهادی تولید
    payment_gateway: str = "sandbox"
    # آدرس عمومی سامانه برای ساخت callback درگاه‌های واقعی
    public_base_url: str = "http://localhost:5173"
    # زرین‌پال REST v4؛ merchant_id خالی = درگاه غیرفعال
    zarinpal_merchant_id: str = ""
    zarinpal_sandbox: bool = True
    # فاز ۶۹ - رزرو آنلاین: رزرو در انتظار پرداخت، تا این سقف اسلات را اشغال نگه می‌دارد
    booking_unpaid_ttl_minutes: int = 120
    # فاز ۳۲ - B40 + تصمیم D03: نقشه شعب با سرویس نقشه پلاگین‌پذیر
    # همان الگوی D02: پیش‌فرض OSM/Leaflet بدون کلید؛ نشنال/Map.ir برای تولید
    # map_provider = "osm" | "neshan" | "mapir"
    map_provider: str = "osm"
    # کلیدهای سرویس نقشه؛ خالی = درگاه غیرفعال (کلید هرگز به کلاینت نمی‌رود)
    neshan_api_key: str = ""
    mapir_api_key: str = ""

    # فاز ۳۵ - B25–B27 + تصمیم D07: دستیار هوشمند پلاگین‌پذیر
    # ai_provider = "rule" (پیش‌فرض: قاعده‌محور، بدون کلید، قطعی) | "llm"
    ai_provider: str = "rule"
    # کلید سرویس AI؛ خالی = fallback به rule (fail-soft)؛ کلید هرگز به کلاینت/لاگ نمی‌رود
    ai_api_key: str = ""
    # فاز ۵۳ - عامل هوشمند (الگوی deepseek-harness): هر سرویس OpenAI-سازگار
    # ai_api_base_url خالی/کلید خالی = ابزارهای عامل به rule سقوط می‌کنند (fail-soft)
    ai_api_base_url: str = ""
    ai_model: str = "deepseek-chat"
    # سقف گام حلقهٔ عامل (ابزار→مدل→ابزار...) برای جلوگیری از حلقهٔ بی‌پایان
    ai_agent_max_steps: int = 4

    # فاز ۳۶ - B28: یکپارچه‌سازی‌های بیرونی — سرویس پیامک پلاگین‌پذیر
    # همان الگوی D02/D03/D07:
    # sms_provider = "log" (پیش‌فرض: توسعه/آزمون، بدون کلید، قطعی) | "kavenegar" | "smsir"
    # sms_enabled=False → ردیف‌های صف به «disabled» علامت می‌خورند (شفافیت DPO)
    sms_enabled: bool = False
    sms_provider: str = "log"
    # کلید سرویس پیامک؛ خالی = fallback به log (fail-soft)؛ کلید هرگز به کلاینت/لاگ نمی‌رود
    sms_api_key: str = ""
    sms_sender: str = ""
    sms_max_attempts: int = 5
    # کپی اعلان‌های درون‌برنامه‌ای به پیامک (فقط گیرنده دارای موبایل)
    notifications_sms_enabled: bool = True

    # MIME های مجاز؛ فایل خارج از فهرست در قرنطینه می‌رود
    allowed_mime_types: str = (
        "application/pdf,image/png,image/jpeg,image/webp,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.openxmlformats-officedocument.presentationml.presentation,"
        "text/plain,text/csv"
    )

    @property
    def allowed_mime_list(self) -> list[str]:
        return [m.strip() for m in self.allowed_mime_types.split(",") if m.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cookie_secure(self) -> bool:
        # بند ۱۳.۲: در عملیات با HTTPS مقدار ENVIRONMENT=production باشد
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
