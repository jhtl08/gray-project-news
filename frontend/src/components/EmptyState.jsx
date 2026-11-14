function EmptyState({ title, children, action }) {
  return (
    <div className="state">
      <p className="state__title">{title}</p>
      {children ? <p className="state__body">{children}</p> : null}
      {action ? <div className="state__actions">{action}</div> : null}
    </div>
  );
}

export default EmptyState;
