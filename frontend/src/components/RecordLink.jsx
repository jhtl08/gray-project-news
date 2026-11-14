/**
 * A record title. With a URL it is a real link with a new-tab hint. Without
 * one it is plain text, so it never looks or behaves like a link that goes
 * nowhere.
 */
function RecordLink({ href, className = "record-title", children }) {
  if (!href) {
    return <span className={`${className} ${className}--plain`}>{children}</span>;
  }

  return (
    <a className={className} href={href} target="_blank" rel="noopener noreferrer">
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

export default RecordLink;
