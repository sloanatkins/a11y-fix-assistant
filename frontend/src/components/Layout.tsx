import { Link, NavLink, Outlet } from "react-router-dom";
import { isDemoMode } from "../demo";

function Layout() {
  const demo = isDemoMode();

  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="rail">
        <Link className="wordmark" to="/">
          Accessibility Fix Assistant
        </Link>
        <nav aria-label="Main">
          <NavLink to="/" end>
            {demo ? "Examples" : "New scan"}
          </NavLink>
          <NavLink to="/evaluation">Evaluation</NavLink>
        </nav>
        <p className="rail-note">
          A clean scan doesn&apos;t prove a page is accessible. Automated tools miss problems that
          need a person to judge.
        </p>
      </header>
      <main id="main-content" tabIndex={-1}>
        {demo && (
          <p className="demo-banner">
            Demo with saved results. These sites are fictional, and your clicks reset when you
            refresh.
          </p>
        )}
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default Layout;
