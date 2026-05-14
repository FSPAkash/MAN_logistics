import { useState } from "react";
import fsLogo from "../assets/FS.png";

const DEMO_USER = "demo";
const DEMO_PASS = "fs1234";

export function Login({ onAuth }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (username.trim() === DEMO_USER && password === DEMO_PASS) {
      sessionStorage.setItem("man_auth", "1");
      setError("");
      onAuth();
    } else {
      setError("Invalid credentials.");
    }
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">MAN Logistics</div>
        <div className="login-sub">Sign in to demo console</div>
        <label className="login-field">
          <span>Username</span>
          <input
            type="text"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
        <label className="login-field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error ? <div className="login-error">{error}</div> : null}
        <button type="submit" className="btn-primary login-submit">
          Sign in
        </button>
        <div className="login-powered">
          <span>Powered by</span>
          <img src={fsLogo} alt="Findability Sciences" />
        </div>
      </form>
    </div>
  );
}
