import { useEffect, useMemo, useState } from "react";
import { api, setCsrfToken } from "./api";
import { ErrorNotice, Field, Modal, roleName } from "./ui";
import {
  AttendancePage,
  CoursesPage,
  CustomersPage,
  DashboardPage,
  MyCoursesPage,
  ReportsPage,
  StudentsPage,
  TeachersPage,
  UsersPage,
} from "./pages";

const iconPaths = {
  home: "M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5M9 21v-7h6v7",
  leads: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM19 8v6M22 11h-6",
  teacher: "M4 19.5V8l8-4 8 4v11.5M2 21h20M8 11h8M8 15h8",
  students: "M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M8.5 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM18 8a3 3 0 0 1 0 6M23 21v-2a4 4 0 0 0-3-3.87",
  calendar: "M6 2v4M18 2v4M3 9h18M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2ZM8 13h3v3H8z",
  check: "M22 11.1V12a10 10 0 1 1-5.9-9.1M22 4 12 14.01l-3-3",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10ZM9 12l2 2 4-4",
  menu: "M4 6h16M4 12h16M4 18h16",
  key: "M21 2l-2 2m-7.6 7.6a5 5 0 1 1-7.1 7.1 5 5 0 0 1 7.1-7.1ZM14 9l7-7M18 5l2 2",
  logout: "M10 17l5-5-5-5M15 12H3M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  eye: "M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12ZM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
  eyeOff: "m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 4.2A11.7 11.7 0 0 1 12 4c6.5 0 10 8 10 8a17 17 0 0 1-2.1 3.2M6.6 6.6C3.5 8.4 2 12 2 12s3.5 8 10 8a10.7 10.7 0 0 0 4.1-.8",
  wifi: "M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 20h.01",
  report: "M4 20V10M10 20V4M16 20v-7M22 20V7M2 20h22",
};

function Icon({ name, size = 20, className = "" }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[name] || iconPaths.more} /></svg>;
}

const menuByRole = {
  admin: [
    ["dashboard", "总览", "home"], ["customers", "客户", "leads"], ["teachers", "老师", "teacher"],
    ["students", "学生", "students"], ["courses", "排课", "calendar"], ["attendance", "签到", "check"],
    ["reports", "报表", "report"], ["users", "管理员", "shield"],
  ],
  teacher: [["my-courses", "课表", "calendar"], ["attendance", "签到", "check"]],
  student: [["my-courses", "课程", "calendar"]],
};

