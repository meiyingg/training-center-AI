import { useEffect, useMemo, useState } from "react";
import { api, downloadCsv } from "./api";
import { Confirm, Empty, ErrorNotice, Field, Loading, Modal, PageHeader, roleName } from "./ui";

function localDateKey(source) {
  const date = source ? new Date(source) : new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
}

function useAsync(load, dependencies = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true; setError("");
    load().then((value) => alive && setData(value)).catch((err) => alive && setError(err.message));
    return () => { alive = false; };
  }, [...dependencies, tick]); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, reload: () => setTick((value) => value + 1), setData };
}

function FormActions({ onClose, busy, label = "保存" }) {
  return <div className="modal-actions"><button type="button" className="button secondary" onClick={onClose}>取消</button><button className="button primary" disabled={busy}>{busy ? "处理中…" : label}</button></div>;
}

function EntityCard({ title, subtitle, badge, children, actions }) {
  return <article className="entity-card"><div className="entity-top"><div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>{badge}</div>{children}{actions && <div className="card-actions">{actions}</div>}</article>;
}

export function DashboardPage({ onNavigate }) {
  const { data, error } = useAsync(() => api("/dashboard"), []);
  if (!data && !error) return <Loading />;
  const stats = [
    ["待跟进客户", data?.pendingCustomers, "orange"], ["正式学生", data?.students, "blue"],
    ["在岗老师", data?.teachers, "violet"], ["今日课程", data?.todayCourses, "green"],
  ];
  return <><PageHeader eyebrow="今日概览" title="教务工作台" description="先处理今天最重要的客户、课程和签到。" action={<button className="button primary" onClick={() => onNavigate("courses")}>＋ 新建课程</button>} /><ErrorNotice error={error} />
    <section className="stats-grid">{stats.map(([label, value, tone]) => <article className={`stat-card ${tone}`} key={label}><span>{label}</span><b>{value ?? "—"}</b><small>实时数据</small></article>)}</section>
    <section className="dashboard-grid"><article className="panel"><div className="panel-head"><div><span className="eyebrow">今日安排</span><h2>课程时间线</h2></div><button className="link-button" onClick={() => onNavigate("courses")}>查看全部 →</button></div>{data?.todayCourseList?.length ? <div className="timeline">{data.todayCourseList.map((course) => <div className="timeline-item" key={course.id}><time>{course.start}</time><div><b>{course.topic}</b><span>{course.start}–{course.end} · {course.studentIds.length} 名学生</span></div></div>)}</div> : <Empty title="今天没有课程" text="可以提前安排下一节课。" />}</article>
      <article className="panel"><div className="panel-head"><div><span className="eyebrow">待办</span><h2>未签到提醒</h2></div><span className="count-pill">{data?.unsigned?.length || 0}</span></div>{data?.unsigned?.length ? <div className="compact-list">{data.unsigned.slice(0, 8).map((item) => <div key={`${item.courseId}-${item.student.id}`}><span className="dot warning"></span><div><b>{item.student.name}</b><small>{item.start} · {item.courseTopic}</small></div></div>)}</div> : <Empty title="全部完成" text="今天暂时没有未签到记录。" />}</article>
      {data?.dueFollowups && <article className="panel followup-panel"><div className="panel-head"><div><span className="eyebrow">招生待办</span><h2>到期客户跟进</h2></div><button className="link-button" onClick={() => onNavigate("customers")}>{data.dueFollowups.length ? `处理 ${data.dueFollowups.length} 项 →` : "客户管理 →"}</button></div>{data.dueFollowups.length ? <div className="due-followups">{data.dueFollowups.slice(0, 6).map((item) => <div className="due-followup" key={item.followupId}><span className={item.nextDate < localDateKey() ? "due-date overdue" : "due-date"}>{item.nextDate < localDateKey() ? "已逾期" : "今天"}</span><div><b>{item.customerName}</b><small>{item.method} · {item.interest || "未填写意向课程"}</small></div><a href={`tel:${item.phone}`}>{item.phone}</a></div>)}</div> : <Empty title="没有到期跟进" text="今天的客户跟进已经安排妥当。" />}</article>}</section></>;
}

export function ReportsPage() {
  const [days, setDays] = useState(30);
  const state = useAsync(() => api(`/reports?days=${days}`), [days]);
  const report = state.data; const summary = report?.summary;
  const trend = report?.daily?.slice(-14) || [];
  const maxScheduled = Math.max(1, ...trend.map((item) => item.scheduled));
  const kpis = [
    ["完成课次", summary?.courses, "节", "blue"], ["累计课时", summary?.courseHours, "小时", "violet"],
    ["应到人次", summary?.scheduled, "人次", "orange"], ["整体签到率", summary?.attendanceRate, "%", "green"],
    ["新增客户", summary?.newCustomers, "人", "blue"], ["报名转化率", summary?.conversionRate, "%", "violet"],
  ];
  return <><PageHeader eyebrow="经营分析" title="运营报表" description="用课程、考勤和招生数据判断机构近期运营情况。" />
    <div className="report-toolbar"><div className="period-switch">{[[7, "近 7 天"], [30, "近 30 天"], [90, "近 90 天"]].map(([value, label]) => <button key={value} className={days === value ? "active" : ""} onClick={() => setDays(value)}>{label}</button>)}</div>{report && <span>{report.period.start} 至 {report.period.end}</span>}</div><ErrorNotice error={state.error} />
    {!report ? <Loading /> : <><section className="report-kpis">{kpis.map(([label, value, unit, tone]) => <article className={`report-kpi ${tone}`} key={label}><span>{label}</span><div><b>{value ?? "—"}</b><small>{unit}</small></div></article>)}</section>
      <section className="report-layout"><article className="panel trend-panel"><div className="panel-head"><div><span className="eyebrow">考勤趋势</span><h2>最近 14 天到课情况</h2></div><span className="legend"><i></i>应到 <i></i>实到</span></div>{trend.some((item) => item.scheduled) ? <div className="attendance-chart">{trend.map((item) => <div className="chart-day" key={item.date} title={`${item.date}：应到 ${item.scheduled}，实到 ${item.signed}`}><div className="bar-track"><span className="bar scheduled" style={{ height: `${Math.max(5, item.scheduled / maxScheduled * 100)}%` }}></span><span className="bar signed" style={{ height: `${Math.max(item.signed ? 5 : 0, item.signed / maxScheduled * 100)}%` }}></span></div><small>{item.date.slice(5).replace("-", "/")}</small></div>)}</div> : <Empty title="暂无考勤数据" text="完成排课和签到后会自动生成趋势。" />}</article>
        <article className="panel report-summary-panel"><div className="panel-head"><div><span className="eyebrow">招生漏斗</span><h2>客户转化</h2></div></div><div className="conversion-ring" style={{ "--rate": `${Math.min(100, summary.conversionRate)}%` }}><div><b>{summary.conversionRate}%</b><span>报名转化</span></div></div><div className="conversion-rows"><div><span>新增客户</span><b>{summary.newCustomers}</b></div><div><span>已报名客户</span><b>{summary.enrolledCustomers}</b></div></div></article></section>
      <section className="panel teacher-report"><div className="panel-head"><div><span className="eyebrow">师资负载</span><h2>老师工作量</h2></div><span className="count-pill">{report.teachers.length}</span></div>{report.teachers.length ? <div className="teacher-performance">{report.teachers.map((teacher) => <article key={teacher.id}><div className="teacher-rank-avatar">{teacher.name[0]}</div><div className="teacher-performance-main"><b>{teacher.name}</b><span>{teacher.subject || "未设置科目"}</span><div className="performance-bar"><i style={{ width: `${teacher.attendanceRate}%` }}></i></div><small>签到率 {teacher.attendanceRate}%</small></div><dl><div><dt>课程</dt><dd>{teacher.courseCount}</dd></div><div><dt>应到</dt><dd>{teacher.scheduled}</dd></div><div><dt>实到</dt><dd>{teacher.signed}</dd></div></dl></article>)}</div> : <Empty title="暂无老师数据" />}</section></>}
  </>;
}

