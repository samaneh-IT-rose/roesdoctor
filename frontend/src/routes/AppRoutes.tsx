import { Navigate, Route, Routes } from "react-router-dom";
import { CircularProgress } from "@mui/material";
import Layout from "../components/Layout";
import GlobalErrorBoundary from "../components/GlobalErrorBoundary";
import { useAuth } from "../auth/AuthContext";
import AccountingPage from "../pages/AccountingPage";
import ActivatePage from "../pages/ActivatePage";
import AdminDashboardPage from "../pages/AdminDashboardPage";
import ApplicantsPage from "../pages/ApplicantsPage";
import AssessmentFormPage from "../pages/AssessmentFormPage";
import AuditEventsPage from "../pages/AuditEventsPage";
import BranchMapPage from "../pages/BranchMapPage";
import BranchesPage from "../pages/BranchesPage";
import CaseDetailPage from "../pages/CaseDetailPage";
import CasesPage from "../pages/CasesPage";
import ChangePasswordPage from "../pages/ChangePasswordPage";
import ConsultationRequestsPage from "../pages/ConsultationRequestsPage";
import CounselorWorklistPage from "../pages/CounselorWorklistPage";
import CounselorsPage from "../pages/CounselorsPage";
import DashboardPage from "../pages/DashboardPage";
import DpoReportPage from "../pages/DpoReportPage";
import ImportsPage from "../pages/ImportsPage";
import InvoicePage from "../pages/InvoicePage";
import Level3AlertsPage from "../pages/Level3AlertsPage";
import NotificationsPage from "../pages/NotificationsPage";
import LoginPage from "../pages/LoginPage";
import SupportPage from "../pages/SupportPage";
import PsychTestCenterPage from "../pages/PsychTestCenterPage";
import PsychAttemptsPage from "../pages/PsychAttemptsPage";
import CounselingFilesPage from "../pages/CounselingFilesPage";
import PsychTestRunPage from "../pages/PsychTestRunPage";
import AssistantPage from "../pages/AssistantPage";
import OrganizationsPage from "../pages/OrganizationsPage";
import OrgProgramsPage from "../pages/OrgProgramsPage";
import OrgProgramWorkdeskPage from "../pages/OrgProgramWorkdeskPage";
import OrgExamResultsPage from "../pages/OrgExamResultsPage";
import LearningPage from "../pages/LearningPage";
import IntegrationsPage from "../pages/IntegrationsPage";
import MyAssessmentsPage from "../pages/MyAssessmentsPage";
import MyPanelPage from "../pages/MyPanelPage";
import OrdersPage from "../pages/OrdersPage";
import ProcessesPage from "../pages/ProcessesPage";
import ProcessMonitoringPage from "../pages/ProcessMonitoringPage";
import ReviewsPage from "../pages/ReviewsPage";
import ServicesPage from "../pages/ServicesPage";
import SupervisorCasesPage from "../pages/SupervisorCasesPage";
import TopicsPage from "../pages/TopicsPage";
import UsersPage from "../pages/UsersPage";
import RolesPermissionsPage from "../pages/RolesPermissionsPage";
import ChatPage from "../pages/ChatPage";
import PublicChatsPage from "../pages/PublicChatsPage";
// فاز ۶۱: فرم‌ساز و نظرسنجی + تماس تلفنی
import FormBuilderPage from "../pages/FormBuilderPage";
import FormResponsesPage from "../pages/FormResponsesPage";
import MyFormsPage from "../pages/MyFormsPage";
import FormFillPage from "../pages/FormFillPage";
import VerificationReviewsPage from "../pages/VerificationReviewsPage";
import WalletPage from "../pages/WalletPage";
import CartablePage from "../pages/CartablePage";
import ProtectedRoute from "./ProtectedRoute";

const CASE_ROLES = ["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"];
const STAFF_ROLES = ["ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "SYSTEM_ADMIN"];
const CLINICAL_ROLES = ["COUNSELOR", "TECHNICAL_SUPERVISOR"];

function RoleRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <CircularProgress sx={{ mx: "auto", display: "block", mt: 10 }} />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.roles.includes("APPLICANT")) return <Navigate to="/me" replace />;
  return <Navigate to="/dashboard" replace />;
}

