// Caixa de aviso. tone: "info" | "erro" | "atencao".
export default function Notice({ tone = "info", title, children, action }) {
  return (
    <div className={`notice notice-${tone}`} role={tone === "erro" ? "alert" : "status"}>
      <div>
        {title && <strong>{title}</strong>}
        {children && <div className="notice-body">{children}</div>}
      </div>
      {action}
    </div>
  );
}