function CustomerForm({ initial, onClose, onDone }) {
  const [form, setForm] = useState(initial ? {
    name: initial.name, phone: initial.phone, contact: initial.contact || "电话",
    interest: initial.interest || "", status: initial.status,
  } : { name: "", phone: "", contact: "电话", interest: "", status: "pending" });
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const submit = async (e) => { e.preventDefault(); setBusy(true); setError(""); try { const body = { ...form }; if (!initial) delete body.status; await api(initial ? `/customers/${initial.id}` : "/customers", { method: initial ? "PUT" : "POST", body }); onDone(initial ? "客户资料已更新" : "客户已录入"); onClose(); } catch (err) { setError(err.message); } finally { setBusy(false); } };
  return <form className="form-stack" onSubmit={submit}><div className="form-grid"><Field label="客户姓名"><input name="name" value={form.name} onChange={change} required /></Field><Field label="手机号"><input name="phone" value={form.phone} onChange={change} inputMode="numeric" minLength="11" maxLength="11" required /></Field></div><div className="form-grid"><Field label="联系方式"><select name="contact" value={form.contact} onChange={change}><option>电话</option><option>微信</option><option>短信</option><option>其他</option></select></Field><Field label="意向课程"><input name="interest" value={form.interest} onChange={change} /></Field></div>{initial && <Field label="状态"><select name="status" value={form.status} onChange={change}><option value="pending">待跟进</option><option value="enrolled">已报名</option></select></Field>}<ErrorNotice error={error} /><FormActions onClose={onClose} busy={busy} /></form>;
}

function FollowupPanel({ customer, onChanged }) {
  const state = useAsync(() => api(`/customers/${customer.id}/followups`), [customer.id]);
  const [form, setForm] = useState({ method: "电话", note: "", result: "", nextDate: "" });
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const change = (event) => setForm({ ...form, [event.target.name]: event.target.value });
  const submit = async (event) => { event.preventDefault(); setBusy(true); setError(""); try { await api(`/customers/${customer.id}/followups`, { method: "POST", body: { ...form, nextDate: form.nextDate || null } }); setForm({ method: "电话", note: "", result: "", nextDate: "" }); state.reload(); onChanged("跟进记录已保存"); } catch (err) { setError(err.message); } finally { setBusy(false); } };
  const remove = async (record) => { try { await api(`/customers/${customer.id}/followups/${record.id}`, { method: "DELETE" }); state.reload(); onChanged("跟进记录已删除"); } catch (err) { setError(err.message); } };
  return <div className="followup-workspace"><form className="form-stack followup-form" onSubmit={submit}><div className="form-grid"><Field label="跟进方式"><select name="method" value={form.method} onChange={change}><option>电话</option><option>微信</option><option>面谈</option><option>短信</option><option>其他</option></select></Field><Field label="下次跟进日期" hint="留空表示无需提醒"><input name="nextDate" type="date" value={form.nextDate} onChange={change} /></Field></div><Field label="本次沟通记录"><textarea name="note" rows="3" maxLength="500" value={form.note} onChange={change} placeholder="记录客户关注的问题、课程偏好和下一步计划" required /></Field><Field label="跟进结果（选填）"><input name="result" maxLength="100" value={form.result} onChange={change} placeholder="例如：已发送试听课时间" /></Field><ErrorNotice error={error} /><button className="button primary" disabled={busy}>{busy ? "保存中…" : "保存跟进记录"}</button></form><section className="followup-history"><div className="section-title"><div><span className="eyebrow">历史记录</span><h3>{customer.name} · {state.data?.length || 0} 次跟进</h3></div></div>{!state.data ? <Loading /> : state.data.length ? <div className="followup-timeline">{state.data.map((record) => <article key={record.id}><span className="timeline-dot"></span><div className="followup-record-head"><b>{record.method}</b><time>{record.created_at?.replace("T", " ").slice(0, 16)}</time></div><p>{record.note}</p>{record.result && <span className="result-chip">结果：{record.result}</span>}<div className="followup-record-foot"><small>{record.next_date ? `下次跟进：${record.next_date}` : "未设置下次提醒"}</small><button type="button" onClick={() => remove(record)}>删除</button></div></article>)}</div> : <Empty title="还没有跟进记录" text="完成一次沟通后在上方记录。" />}</section></div>;
}

export function CustomersPage({ notify }) {
  const [query, setQuery] = useState(""); const [status, setStatus] = useState(""); const [modal, setModal] = useState(null); const [confirm, setConfirm] = useState(null);
  const state = useAsync(() => api(`/customers?q=${encodeURIComponent(query)}&status=${status}`), [query, status]);
  const done = (message) => { notify(message); state.reload(); };
  const remove = async () => { await api(`/customers/${confirm.id}`, { method: "DELETE" }); setConfirm(null); done("客户已删除"); };
  const convert = async (customer) => { await api(`/customers/${customer.id}/convert`, { method: "POST" }); done(`${customer.name} 已转为正式学生`); };
  return <><PageHeader eyebrow="招生跟进" title="客户管理" description="记录线索、安排跟进提醒，并把已报名客户转为正式学生。" action={<button className="button primary" onClick={() => setModal({ type: "add" })}>＋ 录入客户</button>} />
    <div className="toolbar"><input className="search" placeholder="搜索姓名或手机号" value={query} onChange={(e) => setQuery(e.target.value)} /><div className="filter-pills">{[["", "全部"], ["pending", "待跟进"], ["enrolled", "已报名"]].map(([key, label]) => <button className={status === key ? "active" : ""} onClick={() => setStatus(key)} key={key}>{label}</button>)}</div></div><ErrorNotice error={state.error} />
    {!state.data ? <Loading /> : state.data.length ? <div className="entity-grid">{state.data.map((customer) => <EntityCard key={customer.id} title={customer.name} subtitle={customer.phone} badge={<span className={`badge ${customer.status === "enrolled" ? "success" : "warning"}`}>{customer.status === "enrolled" ? "已报名" : "待跟进"}</span>} actions={<><button className="button mini primary" onClick={() => setModal({ type: "followups", item: customer })}>跟进记录 {customer.followupCount || ""}</button><button className="button mini secondary" onClick={() => setModal({ type: "edit", item: customer })}>编辑</button>{customer.status === "pending" && <button className="button mini soft" onClick={() => convert(customer)}>转为学生</button>}<button className="button mini danger-ghost" onClick={() => setConfirm(customer)}>删除</button></>}><dl className="meta-list"><div><dt>联系方式</dt><dd>{customer.contact || "—"}</dd></div><div><dt>意向课程</dt><dd>{customer.interest || "未填写"}</dd></div><div><dt>最近跟进</dt><dd>{customer.lastFollowupAt?.slice(0, 10) || "尚未跟进"}</dd></div><div><dt>下次提醒</dt><dd className={customer.nextFollowup && customer.nextFollowup <= localDateKey() ? "text-warning" : ""}>{customer.nextFollowup || "未安排"}</dd></div></dl></EntityCard>)}</div> : <Empty title="没有匹配的客户" />}
    {modal?.type === "followups" ? <Modal wide title={`${modal.item.name} · 跟进记录`} onClose={() => setModal(null)}><FollowupPanel customer={modal.item} onChanged={done} /></Modal> : modal && <Modal title={modal.type === "add" ? "录入客户" : "编辑客户"} onClose={() => setModal(null)}><CustomerForm initial={modal.item} onClose={() => setModal(null)} onDone={done} /></Modal>}
    {confirm && <Confirm title="删除客户" text={`确定删除 ${confirm.name}？此操作无法撤销。`} onCancel={() => setConfirm(null)} onConfirm={remove} />}</>;
}

