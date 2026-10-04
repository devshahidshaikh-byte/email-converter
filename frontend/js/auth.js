
/*
 * Frontend account helper.
 *
 * The real authentication is done by FastAPI + SQLite. This file only:
 * 1. asks the backend who is logged in,
 * 2. keeps the CSRF token for safe account/admin actions,
 * 3. updates the UI,
 * 4. provides a sign-out button.
 */

const Auth = {
  user: null,
  csrfToken: "",

  async load() {
    const response = await fetch(apiUrl("/api/auth/me"), { credentials: "include" });

    if (!response.ok) {
      window.location.href = "/login";
      return null;
    }

    const data = await response.json();
    this.user = data.user;
    this.csrfToken = data.csrf_token;

    // sessionStorage is intentionally used only for UI/session metadata.
    // The actual login session remains in the HttpOnly cookie.
    sessionStorage.setItem("csrf_token", this.csrfToken);
    sessionStorage.setItem("user", JSON.stringify(this.user));

    this.render();
    return this.user;
  },

  render() {
    const pill = document.getElementById("accountPill");
    const adminLink = document.getElementById("adminLink");
    const logoutBtn = document.getElementById("logoutBtn");
    const locked = document.getElementById("privateLocked");
    const open = document.getElementById("privateOpen");
    const bulk = document.getElementById("bulkSection");

    if (!this.user) return;

    if (pill) {
      pill.textContent = this.user.email;
      pill.title = this.user.role === "admin" ? "Administrator" : "Signed-in user";
    }

    if (adminLink && this.user.role === "admin") {
      adminLink.classList.remove("hidden");
    }

    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => this.logout());
    }

    // This is the visible private feature gate.
    // The backend ALSO checks approval, so changing JavaScript cannot bypass it.
    const privateAccess = Boolean(this.user.private_access);
    if (locked) locked.classList.toggle("hidden", privateAccess);
    if (open) open.classList.toggle("hidden", !privateAccess);
    if (bulk) bulk.classList.toggle("hidden", !privateAccess);
  },

  async logout() {
    try {
      await fetch(apiUrl("/api/auth/logout"), {
        method: "POST",
        headers: { "X-CSRF-Token": this.csrfToken },
        credentials: "include"
      });
    } finally {
      sessionStorage.clear();
      window.location.href = "/login";
    }
  }
};

// Load the account before the generator becomes usable.
Auth.load();
