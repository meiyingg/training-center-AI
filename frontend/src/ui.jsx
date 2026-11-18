import { useEffect } from "react";

export function Modal({ title, children, onClose, wide = false }) {
  useEffect(() => {
    const close = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="sheet-handle" aria-hidden="true"></div>
        <div className="modal-head"><div><span className="eyebrow">操作面板</span><h2>{title}</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭">×</button></div>
        {children}
      </section>
    </div>
  );
}

export function Confirm({ title, text, onCancel, onConfirm, busy }) {
  return <Modal title={title} onClose={onCancel}>
    <p className="modal-copy">{text}</p>
    <div className="modal-actions"><button className="button secondary" onClick={onCancel}>取消</button><button className="button danger" disabled={busy} onClick={onConfirm}>{busy ? "处理中…" : "确认"}</button></div>
  </Modal>;
}

export function Field({ label, children, hint }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>;
}

export function PageHeader({ eyebrow, title, description, action }) {
  return <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</header>;
}

export function Empty({ title = "暂无数据", text = "完成第一条记录后，这里会自动更新。" }) {
  return <div className="empty"><div className="empty-icon">◇</div><h3>{title}</h3><p>{text}</p></div>;
}

export function Loading() {
  return <div className="loading"><span></span><span></span><span></span></div>;
}

export function ErrorNotice({ error }) {
  return error ? <div className="error-notice" role="alert">{error}</div> : null;
}

export const roleName = { admin: "管理员", teacher: "老师", student: "学生" };
export const fmtDate = (date) => date || "—";