function AuthPage({ onAuthenticated }) {
  const rememberedPreference = localStorage.getItem("tcms_remember_login") === "true";
  const [form, setForm] = useState({
    username: localStorage.getItem("tcms_username") || "",
    password: "",
    remember: rememberedPreference,
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const change = (event) => {
    const value = event.target.type === "checkbox" ? event.target.checked : event.target.value;
    setForm((current) => ({ ...current, [event.target.name]: value }));
  };
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const user = await api("/auth/login", { method: "POST", body: { username: form.username, password: form.password, remember: form.remember } });
      if (form.remember) {
        localStorage.setItem("tcms_username", form.username);
        localStorage.setItem("tcms_remember_login", "true");
      } else {
        localStorage.removeItem("tcms_username");
        localStorage.removeItem("tcms_remember_login");
      }
      onAuthenticated(user);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };

  return <main className="auth-page">
    <section className="auth-visual">
      <div className="auth-mark">培</div>
      <div className="auth-message"><span className="eyebrow light">Training Center · 3.3</span><h1>教务管理，<br />随时掌握。</h1><p>从客户跟进到学生签到，把机构每天的关键工作装进手机。</p></div>
      <div className="auth-metrics"><div><b>3</b><span>角色权限</span></div><div><b>1</b><span>统一工作台</span></div><div><b>30 天</b><span>安全免登录</span></div></div>
    </section>
    <section className="auth-panel">
      <div className="auth-card">
        <div className="auth-mobile-brand"><div className="auth-mark">培</div><div><b>培训机构</b><span>移动教务工作台</span></div></div>
        <div className="auth-heading"><span className="eyebrow">安全登录</span><h2>欢迎回来</h2><p>账号由机构管理员开通。忘记账号或密码，请联系机构管理员。</p></div>
        <form className="form-stack" onSubmit={submit} autoComplete="on">
          <Field label="用户名"><input name="username" value={form.username} onChange={change} autoComplete="username" autoCapitalize="none" spellCheck="false" minLength="3" maxLength="32" placeholder="请输入用户名" required /></Field>
          <Field label="密码"><div className="password-input"><input name="password" value={form.password} onChange={change} type={showPassword ? "text" : "password"} autoComplete="current-password" minLength="1" placeholder="请输入密码" required /><button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "隐藏密码" : "显示密码"}><Icon name={showPassword ? "eyeOff" : "eye"} /></button></div></Field>
          <div className="remember-row"><label className="switch-label"><input name="remember" type="checkbox" checked={form.remember} onChange={change} /><span className="switch"></span><span><b>记住登录</b><small>在这台设备保持 30 天</small></span></label><span className="security-note">密码由设备密码管理器保存</span></div>
          <ErrorNotice error={error} />
          <button className="button primary full login-button" disabled={busy}><span>{busy ? "正在验证…" : "进入工作台"}</span><span className="button-arrow">→</span></button>
        </form>
        <p className="auth-footnote">登录即表示这是你信任的设备。请勿在公共手机上开启“记住登录”。</p>
      </div>
    </section>
  </main>;
}

