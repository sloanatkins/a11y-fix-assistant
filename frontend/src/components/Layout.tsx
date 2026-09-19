import { Link, NavLink, Outlet } from "react-router-dom";

function Layout() {
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
            New scan
          </NavLink>
          <NavLink to="/evaluation">Evaluation</NavLink>
        </nav>
        <p className="rail-note">
          A clean scan doesn&apos;t prove a page is accessible. Automated tools miss problems that
          need a person to judge.
        </p>
      </header>
      <main id="main-content" tabIndex={-1}>
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export default Layout;