function makeInitialPassword() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const values = new Uint32Array(10); crypto.getRandomValues(values);
  return `T!${Array.from(values, (value) => chars[value % chars.length]).join("")}`;
}

function TeacherForm({ initial, onClose, onDone }) {
  const [form, setForm] = useState(initial ? { name: initial.name, phone: initial.phone || "", subject: initial.subject || "" } : { name: "", phone: "", subject: "", createAccount: true, username: "", password: makeInitialPassword() }); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { if (initial || !form.createAccount) return; if (!form.name.trim()) { setForm((current) => current.username ? { ...current, username: "" } : current); return; } let alive = true; const timer = window.setTimeout(() => api(`/teachers/username-suggestion?name=${encodeURIComponent(form.name)}`).then((data) => { if (alive) setForm((current) => ({ ...current, username: data.username })); }).catch(() => {}), 220); return () => { alive = false; window.clearTimeout(timer); }; }, [initial, form.name, form.createAccount]);
  const change = (event) => setForm({ ...form, [event.target.name]: event.target.type === "checkbox" ? event.target.checked : event.target.value });
  const submit = async (e) => { e.preventDefault(); setBusy(true); setError(""); try { const body = initial ? { name: form.name, phone: form.phone, subject: form.subject } : form; const teacher = await api(initial ? `/teachers/${initial.id}` : "/teachers", { method: initial ? "PUT" : "POST", body }); const credentials = !initial && form.createAccount ? { name: teacher.name, username: teacher.account.username, password: form.password } : null; onDone(initial ? "老师资料已更新" : "老师已添加", credentials); onClose(); } catch (err) { setError(err.message); } finally { setBusy(false); } };
  return <form className="form-stack teacher-create-form" onSubmit={submit}><div className="form-section"><div className="form-section-title"><b>老师资料</b><span>用于排课和联系</span></div><Field label="姓名"><input name="name" value={form.name} onChange={change} required /></Field><div className="form-grid"><Field label="联系电话"><input name="phone" value={form.phone} onChange={change} inputMode="tel" /></Field><Field label="授课科目"><input name="subject" value={form.subject} onChange={change} placeholder="例如：英语、数学" /></Field></div></div>{!initial && <div className="form-section account-section"><label className="account-toggle"><input name="createAccount" type="checkbox" checked={form.createAccount} onChange={change} /><span className="switch"></span><span><b>同时开通老师登录账号</b><small>老师可登录查看自己的课表和签到</small></span></label>{form.createAccount && <div className="account-fields"><Field label="登录用户名" hint="根据姓名自动生成；如有重复会自动追加数字"><input name="username" value={form.username} readOnly tabIndex="-1" placeholder="填写姓名后自动生成" /></Field><Field label="初始密码" hint="保存后只展示这一次，请交给老师本人"><div className="generated-password"><input name="password" value={form.password} onChange={change} minLength="8" required /><button type="button" onClick={() => setForm({ ...form, password: makeInitialPassword() })}>重新生成</button></div></Field></div>}</div>}<ErrorNotice error={error} /><FormActions onClose={onClose} busy={busy} label={initial ? "保存资料" : "创建老师"} /></form>;
}

function AccountForm({ kind = "teachers", who = "老师", teacher, onClose, onDone }) {
  const creating = !teacher.account; const [form, setForm] = useState({ username: "", password: makeInitialPassword() }); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  useEffect(() => { if (!creating) return; let alive = true; api(`/${kind}/username-suggestion?name=${encodeURIComponent(teacher.name)}`).then((data) => { if (alive) setForm((current) => ({ ...current, username: data.username })); }).catch(() => {}); return () => { alive = false; }; }, [creating, teacher.name]);
  const submit = async (event) => { event.preventDefault(); setBusy(true); setError(""); try { const path = creating ? `/${kind}/${teacher.id}/account` : `/${kind}/${teacher.id}/account/reset-password`; const body = creating ? form : { password: form.password }; const result = await api(path, { method: "POST", body }); onDone(creating ? `${who}账号已开通` : `${who}密码已重置`, { name: teacher.name, username: creating ? result.username : teacher.account.username, password: form.password }); onClose(); } catch (err) { setError(err.message); } finally { setBusy(false); } };
  return <form className="form-stack" onSubmit={submit}><div className="account-explainer"><b>{creating ? `为${who}开通登录权限` : `重置 @${teacher.account.username} 的密码`}</b><p>系统不会保存或显示明文密码。请将本次设置的密码安全地交给{who}本人，登录后可自行修改。</p></div>{creating && <Field label="登录用户名" hint="根据姓名自动生成；重复时自动追加数字"><input value={form.username} readOnly tabIndex="-1" placeholder="正在生成…" /></Field>}<Field label={creating ? "初始密码" : "新密码"}><div className="generated-password"><input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} minLength="8" required /><button type="button" onClick={() => setForm({ ...form, password: makeInitialPassword() })}>重新生成</button></div></Field><ErrorNotice error={error} /><FormActions onClose={onClose} busy={busy} label={creating ? "开通账号" : "重置密码"} /></form>;
}

function CredentialsCard({ credentials, onClose, who = "老师" }) {
  const [copied, setCopied] = useState(false); const text = `登录地址：${window.location.origin}\n用户名：${credentials.username}\n初始密码：${credentials.password}`;
  const copy = async () => { await navigator.clipboard.writeText(text); setCopied(true); };
  return <Modal title={`${who}登录信息已生成`} onClose={onClose}><div className="credential-card"><div className="credential-success">✓</div><p>请把以下信息交给 <b>{credentials.name}</b>。密码关闭后无法再次查看，只能重置。</p><dl><div><dt>登录地址</dt><dd>{window.location.origin}</dd></div><div><dt>用户名</dt><dd>{credentials.username}</dd></div><div><dt>初始密码</dt><dd>{credentials.password}</dd></div></dl><button className="button primary full" onClick={copy}>{copied ? "已复制" : "复制全部登录信息"}</button></div></Modal>;
}

