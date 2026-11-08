import { useEffect } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { clearToken, getToken } from "../api.js";

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const signedIn = Boolean(getToken());

  // start each page at the top (unless the link points to a section)
  useEffect(() => {
    if (!location.hash) window.scrollTo(0, 0);
  }, [location.pathname, location.hash]);

  function signOut() {
    clearToken();
    navigate("/");
  }

  return (
    <>
      <header className="site-header">
        <Link className="brand" to="/" aria-label="Support Agent AI, home">
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
          </span>
          Support Agent AI
        </Link>
        <nav className="nav" aria-label="Main">
          <a href="/#what">What it does</a>
          <a href="/#how">How it works</a>
          {signedIn ? (
            <>
              <Link className="nav-keep" to="/dashboard">
                Dashboard
              </Link>
              <button type="button" className="link-button" onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link className="nav-keep" to="/login">
                Sign in
              </Link>
              <Link className="button button-small" to="/register">
                Try our services
              </Link>
            </>
          )}
        </nav>
      </header>

      <Outlet />

      <footer className="site-footer">
        <span>© 2026 Support Agent AI</span>
        <a href="mailto:hello@supportagent.ai">hello@supportagent.ai</a>
      </footer>
    </>
  );
}