function PasswordModal({ onClose, notify }) {
  const [form, setForm] = useState({ old: "", new: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    try { await api("/auth/password", { method: "POST", body: form }); notify("密码已更新，请在需要时重新开启记住登录"); onClose(); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return <Modal title="修改密码" onClose={onClose}><form className="form-stack" onSubmit={submit} autoComplete="on"><Field label="当前密码"><input type="password" autoComplete="current-password" value={form.old} onChange={(e) => setForm({ ...form, old: e.target.value })} required /></Field><Field label="新密码" hint="至少 8 位"><input type="password" autoComplete="new-password" minLength="8" value={form.new} onChange={(e) => setForm({ ...form, new: e.target.value })} required /></Field><ErrorNotice error={error} /><div className="modal-actions"><button type="button" className="button secondary" onClick={onClose}>取消</button><button className="button primary" disabled={busy}>{busy ? "保存中…" : "保存新密码"}</button></div></form></Modal>;
}

function Workspace({ user, onLogout }) {
  const items = useMemo(() => menuByRole[user.role] || [], [user.role]);
  const [active, setActive] = useState(items[0]?.[0]);
  const [drawer, setDrawer] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => {
    const on = () => setOnline(true); const off = () => setOnline(false);
    window.addEventListener("online", on); window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  const notify = (message) => {
    navigator.vibrate?.(8);
    setToast(message); window.clearTimeout(window.__toastTimer);
    window.__toastTimer = window.setTimeout(() => setToast(""), 2800);
  };
  const go = (key) => {
    const update = () => { setActive(key); setDrawer(false); window.scrollTo({ top: 0, behavior: "smooth" }); };
    if (document.startViewTransition) document.startViewTransition(update); else update();
  };
  const logout = async () => {
    try { await api("/auth/logout", { method: "POST" }); }
    finally { setCsrfToken(""); localStorage.removeItem("tcms_remember_login"); onLogout(); }
  };

  const pageProps = { notify, user };
  const pages = {
    dashboard: <DashboardPage {...pageProps} onNavigate={go} />,
    customers: <CustomersPage {...pageProps} />,
    teachers: <TeachersPage {...pageProps} />,
    students: <StudentsPage {...pageProps} />,
    courses: <CoursesPage {...pageProps} />,
    attendance: <AttendancePage {...pageProps} />,
    reports: <ReportsPage {...pageProps} />,
    users: <UsersPage {...pageProps} />,
    "my-courses": <MyCoursesPage {...pageProps} />,
  };
  const current = items.find(([key]) => key === active) || items[0];
  const preferredMobileKeys = user.role === "admin" ? ["dashboard", "customers", "courses", "attendance"] : items.map(([key]) => key);
  const mobileItems = preferredMobileKeys.map((key) => items.find(([itemKey]) => itemKey === key)).filter(Boolean).slice(0, 4);
  const mobileHasMore = items.some(([key]) => !mobileItems.some(([mobileKey]) => mobileKey === key));

  return <div className="workspace">
    {drawer && <button className="drawer-scrim" aria-label="关闭菜单" onClick={() => setDrawer(false)} />}
    <aside className={`sidebar ${drawer ? "open" : ""}`}>
      <div className="brand"><div className="brand-mark">培</div><div><b>培训机构</b><span>智能教务工作台</span></div><button className="sidebar-close" onClick={() => setDrawer(false)} aria-label="关闭菜单">×</button></div>
      <div className="sidebar-label">工作空间</div>
      <nav>{items.map(([key, label, icon]) => <button key={key} className={active === key ? "active" : ""} onClick={() => go(key)}><Icon name={icon} /><span>{label}</span></button>)}</nav>
      <div className="sidebar-account">
        <div className="profile"><div className="avatar">{(user.name || user.username)[0]}</div><div><b>{user.name || user.username}</b><span>{roleName[user.role]} · @{user.username}</span></div></div>
        <div className="profile-actions"><button onClick={() => { setPasswordOpen(true); setDrawer(false); }}><Icon name="key" />修改密码</button><button onClick={logout}><Icon name="logout" />退出</button></div>
      </div>
    </aside>
    <section className="work-main">
      <header className="topbar">
        <button className="menu-button" onClick={() => setDrawer(true)} aria-label="打开菜单"><Icon name="menu" /></button>
        <div className="topbar-title"><span>今天的工作空间</span><b>{current?.[1]}</b></div>
        <div className={`online-pill ${online ? "" : "offline"}`}><Icon name="wifi" size={14} /><span>{online ? "在线" : "离线"}</span></div>
        <div className="top-actions"><button className="text-button" onClick={() => setPasswordOpen(true)}>修改密码</button><button className="text-button" onClick={logout}>退出</button></div>
        <button className="mobile-profile" onClick={() => setDrawer(true)} aria-label="打开个人菜单">{(user.name || user.username)[0]}</button>
      </header>
      <div className="page-content"><div className="page-stage" key={active}>{pages[active]}</div></div>
    </section>
    <nav className="mobile-nav" aria-label="手机主导航">
      {mobileItems.map(([key, label, icon]) => <button key={key} className={active === key ? "active" : ""} onClick={() => go(key)}><span className="mobile-nav-icon"><Icon name={icon} /></span><small>{label}</small></button>)}
      {mobileHasMore && <button className={mobileItems.some(([key]) => key === active) ? "" : "active"} onClick={() => setDrawer(true)}><span className="mobile-nav-icon"><Icon name="more" /></span><small>更多</small></button>}
    </nav>
    {passwordOpen && <PasswordModal onClose={() => setPasswordOpen(false)} notify={notify} />}
    {!online && <div className="offline-banner">当前网络不可用，恢复连接后可继续操作</div>}
    {toast && <div className="toast" role="status"><span>✓</span>{toast}</div>}
  </div>;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  useEffect(() => { api("/auth/me").then(setUser).catch(() => setUser(null)).finally(() => setReady(true)); }, []);
  if (!ready) return <div className="splash"><div className="splash-orbit"><div className="brand-mark large">培</div></div><span>正在准备你的工作台</span></div>;
  return user ? <Workspace user={user} onLogout={() => setUser(null)} /> : <AuthPage onAuthenticated={setUser} />;
}