export function TeachersPage({ notify }) {
  const [query, setQuery] = useState(""); const [modal, setModal] = useState(null); const [accountTeacher, setAccountTeacher] = useState(null); const [credentials, setCredentials] = useState(null); const [confirm, setConfirm] = useState(null); const state = useAsync(() => api(`/teachers?q=${encodeURIComponent(query)}`), [query]);
  const done = (message, loginInfo = null) => { notify(message); state.reload(); if (loginInfo) setCredentials(loginInfo); };
  const remove = async () => { try { await api(`/teachers/${confirm.id}`, { method: "DELETE" }); setConfirm(null); done("老师及其登录账号已删除"); } catch (err) { notify(err.message); setConfirm(null); } };
  return <><PageHeader eyebrow="师资档案" title="老师管理" description="统一维护老师资料、授课科目和登录账号。" action={<button className="button primary" onClick={() => setModal({})}>＋ 新增老师</button>} /><div className="toolbar"><input className="search" placeholder="搜索老师、科目或手机号" value={query} onChange={(e) => setQuery(e.target.value)} /></div><ErrorNotice error={state.error} />{!state.data ? <Loading /> : state.data.length ? <div className="entity-grid">{state.data.map((teacher) => <EntityCard key={teacher.id} title={teacher.name} subtitle={teacher.phone || "未填写电话"} badge={<span className={`badge ${teacher.account ? "success" : "neutral"}`}>{teacher.account ? "可登录" : "未开通账号"}</span>} actions={<><button className={`button mini ${teacher.account ? "secondary" : "primary"}`} onClick={() => setAccountTeacher(teacher)}>{teacher.account ? "重置密码" : "开通登录"}</button><button className="button mini secondary" onClick={() => setModal({ item: teacher })}>编辑资料</button><button className="button mini danger-ghost" onClick={() => setConfirm(teacher)}>删除</button></>}><dl className="meta-list"><div><dt>授课科目</dt><dd>{teacher.subject || "待设置"}</dd></div><div><dt>累计课程</dt><dd>{teacher.courseCount || 0} 节</dd></div><div><dt>登录用户名</dt><dd>{teacher.account ? `@${teacher.account.username}` : "尚未设置"}</dd></div></dl></EntityCard>)}</div> : <Empty title="暂无老师档案" />}{modal && <Modal title={modal.item ? "编辑老师资料" : "新增老师并开通账号"} wide={!modal.item} onClose={() => setModal(null)}><TeacherForm initial={modal.item} onClose={() => setModal(null)} onDone={done} /></Modal>}{accountTeacher && <Modal title={accountTeacher.account ? "重置老师密码" : "开通老师登录"} onClose={() => setAccountTeacher(null)}><AccountForm kind="teachers" who="老师" teacher={accountTeacher} onClose={() => setAccountTeacher(null)} onDone={done} /></Modal>}{credentials && <CredentialsCard credentials={credentials} onClose={() => setCredentials(null)} />}{confirm && <Confirm title="删除老师" text={`确定删除 ${confirm.name}？其登录账号也会一并删除；有课程的老师无法删除。`} onCancel={() => setConfirm(null)} onConfirm={remove} />}</>;
}

function StudentForm({ initial, onClose, onDone }) {
  const blank = { name: "", phone: "", email: "", gender: "", birthDate: "", school: "", grade: "", guardianName: "", guardianPhone: "", address: "", notes: "", status: "active" };
  const [form, setForm] = useState(initial ? Object.fromEntries(Object.keys(blank).map((key) => [key, initial[key] ?? blank[key]])) : { ...blank, createAccount: true, username: "", password: makeInitialPassword() }); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  useEffect(() => { if (initial || !form.createAccount) return; if (!form.name.trim()) { setForm((current) => current.username ? { ...current, username: "" } : current); return; } let alive = true; const timer = window.setTimeout(() => api(`/students/username-suggestion?name=${encodeURIComponent(form.name)}`).then((data) => { if (alive) setForm((current) => ({ ...current, username: data.username })); }).catch(() => {}), 220); return () => { alive = false; window.clearTimeout(timer); }; }, [initial, form.name, form.createAccount]);
  const change = (event) => setForm({ ...form, [event.target.name]: event.target.type === "checkbox" ? event.target.checked : event.target.value });
  const submit = async (e) => { e.preventDefault(); setBusy(true); setError(""); try { const student = await api(initial ? `/students/${initial.id}` : "/students", { method: initial ? "PUT" : "POST", body: form }); const credentials = !initial && form.createAccount ? { name: student.name, username: student.account.username, password: form.password } : null; onDone(initial ? "学生资料已更新" : "学生已添加", credentials); onClose(); } catch (err) { setError(err.message); } finally { setBusy(false); } };
  return <form className="form-stack student-profile-form" onSubmit={submit}><div className="form-section"><div className="form-section-title"><b>基本信息</b><span>学生本人资料</span></div><div className="form-grid three"><Field label="姓名"><input name="name" value={form.name} onChange={change} required /></Field><Field label="性别"><select name="gender" value={form.gender} onChange={change}><option value="">未填写</option><option>男</option><option>女</option><option>其他</option></select></Field><Field label="出生日期"><input name="birthDate" type="date" value={form.birthDate} onChange={change} /></Field></div><div className="form-grid"><Field label="学生电话"><input name="phone" value={form.phone} onChange={change} inputMode="tel" /></Field><Field label="电子邮箱"><input name="email" type="email" value={form.email} onChange={change} /></Field></div></div><div className="form-section"><div className="form-section-title"><b>学业信息</b><span>便于分班和匹配课程</span></div><div className="form-grid"><Field label="就读学校"><input name="school" value={form.school} onChange={change} /></Field><Field label="年级"><input name="grade" value={form.grade} onChange={change} placeholder="例如：初二" /></Field></div></div><div className="form-section"><div className="form-section-title"><b>监护人与联系信息</b><span>未成年学生建议完整填写</span></div><div className="form-grid"><Field label="监护人姓名"><input name="guardianName" value={form.guardianName} onChange={change} /></Field><Field label="监护人电话"><input name="guardianPhone" value={form.guardianPhone} onChange={change} inputMode="tel" /></Field></div><Field label="家庭地址"><input name="address" value={form.address} onChange={change} /></Field></div><div className="form-section"><div className="form-section-title"><b>内部管理</b><span>仅管理员可见</span></div><div className="form-grid"><Field label="档案状态"><select name="status" value={form.status} onChange={change}><option value="active">在读</option><option value="inactive">已停课</option></select></Field><Field label="内部备注"><textarea name="notes" rows="3" maxLength="1000" value={form.notes} onChange={change} placeholder="过敏情况、学习特点、需要注意的事项等" /></Field></div></div>{!initial && <div className="form-section account-section"><label className="account-toggle"><input name="createAccount" type="checkbox" checked={form.createAccount} onChange={change} /><span className="switch"></span><span><b>同时开通学生登录账号</b><small>学生可登录查看自己的课程并签到</small></span></label>{form.createAccount && <div className="account-fields"><Field label="登录用户名" hint="根据姓名自动生成；如有重复会自动追加数字"><input name="username" value={form.username} readOnly tabIndex="-1" placeholder="填写姓名后自动生成" /></Field><Field label="初始密码" hint="保存后只展示这一次，请交给学生或家长"><div className="generated-password"><input name="password" value={form.password} onChange={change} minLength="8" required /><button type="button" onClick={() => setForm({ ...form, password: makeInitialPassword() })}>重新生成</button></div></Field></div>}</div>}<ErrorNotice error={error} /><FormActions onClose={onClose} busy={busy} label="保存学生档案" /></form>;
}

