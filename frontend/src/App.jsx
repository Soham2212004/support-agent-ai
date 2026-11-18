import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Home from "./pages/Home.jsx";
import Register from "./pages/Register.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import ApiDocs from "./pages/ApiDocs.jsx";
import PublicChatDemo from "./pages/PublicChatDemo.jsx";
import StatusPage from "./pages/StatusPage.jsx";
import VerifyEmail from "./pages/VerifyEmail.jsx";
import Pricing from "./pages/Pricing.jsx";
import Terms from "./pages/Terms.jsx";
import Privacy from "./pages/Privacy.jsx";
import Contact from "./pages/Contact.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="register" element={<Register />} />
        <Route path="login" element={<Login />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="api-docs" element={<ApiDocs />} />
        <Route path="demo" element={<PublicChatDemo />} />
        <Route path="status" element={<StatusPage />} />
        <Route path="verify-email" element={<VerifyEmail />} />
        <Route path="pricing" element={<Pricing />} />
        <Route path="terms" element={<Terms />} />
        <Route path="privacy" element={<Privacy />} />
        <Route path="contact" element={<Contact />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}