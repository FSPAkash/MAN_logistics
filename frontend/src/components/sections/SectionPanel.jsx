export function SectionPanel({ title, subtitle, children, className = "" }) {
  return (
    <section className={`section-panel glass-normal ${className}`.trim()}>
      {title ? (
        <div className="section-head">
          <h1>{title}</h1>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}