export function StudentsPage({ notify }) {
  const [query, setQuery] = useState(""); const [status, setStatus] = useState("active"); const [modal, setModal] = useState(null); const [stats, setStats] = useState(null); const [confirm, setConfirm] = useState(null); const [accountStudent, setAccountStudent] = useState(null); const [credentials, setCredentials] = useState(null); const state = useAsync(() => api(`/students?q=${encodeURIComponent(query)}&status=${status}`), [query, status]);
  const done = (message, loginInfo = null) => { notify(message); state.reload(); if (loginInfo) setCredentials(loginInfo); };
  const showStats = async (student) => setStats({ student, data: await api(`/students/${student.id}/stats`) });
  const remove = async () => { await api(`/students/${confirm.id}`, { method: "DELETE" }); setConfirm(null); done("学生已删除"); };
  return <><PageHeader eyebrow="学员档案" title="学生管理" description="集中管理学生、学业、监护人和考勤资料。" action={<button className="button primary" onClick={() => setModal({})}>＋ 新增学生</button>} /><div className="toolbar"><input className="search" placeholder="搜索学生、监护人、学校或手机号" value={query} onChange={(e) => setQuery(e.target.value)} /><div className="filter-pills">{[["", "全部"], ["active", "在读"], ["inactive", "已停课"]].map(([key, label]) => <button key={key} className={status === key ? "active" : ""} onClick={() => setStatus(key)}>{label}</button>)}</div></div><ErrorNotice error={state.error} />{!state.data ? <Loading /> : state.data.length ? <div className="entity-grid student-grid">{state.data.map((student) => <EntityCard key={student.id} title={student.name} subtitle={[student.school, student.grade].filter(Boolean).join(" · ") || student.phone || "资料待完善"} badge={<span className={`badge ${student.status === "inactive" ? "neutral" : "success"}`}>{student.status === "inactive" ? "已停课" : "在读"}</span>} actions={<><button className={`button mini ${student.account ? "secondary" : "primary"}`} onClick={() => setAccountStudent(student)}>{student.account ? "重置密码" : "开通登录"}</button><button className="button mini secondary" onClick={() => setModal({ item: student })}>编辑档案</button><button className="button mini soft" onClick={() => showStats(student)}>考勤表现</button><button className="button mini danger-ghost" onClick={() => setConfirm(student)}>删除</button></>}><dl className="meta-list student-meta"><div><dt>学生电话</dt><dd>{student.phone || "未填写"}</dd></div><div><dt>监护人</dt><dd>{student.guardianName || "未填写"}</dd></div><div><dt>监护人电话</dt><dd>{student.guardianPhone || "未填写"}</dd></div><div><dt>登录账号</dt><dd>{student.account ? `@${student.account.username}` : "未开通"}</dd></div><div><dt>课程 / 签到</dt><dd>{student.courseCount || 0} / {student.checkinCount || 0}</dd></div></dl>{student.notes && <p className="student-note">{student.notes}</p>}</EntityCard>)}</div> : <Empty title="暂无匹配的学生档案" />}
    {modal && <Modal wide title={modal.item ? `编辑 ${modal.item.name} 的档案` : "新增学生档案"} onClose={() => setModal(null)}><StudentForm initial={modal.item} onClose={() => setModal(null)} onDone={done} /></Modal>}
    {stats && <Modal title={`${stats.student.name} · 考勤表现`} onClose={() => setStats(null)}><div className="student-summary"><div className="student-summary-head"><div className="avatar">{stats.student.name[0]}</div><div><b>{stats.student.name}</b><span>{[stats.student.school, stats.student.grade].filter(Boolean).join(" · ") || "未填写学校年级"}</span></div></div><div className="mini-stats"><div><b>{stats.data.total}</b><span>应到</span></div><div><b>{stats.data.signed}</b><span>实到</span></div><div><b>{stats.data.missed}</b><span>缺勤</span></div><div><b>{stats.data.rate}%</b><span>签到率</span></div></div>{stats.student.guardianName && <div className="guardian-strip"><span>监护人</span><b>{stats.student.guardianName}</b><a href={`tel:${stats.student.guardianPhone}`}>{stats.student.guardianPhone || "未填写电话"}</a></div>}</div></Modal>}
    {accountStudent && <Modal title={accountStudent.account ? "重置学生密码" : "开通学生登录"} onClose={() => setAccountStudent(null)}><AccountForm kind="students" who="学生" teacher={accountStudent} onClose={() => setAccountStudent(null)} onDone={done} /></Modal>}
    {credentials && <CredentialsCard who="学生" credentials={credentials} onClose={() => setCredentials(null)} />}
    {confirm && <Confirm title="删除学生" text={`确定删除 ${confirm.name}？其登录账号和相关课程名单也会一并删除。`} onCancel={() => setConfirm(null)} onConfirm={remove} />}</>;
}

