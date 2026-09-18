import { Link, NavLink, Outlet } from "react-router-dom";

function Layout() {
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="site-header">
        <Link className="site-name" to="/">
          Accessibility Fix Assistant
        </Link>
        <nav aria-label="Main">
          <NavLink to="/" end>
            New scan
          </NavLink>
          <NavLink to="/evaluation">Evaluation</NavLink>
        </nav>
      </header>
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
    </>
  );
}

export default Layout;