export default function AppRoutes() {
  return (
    /* فاز ۵۱: مرز خطای سراسری — کرش رندر هر مسیر به‌جای صفحهٔ سفید، پیام فارسی دارد */
    <GlobalErrorBoundary>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/activate" element={<ActivatePage />} />
      {/* فاز ۳۲ - B40: نقشه شعب عمومی (بدون احراز هویت، مانند API عمومی) */}
      <Route path="/branch-map" element={<Layout><BranchMapPage /></Layout>} />
      <Route path="/" element={<RoleRedirect />} />
      <Route path="/change-password" element={<ProtectedRoute><Layout><ChangePasswordPage /></Layout></ProtectedRoute>} />
      <Route path="/dashboard" element={
        <ProtectedRoute roles={STAFF_ROLES}><Layout><DashboardPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۵۹: کارتابل شخصی هر حساب + نمای مدیریتی کارتابل کاربر */}
      <Route path="/cartable" element={
        <ProtectedRoute roles={STAFF_ROLES}><Layout><CartablePage /></Layout></ProtectedRoute>
      } />
      <Route path="/cartable/:userId" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><CartablePage /></Layout></ProtectedRoute>
      } />
      <Route path="/admin-dashboard" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN"]}><Layout><AdminDashboardPage /></Layout></ProtectedRoute>
      } />
      <Route path="/dpo-report" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN", "DPO"]}><Layout><DpoReportPage /></Layout></ProtectedRoute>
      } />
      <Route path="/audit-events" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><AuditEventsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/users" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><UsersPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۵۲: ماتریس نقش‌ها و دسترسی‌ها (گرافیکی) */}
      <Route path="/roles-permissions" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN"]}><Layout><RolesPermissionsPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۵۲: چت آنلاین و مشاوره — همهٔ حساب‌های فعال */}
      <Route path="/chat" element={
        <ProtectedRoute><Layout><ChatPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۵۵: پنل پذیرش/مدیر — گفتگوهای عمومی سایت و امتیازها */}
      <Route path="/public-chats" element={
        <ProtectedRoute roles={["ORG_MANAGER", "RECEPTION", "SYSTEM_ADMIN"]}>
          <Layout><PublicChatsPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۶۱: فرم‌ساز و نظرسنجی — ساخت/مدیریت فرم‌ها توسط مدیر */}
      <Route path="/form-builder" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN"]}>
          <Layout><FormBuilderPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/form-responses" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN"]}>
          <Layout><FormResponsesPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/form-responses/:templateId" element={
        <ProtectedRoute roles={["ORG_MANAGER", "SYSTEM_ADMIN"]}>
          <Layout><FormResponsesPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۶۱: فرم‌های من (نظرسنجی‌های در انتظار) + تکمیل فرم با لینک مستقیم */}
      <Route path="/my-forms" element={
        <ProtectedRoute><Layout><MyFormsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/forms/:templateId/fill" element={
        <ProtectedRoute><Layout><FormFillPage /></Layout></ProtectedRoute>
      } />
      <Route path="/counselors" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR"]}>
          <Layout><CounselorsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/services" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"]}>
          <Layout><ServicesPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۳ - B32: دسته‌بندی موضوعی */}
      <Route path="/topics" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"]}>
          <Layout><TopicsPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۳ - B21: سازمان‌ها و قراردادها */}
      <Route path="/organizations" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"]}>
          <Layout><OrganizationsPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۵۸ - پنل آزمون‌های سازمانی: فهرست برنامه‌ها + کارتابل */}
      <Route path="/org-programs" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><OrgProgramsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/org-programs/:id" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><OrgProgramWorkdeskPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۷۴ - آزمون‌های برگزارشده سازمانی: مدیر سازمان فقط سازمان خودش */}
      <Route path="/org-exam-results" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><OrgExamResultsPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۴ - B33–B36: محتوا/دوره/آزمون/گواهی */}
      <Route path="/learning" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"]}>
          <Layout><LearningPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۵ - B23: پشتیبانی */}
      <Route path="/support" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><SupportPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۵ + ۴۷ - B37: مرکز آزمون روان‌شناسی (D08) — همه نقش‌ها می‌توانند آزمون بدهند */}
      <Route path="/psych-tests" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION", "APPLICANT"]}>
          <Layout><PsychTestCenterPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۷۰ - آزمون‌های برگزارشده + پرونده‌های مشاوره کاربران */}
      <Route path="/psych-attempts" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION"]}>
          <Layout><PsychAttemptsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/counseling-files" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION"]}>
          <Layout><CounselingFilesPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/psych-tests/:slug/run" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR", "COUNSELOR", "RECEPTION", "APPLICANT"]}>
          <Layout><PsychTestRunPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۵ - B25–B27: دستیار هوشمند (D07) */}
      <Route path="/assistant" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR", "APPLICANT"]}>
          <Layout><AssistantPage /></Layout>
        </ProtectedRoute>
      } />
      {/* فاز ۳۶ - B28: یکپارچه‌سازی‌های بیرونی */}
      <Route path="/integrations" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER"]}>
          <Layout><IntegrationsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/verification-reviews" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "TECHNICAL_SUPERVISOR"]}>
          <Layout><VerificationReviewsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/branches" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR"]}>
          <Layout><BranchesPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/orders" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"]}>
          <Layout><OrdersPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/invoices/:id" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION", "TECHNICAL_SUPERVISOR", "COUNSELOR"]}>
          <Layout><InvoicePage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/wallet" element={
        <ProtectedRoute>
          <Layout><WalletPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/accounting" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER"]}>
          <Layout><AccountingPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/applicants" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"]}>
          <Layout><ApplicantsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/imports" element={
        <ProtectedRoute roles={["SYSTEM_ADMIN", "ORG_MANAGER", "RECEPTION"]}>
          <Layout><ImportsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/consultation-requests" element={
        <ProtectedRoute roles={["ORG_MANAGER", "RECEPTION", "SYSTEM_ADMIN", "COUNSELOR"]}>
          <Layout><ConsultationRequestsPage /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/cases" element={
        <ProtectedRoute roles={CASE_ROLES}><Layout><CasesPage /></Layout></ProtectedRoute>
      } />
      <Route path="/cases/:id" element={
        <ProtectedRoute roles={CASE_ROLES}><Layout><CaseDetailPage /></Layout></ProtectedRoute>
      } />
      <Route path="/cases/:caseId/assessments/new" element={
        <ProtectedRoute roles={CLINICAL_ROLES}><Layout><AssessmentFormPage /></Layout></ProtectedRoute>
      } />
      <Route path="/assessments/:id" element={
        <ProtectedRoute roles={CLINICAL_ROLES}><Layout><AssessmentFormPage /></Layout></ProtectedRoute>
      } />
      <Route path="/reviews" element={
        <ProtectedRoute roles={["TECHNICAL_SUPERVISOR"]}><Layout><ReviewsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/notifications" element={
        <ProtectedRoute><Layout><NotificationsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/level3-alerts" element={
        <ProtectedRoute roles={["TECHNICAL_SUPERVISOR"]}><Layout><Level3AlertsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/supervised-cases" element={
        <ProtectedRoute roles={["TECHNICAL_SUPERVISOR"]}><Layout><SupervisorCasesPage /></Layout></ProtectedRoute>
      } />
      <Route path="/my-assessments" element={
        <ProtectedRoute roles={["COUNSELOR"]}><Layout><MyAssessmentsPage /></Layout></ProtectedRoute>
      } />
      <Route path="/worklist" element={
        <ProtectedRoute roles={["COUNSELOR"]}><Layout><CounselorWorklistPage /></Layout></ProtectedRoute>
      } />
      <Route path="/me" element={
        <ProtectedRoute roles={["APPLICANT"]}><Layout><MyPanelPage /></Layout></ProtectedRoute>
      } />
      <Route path="/processes" element={
        <ProtectedRoute roles={STAFF_ROLES}><Layout><ProcessesPage /></Layout></ProtectedRoute>
      } />
      {/* فاز ۴۹ - B42: مانیتورینگ وضعیت درخواست در فرایند */}
      <Route path="/process-monitoring" element={
        <ProtectedRoute roles={STAFF_ROLES}><Layout><ProcessMonitoringPage /></Layout></ProtectedRoute>
      } />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </GlobalErrorBoundary>
  );
}