function CourseForm({ initial, teachers, students, onClose, onDone }) {
  const [form, setForm] = useState(initial ? {
    date: initial.date, start: initial.start, end: initial.end, teacherId: initial.teacherId,
    topic: initial.topic, location: initial.location || "", studentIds: initial.studentIds || [], repeatWeeks: 1,
  } : { date: localDateKey(), start: "09:00", end: "10:00", teacherId: teachers[0]?.id || "", topic: "", location: "", studentIds: [], repeatWeeks: 1 });
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [search, setSearch] = useState(""); const [onlyChosen, setOnlyChosen] = useState(false);
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const chosen = useMemo(() => new Set(form.studentIds), [form.studentIds]);
  const keyword = search.trim().toLowerCase();
  const visible = useMemo(() => students.filter((student) => (!onlyChosen || chosen.has(student.id)) && (!keyword || [student.name, student.phone, student.school, student.grade, student.guardianName].some((value) => (value || "").toLowerCase().includes(keyword)))), [students, keyword, onlyChosen, chosen]);
  const toggle = (id) => set("studentIds", chosen.has(id) ? form.studentIds.filter((x) => x !== id) : [...form.studentIds, id]);
  const selectVisible = () => set("studentIds", [...new Set([...form.studentIds, ...visible.map((student) => student.id)])]);
  const clearVisible = () => { const hide = new Set(visible.map((student) => student.id)); set("studentIds", form.studentIds.filter((id) => !hide.has(id))); };
  const lastDate = useMemo(() => { if (!form.date || form.repeatWeeks < 2) return ""; const d = new Date(`${form.date}T00:00:00`); d.setDate(d.getDate() + 7 * (form.repeatWeeks - 1)); return localDateKey(d); }, [form.date, form.repeatWeeks]);
  const weekday = form.date ? "日一二三四五六"[new Date(`${form.date}T00:00:00`).getDay()] : "";
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const { repeatWeeks, ...single } = form;
      if (initial) await api(`/courses/${initial.id}`, { method: "PUT", body: single });
      else if (repeatWeeks > 1) await api("/courses/batch", { method: "POST", body: { ...single, repeatWeeks } });
      else await api("/courses", { method: "POST", body: single });
      onDone(initial ? "课程已更新" : repeatWeeks > 1 ? `已创建 ${repeatWeeks} 节每周课程` : "课程已创建"); onClose();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return <form className="form-stack course-form" onSubmit={submit}>
    <div className="form-section"><div className="form-section-title"><b>课程信息</b><span>主题、老师与上课地点</span></div>
      <div className="form-grid"><Field label="课程主题"><input value={form.topic} onChange={(e) => set("topic", e.target.value)} required /></Field><Field label="上课地点" hint="选填，如 201教室 / 线上"><input value={form.location} maxLength="100" onChange={(e) => set("location", e.target.value)} /></Field></div>
      <Field label="授课老师"><select value={form.teacherId} onChange={(e) => set("teacherId", e.target.value)} required><option value="">请选择</option>{teachers.map((teacher) => <option value={teacher.id} key={teacher.id}>{teacher.name} · {teacher.subject || "未设科目"}</option>)}</select></Field></div>
    <div className="form-section"><div className="form-section-title"><b>时间安排</b><span>{weekday && `首节课 周${weekday}`}</span></div>
      <div className="form-grid three"><Field label={initial ? "日期" : "首节课日期"}><input type="date" value={form.date} onChange={(e) => set("date", e.target.value)} required /></Field><Field label="开始"><input type="time" value={form.start} onChange={(e) => set("start", e.target.value)} required /></Field><Field label="结束"><input type="time" value={form.end} onChange={(e) => set("end", e.target.value)} required /></Field></div>
      {!initial && <Field label="每周重复" hint={form.repeatWeeks > 1 ? `共 ${form.repeatWeeks} 节，每周${weekday}，至 ${lastDate}；任一节与老师时间冲突则全部不创建` : "默认只创建这一节课"}><div className="repeat-row">{[1, 4, 8, 12].map((n) => <button type="button" key={n} className={form.repeatWeeks === n ? "active" : ""} onClick={() => set("repeatWeeks", n)}>{n === 1 ? "不重复" : `${n} 周`}</button>)}<input type="number" min="1" max="52" value={form.repeatWeeks} onChange={(e) => set("repeatWeeks", Math.min(52, Math.max(1, Number(e.target.value) || 1)))} aria-label="重复周数" /></div></Field>}</div>
    <div className="form-section"><div className="form-section-title"><b>上课学生</b><span>已选 {form.studentIds.length} / 共 {students.length} 人</span></div>
      <div className="student-picker"><div className="picker-tools"><input className="search" placeholder="搜索姓名、电话、学校、年级、家长" value={search} onChange={(e) => setSearch(e.target.value)} /><label className="picker-only"><input type="checkbox" checked={onlyChosen} onChange={(e) => setOnlyChosen(e.target.checked)} />只看已选</label></div>
        <div className="picker-bulk"><button type="button" onClick={selectVisible} disabled={!visible.length}>全选当前 {visible.length} 人</button><button type="button" onClick={clearVisible} disabled={!visible.length}>取消当前</button><button type="button" onClick={() => set("studentIds", [])} disabled={!form.studentIds.length}>清空已选</button></div>
        <div className="picker-list">{visible.length ? visible.map((student) => <label key={student.id} className={chosen.has(student.id) ? "checked" : ""}><input type="checkbox" checked={chosen.has(student.id)} onChange={() => toggle(student.id)} /><span><b>{student.name}</b><small>{[student.school, student.grade].filter(Boolean).join(" · ") || student.phone || "资料待完善"}</small></span></label>) : <div className="picker-empty">{students.length ? "没有匹配的学生" : "还没有在读学生，请先到学生管理添加"}</div>}</div></div></div>
    <ErrorNotice error={error} /><FormActions onClose={onClose} busy={busy} label={initial ? "保存修改" : form.repeatWeeks > 1 ? `创建 ${form.repeatWeeks} 节课程` : "创建课程"} />
  </form>;
}

export function CoursesPage({ notify }) {
  const [teacherId, setTeacherId] = useState(""); const [modal, setModal] = useState(null); const [confirm, setConfirm] = useState(null);
  const resources = useAsync(async () => { const [courses, teachers, students] = await Promise.all([api(`/courses/all`), api("/teachers"), api("/students?status=active")]); return { courses, teachers, students }; }, []);
  const byDate = useMemo(() => buildByDate((resources.data?.courses || []).filter((course) => !teacherId || course.teacherId === teacherId)), [resources.data, teacherId]);
  const done = (message) => { notify(message); resources.reload(); };
  const action = async (course, type) => { await api(`/courses/${course.id}/${type}`, { method: "POST" }); done(type === "cancel" ? "课程已取消" : "课程已恢复"); };
  const remove = async () => { await api(`/courses/${confirm.id}`, { method: "DELETE" }); setConfirm(null); done("课程已删除"); };
  const renderCourse = (course) => <article className={`day-course admin-course${course.canceled ? " is-canceled" : ""}`} key={course.id}>
    <div className="day-course-time"><b>{course.start}</b><span>{course.end}</span></div>
    <div className="day-course-main"><h3>{course.topic} {course.canceled && <span className="badge danger">已取消</span>}</h3><p>{[course.teacherName, course.location].filter(Boolean).join(" · ") || "未排老师"} · {course.studentIds.length} 名学生 · 已签到 {course.signedCount}</p>
      <div className="day-course-actions">{course.canceled ? <button className="button mini soft" onClick={() => action(course, "restore")}>恢复</button> : <><button className="button mini secondary" onClick={() => setModal({ item: course })}>编辑</button><button className="button mini danger-ghost" onClick={() => action(course, "cancel")}>取消</button></>}<button className="button mini danger-ghost" onClick={() => setConfirm(course)}>删除</button></div>
    </div>
  </article>;
  return <><PageHeader eyebrow="课程运营" title="排课管理" description="日历中查看与管理每天的课程；系统会自动拦截老师时间冲突。" action={<button className="button primary" onClick={() => setModal({})}>＋ 新建课程</button>} /><div className="toolbar"><select value={teacherId} onChange={(e) => setTeacherId(e.target.value)}><option value="">全部老师</option>{resources.data?.teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.name}</option>)}</select>{teacherId && <button className="button secondary mini" onClick={() => setTeacherId("")}>清空筛选</button>}</div><ErrorNotice error={resources.error} />
    {!resources.data ? <Loading /> : <CalendarView byDate={byDate} today={localDateKey()} renderCourse={renderCourse} emptyTitle="这一天没有排课" activeOnly />}
    {modal && resources.data && <Modal wide title={modal.item ? "编辑课程" : "新建课程"} onClose={() => setModal(null)}><CourseForm initial={modal.item} teachers={resources.data.teachers} students={resources.data.students} onClose={() => setModal(null)} onDone={done} /></Modal>}
    {confirm && <Confirm title="彻底删除课程" text={`确定删除「${confirm.topic}」及其签到记录？通常建议使用“取消课程”。`} onCancel={() => setConfirm(null)} onConfirm={remove} />}</>;
}

