import Button from "./Button.jsx";
import Icon from "./Icon.jsx";

function ErrorState({ title, message, onRetry, retrying = false }) {
  return (
    <div className="state state--error">
      <Icon name="alert" size={20} className="state__icon" />
      <p className="state__title">{title}</p>
      {message ? <p className="state__body">{message}</p> : null}
      {onRetry ? (
        <div className="state__actions">
          <Button variant="secondary" onClick={onRetry} loading={retrying}>
            Try again
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export default ErrorState;