export function AttendancePage({ user, notify }) {
  const coursesState = useAsync(() => api(user.role === "admin" ? "/courses/all" : "/courses"), [user.role]); const [selected, setSelected] = useState(""); const [attendance, setAttendance] = useState(null); const [error, setError] = useState("");
  useEffect(() => { if (!selected) { setAttendance(null); return; } api(`/courses/${selected}/attendance`).then(setAttendance).catch((err) => setError(err.message)); }, [selected]);
  const refresh = async () => setAttendance(await api(`/courses/${selected}/attendance`));
  const sign = async (studentId) => { await api("/checkins", { method: "POST", body: { courseId: selected, studentId } }); notify("已代签"); refresh(); };
  const revoke = async (studentId) => { await api(`/checkins/${selected}/${studentId}`, { method: "DELETE" }); notify("签到已撤销"); refresh(); };
  return <><PageHeader eyebrow="到课管理" title="签到查询" description={user.role === "teacher" ? "查看自己课程的签到情况，并处理代签或纠错。" : "选择课程查看已签到与未签到学生。"} /><div className="toolbar"><select className="course-select" value={selected} onChange={(e) => setSelected(e.target.value)}><option value="">请选择一节课程</option>{coursesState.data?.filter((course) => !course.canceled).map((course) => <option key={course.id} value={course.id}>{course.date} {course.start} · {course.topic}</option>)}</select>{selected && <button className="button secondary" onClick={() => downloadCsv(`/courses/${selected}/export.csv`, `attendance-${selected}.csv`)}>导出 CSV</button>}</div><ErrorNotice error={coursesState.error || error} />
    {!selected ? <Empty title="先选择课程" text="选择后会显示完整的签到名单。" /> : !attendance ? <Loading /> : <><section className="attendance-summary"><div><b>{attendance.signedCount}</b><span>已签到</span></div><div><b>{attendance.total - attendance.signedCount}</b><span>未签到</span></div><div><b>{attendance.total ? Math.round(attendance.signedCount / attendance.total * 100) : 0}%</b><span>签到率</span></div></section><div className="attendance-columns"><section className="panel"><div className="panel-head"><h2>已签到</h2><span className="count-pill success">{attendance.signed.length}</span></div><div className="people-list">{attendance.signed.map((student) => <div key={student.id}><div className="avatar small">{student.name[0]}</div><div><b>{student.name}</b><span>{student.phone || "无电话"}</span></div><button className="button mini danger-ghost" onClick={() => revoke(student.id)}>撤销</button></div>)}</div></section><section className="panel"><div className="panel-head"><h2>未签到</h2><span className="count-pill warning">{attendance.unsigned.length}</span></div><div className="people-list">{attendance.unsigned.map((student) => <div key={student.id}><div className="avatar small muted-avatar">{student.name[0]}</div><div><b>{student.name}</b><span>{student.phone || "无电话"}</span></div><button className="button mini soft" onClick={() => sign(student.id)}>代签</button></div>)}</div></section></div></>}
  </>;
}

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];
const courseStart = (course) => new Date(`${course.date}T${course.start}:00`);
const courseEnd = (course) => new Date(`${course.date}T${course.end}:00`);

function nextCourse(courses, now) {
  return courses
    .filter((course) => courseEnd(course) >= now)
    .sort((a, b) => courseStart(a) - courseStart(b))[0] || null;
}

function relativeLabel(course, now) {
  const start = courseStart(course);
  if (now >= start && now <= courseEnd(course)) return { text: "正在上课", tone: "live" };
  const todayKey = localDateKey(now);
  const tomorrowKey = localDateKey(new Date(now.getTime() + 86400000));
  if (course.date === todayKey) {
    const minutes = Math.round((start - now) / 60000);
    if (minutes <= 0) return { text: "即将开始", tone: "soon" };
    if (minutes < 60) return { text: `${minutes} 分钟后`, tone: "soon" };
    const h = Math.floor(minutes / 60); const m = minutes % 60;
    return { text: `今天 · 还有 ${h} 小时${m ? ` ${m} 分` : ""}`, tone: "soon" };
  }
  if (course.date === tomorrowKey) return { text: "明天", tone: "upcoming" };
  const weekday = WEEKDAYS[new Date(`${course.date}T00:00:00`).getDay()];
  return { text: `${Number(course.date.slice(5, 7))}月${Number(course.date.slice(8, 10))}日 周${weekday}`, tone: "upcoming" };
}

function NextClassCard({ course, now, user, signed, onSign }) {
  const info = relativeLabel(course, now);
  return <article className={`next-class ${info.tone}`}>
    <div className="next-class-head"><span className="eyebrow">下一节课</span><span className="next-chip">{info.text}</span></div>
    <h2>{course.topic}</h2>
    <div className="next-class-meta"><span>🕑 {course.date} {course.start}–{course.end}</span>{course.location && <span>📍 {course.location}</span>}{course.teacherName && <span>👩‍🏫 {course.teacherName}</span>}</div>
    {user.role === "student" && <button className="button primary full" disabled={signed || info.tone !== "live" && info.tone !== "soon"} onClick={() => onSign(course)}>{signed ? "已签到 ✓" : info.tone === "live" || info.tone === "soon" ? "立即签到" : "未到签到时间"}</button>}
  </article>;
}

function buildByDate(courses) {
  const map = {};
  courses.forEach((course) => { (map[course.date] = map[course.date] || []).push(course); });
  Object.values(map).forEach((list) => list.sort((a, b) => a.start.localeCompare(b.start)));
  return map;
}

function CalendarView({ byDate, today, renderCourse, emptyTitle = "这一天没有课程", activeOnly = false }) {
  const [cursor, setCursor] = useState(() => { const [y, m] = today.split("-").map(Number); return { y, m: m - 1 }; });
  const [selected, setSelected] = useState(today);
  const startPad = new Date(cursor.y, cursor.m, 1).getDay();
  const daysInMonth = new Date(cursor.y, cursor.m + 1, 0).getDate();
  const keyFor = (d) => `${cursor.y}-${String(cursor.m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  const move = (delta) => { const total = cursor.m + delta; setCursor({ y: cursor.y + Math.floor(total / 12), m: ((total % 12) + 12) % 12 }); };
  const cells = [...Array(startPad).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];
  const dayCourses = byDate[selected] || [];
  const dotCount = (key) => (byDate[key] || []).filter((c) => !activeOnly || !c.canceled).length;
  return <section className="panel calendar-panel">
    <div className="cal-head"><button type="button" className="cal-nav" onClick={() => move(-1)} aria-label="上个月">‹</button><b>{cursor.y} 年 {cursor.m + 1} 月</b><button type="button" className="cal-nav" onClick={() => move(1)} aria-label="下个月">›</button></div>
    <div className="cal-weekrow">{WEEKDAYS.map((w) => <span key={w}>{w}</span>)}</div>
    <div className="cal-grid">{cells.map((d, i) => { if (!d) return <span key={`p${i}`} className="cal-cell empty" />; const key = keyFor(d); const count = dotCount(key); return <button type="button" key={key} className={`cal-cell${key === today ? " today" : ""}${key === selected ? " active" : ""}${count ? " has" : ""}`} onClick={() => setSelected(key)}><span>{d}</span>{count > 0 && <i className="cal-dot" />}</button>; })}</div>
    <div className="cal-day">
      <div className="cal-day-head"><b>{Number(selected.slice(5, 7))}月{Number(selected.slice(8, 10))}日 周{WEEKDAYS[new Date(`${selected}T00:00:00`).getDay()]}</b><span>{dayCourses.length ? `${dayCourses.length} 节课` : "没有课程"}</span></div>
      {dayCourses.length ? <div className="cal-day-list">{dayCourses.map(renderCourse)}</div> : <Empty title={emptyTitle} text="点选上方其他日期查看。" />}
    </div>
  </section>;
}

function UpcomingList({ courses, now }) {
  const items = courses.filter((course) => courseEnd(course) >= now).sort((a, b) => courseStart(a) - courseStart(b)).slice(0, 6);
  if (!items.length) return null;
  return <section className="panel upcoming-panel"><div className="panel-head"><div><span className="eyebrow">接下来</span><h2>后续课程</h2></div><span className="count-pill">{items.length}</span></div>
    <div className="upcoming-list">{items.map((course) => <div className="upcoming-row" key={course.id}><div className="upcoming-date"><b>{Number(course.date.slice(5, 7))}/{Number(course.date.slice(8, 10))}</b><span>周{WEEKDAYS[new Date(`${course.date}T00:00:00`).getDay()]}</span></div><div className="upcoming-info"><b>{course.topic}</b><small>{course.start}–{course.end}{course.location ? ` · ${course.location}` : ""}{course.teacherName ? ` · ${course.teacherName}` : ""}</small></div></div>)}</div>
  </section>;
}

export function MyCoursesPage({ user, notify }) {
  const state = useAsync(() => api("/courses"), []);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const timer = window.setInterval(() => setNow(new Date()), 60000); return () => window.clearInterval(timer); }, []);
  const courses = useMemo(() => (state.data || []).filter((course) => !course.canceled), [state.data]);
  const byDate = useMemo(() => buildByDate(courses), [courses]);
  const upcoming = useMemo(() => nextCourse(courses, now), [courses, now]);
  const future = useMemo(() => courses.filter((course) => courseEnd(course) >= now), [courses, now]);
  const signed = (course) => course.signedStudentIds?.includes(user.link_id);
  const sign = async (course) => { try { await api("/checkins", { method: "POST", body: { courseId: course.id } }); notify("签到成功"); state.reload(); } catch (err) { notify(err.message); } };
  const renderCourse = (course) => { const done = signed(course); return <article className="day-course" key={course.id}><div className="day-course-time"><b>{course.start}</b><span>{course.end}</span></div><div className="day-course-main"><h3>{course.topic}</h3><p>{[course.location, course.teacherName].filter(Boolean).join(" · ") || "—"}</p>{user.role === "teacher" && <small>已签到 {course.signedCount} / {course.studentIds.length}</small>}</div>{user.role === "student" ? <button className="button mini primary" disabled={done} onClick={() => sign(course)}>{done ? "已签 ✓" : "签到"}</button> : <span className={`badge ${done ? "success" : "info"}`}>{done ? "已签" : "待上"}</span>}</article>; };
  const hasSide = Boolean(upcoming) || future.length > 0;
  return <><PageHeader eyebrow={user.role === "teacher" ? "授课安排" : "学习安排"} title={user.role === "teacher" ? "我的课表" : "我的课程"} description={user.role === "teacher" ? "日历中查看每天的授课安排。" : "日历中查看每天的课程，到课后点击签到。"} /><ErrorNotice error={state.error} />
    {!state.data ? <Loading /> : courses.length ? <div className={`schedule-layout${hasSide ? "" : " solo"}`}>{hasSide && <div className="schedule-side">{upcoming && <NextClassCard course={upcoming} now={now} user={user} signed={signed(upcoming)} onSign={sign} />}<UpcomingList courses={courses} now={now} /></div>}<CalendarView byDate={byDate} today={localDateKey()} renderCourse={renderCourse} /></div> : <Empty title="暂时没有课程" text="管理员排课后会自动显示在这里。" />}</>;
}

function UserForm({ onClose, onDone }) {
  const [form, setForm] = useState({ username: "", password: "", name: "", role: "admin" }); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const submit = async (e) => { e.preventDefault(); setBusy(true); setError(""); try { await api("/users", { method: "POST", body: form }); onDone("管理员账号已创建"); onClose(); } catch (err) { setError(err.message); } finally { setBusy(false); } };
  return <form className="form-stack" onSubmit={submit}><div className="account-explainer"><b>仅用于创建机构管理员</b><p>老师和学生账号请在「老师」「学生」档案里开通，角色创建后不可更改。</p></div><div className="form-grid"><Field label="用户名"><input name="username" value={form.username} onChange={change} minLength="3" maxLength="32" required /></Field><Field label="姓名"><input name="name" value={form.name} onChange={change} required /></Field></div><Field label="初始密码" hint="至少 8 位"><input name="password" type="password" minLength="8" value={form.password} onChange={change} required /></Field><ErrorNotice error={error} /><FormActions onClose={onClose} busy={busy} label="创建管理员" /></form>;
}

export function UsersPage({ user, notify }) {
  const state = useAsync(() => api("/users"), []); const [createOpen, setCreateOpen] = useState(false); const [passwordUser, setPasswordUser] = useState(null); const [confirm, setConfirm] = useState(null);
  const done = (message) => { notify(message); state.reload(); };
  const resetPassword = async (event) => { event.preventDefault(); const password = new FormData(event.currentTarget).get("password"); try { await api(`/users/${passwordUser.id}/reset-password`, { method: "POST", body: { password } }); setPasswordUser(null); notify("密码已重置"); } catch (err) { notify(err.message); } };
  const remove = async () => { try { await api(`/users/${confirm.id}`, { method: "DELETE" }); setConfirm(null); done("管理员账号已删除"); } catch (err) { setConfirm(null); notify(err.message); } };
  return <><PageHeader eyebrow="访问控制" title="管理员账号" description="管理员、老师、学生是三个固定角色。这里只维护管理员；老师、学生账号在各自档案中开通。" action={<button className="button primary" onClick={() => setCreateOpen(true)}>＋ 新增管理员</button>} /><ErrorNotice error={state.error} />{!state.data ? <Loading /> : <div className="table-shell"><table><thead><tr><th>姓名</th><th>用户名</th><th>角色</th><th>操作</th></tr></thead><tbody>{state.data.map((item) => <tr key={item.id}><td><b>{item.name || "—"}</b>{item.id === user.id && <span className="badge info self-tag">当前登录</span>}</td><td>{item.username}</td><td>{roleName[item.role]}</td><td><div className="row-actions"><button className="button mini secondary" onClick={() => setPasswordUser(item)}>重置密码</button>{item.id !== user.id && <button className="button mini danger-ghost" onClick={() => setConfirm(item)}>删除</button>}</div></td></tr>)}</tbody></table></div>}
    {createOpen && <Modal title="新增管理员" onClose={() => setCreateOpen(false)}><UserForm onClose={() => setCreateOpen(false)} onDone={done} /></Modal>}
    {passwordUser && <Modal title={`重置 ${passwordUser.username} 的密码`} onClose={() => setPasswordUser(null)}><form className="form-stack" onSubmit={resetPassword}><Field label="新密码" hint="至少 8 位"><input name="password" type="password" minLength="8" required /></Field><FormActions onClose={() => setPasswordUser(null)} label="重置密码" /></form></Modal>}
    {confirm && <Confirm title="删除管理员" text={`确定删除管理员账号 ${confirm.username}？`} onCancel={() => setConfirm(null)} onConfirm={remove} />}</>;
}
