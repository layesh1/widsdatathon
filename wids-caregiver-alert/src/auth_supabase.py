"""
auth_supabase.py — Supabase-backed authentication for WiDS Wildfire Dashboard
49ers Intelligence Lab · WiDS Datathon 2025

Matches existing schema exactly:
  public.users                  — custom user table (password_hash / password_salt)
  public.user_events            — audit / navigation log
  public.evacuation_plans       — per-user jsonb plan (PK = username)
  public.caregiver_access_codes — DB-managed caregiver invite codes
  public.evacuation_status      — status CHECK IN ('Evacuated', 'Not Evacuated')
  public.evacuation_changelog   — new_status CHECK IN ('Evacuated', 'Not Evacuated')

Staff access codes (hardcoded, share only with staff):
  Emergency Worker / Dispatcher  →  DISPATCH-2025
  Data Analyst                   →  ANALYST-WiDS9

Caregiver signup is open to all community members (no code required).
An optional caregiver invite code (e.g. EVAC-DEMO2025 from caregiver_access_codes)
marks the account as caregiver_verified = true.

Test accounts — easiest to create via the signup UI, or see SQL snippet at EOF.
  caregiver_test  / WiDS@2025! / Caregiver/Evacuee
  dispatcher_test / WiDS@2025! / Emergency Worker   (code: DISPATCH-2025)
  analyst_test    / WiDS@2025! / Data Analyst        (code: ANALYST-WiDS9)
"""

import hashlib
import os
import streamlit as st
from supabase import create_client, Client
from datetime import datetime
from pathlib import Path

# ── Staff role access codes (hardcoded — never stored in DB) ─────────────────
_STAFF_CODES = {
    "Emergency Worker": "DISPATCH-2025",
    "Data Analyst":     "ANALYST-WiDS9",
}
ROLES = ["Caregiver/Evacuee", "Emergency Worker", "Data Analyst"]

# ── Evacuation statuses — must match DB CHECK constraint exactly ─────────────
EVAC_STATUSES = ["Not Evacuated", "Evacuated"]
_STATUS_COLORS = {
    "Evacuated":     "#00cc88",
    "Not Evacuated": "#AA0000",
}


# ─────────────────────────────────────────────────────────────────────────────
# SUPABASE CLIENT
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])


# ─────────────────────────────────────────────────────────────────────────────
# PASSWORD HELPERS  (PBKDF2-HMAC-SHA256, stdlib only — no extra deps)
# ─────────────────────────────────────────────────────────────────────────────

def _generate_salt() -> str:
    return os.urandom(32).hex()


def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        iterations=260_000,
    )
    return dk.hex()


def _verify_password(password: str, salt: str, stored_hash: str) -> bool:
    return _hash_password(password, salt) == stored_hash


# ─────────────────────────────────────────────────────────────────────────────
# AUTH UI
# ─────────────────────────────────────────────────────────────────────────────

def render_auth_page(logo_paths=None):
    """
    Renders login / signup wall.
    Sets session_state: authenticated, username, role, user_id.
    Calls st.stop() if not authenticated.
    """
    if st.session_state.get("authenticated"):
        return

    # ── Google OAuth callback — handle BEFORE showing the auth form ───────────
    # Supabase redirects back with ?code=... after Google consent
    if _handle_google_oauth_callback():
        return  # rerun was called inside; st.stop() not needed

    _inject_auth_styles()

    # Center everything in a narrow middle column
    _, center, _ = st.columns([1, 2, 1])

    with center:
        if logo_paths:
            for lp in (Path(p) for p in logo_paths):
                if lp.exists():
                    _, img_col, _ = st.columns([1, 1, 1])
                    with img_col:
                        st.image(str(lp), width="stretch")
                    break

        st.markdown("<div class='auth-title'>49ers Intelligence Lab</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='auth-subtitle'>WiDS Datathon 2025 — Wildfire Caregiver Alert System</div>",
            unsafe_allow_html=True,
        )

        tab_in, tab_up = st.tabs(["Sign In", "Create Account"])
        with tab_in:
            _render_login_form()
        with tab_up:
            _render_signup_form()

    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE OAUTH  (Supabase Auth provider)
# ─────────────────────────────────────────────────────────────────────────────

def _get_app_url() -> str:
    """Return the app's base URL for OAuth redirect_to."""
    try:
        return st.secrets["APP_URL"].rstrip("/")
    except Exception:
        return "http://localhost:8501"


def _render_google_signin_button():
    """
    Shows a Google-styled OAuth button.
    Builds the Supabase OAuth URL directly — no supabase-py OAuth methods needed.
    """
    supabase_url = st.secrets.get("SUPABASE_URL", "").rstrip("/")
    if not supabase_url:
        st.info("Google sign-in: SUPABASE_URL not found in secrets. "
                f"Available keys: {list(st.secrets.keys())}")
        return
    app_url = _get_app_url()

    from urllib.parse import quote
    oauth_url = (
        f"{supabase_url}/auth/v1/authorize"
        f"?provider=google"
        f"&redirect_to={quote(app_url, safe='')}"
    )

    # Inject JS once: reads hash fragment (#access_token=...) on return from Google
    # and rewrites it to query params (?access_token=...) that Python can read.
    st.components.v1.html("""
<script>
(function() {
    if (window.location.hash && window.location.hash.indexOf('access_token') !== -1) {
        var hash = window.location.hash.substring(1);
        var params = new URLSearchParams(hash);
        var at = params.get('access_token');
        var rt = params.get('refresh_token') || '';
        if (at) {
            var newUrl = window.location.origin + window.location.pathname
                + '?g_at=' + encodeURIComponent(at)
                + (rt ? '&g_rt=' + encodeURIComponent(rt) : '');
            window.location.replace(newUrl);
        }
    }
})();
</script>
""", height=0)

    st.markdown(
        f"""<a href="{oauth_url}" style="
            display:flex;align-items:center;justify-content:center;gap:10px;
            background:#fff;color:#3c4043;border:1px solid #dadce0;border-radius:8px;
            padding:11px 16px;text-decoration:none;font-weight:500;font-size:0.9rem;
            width:100%;box-sizing:border-box;margin-bottom:4px;
            font-family:Roboto,sans-serif;
        ">
            <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
              <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z"/>
              <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2.04a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z"/>
              <path fill="#FBBC05" d="M4.5 10.48A4.8 4.8 0 0 1 4.5 7.5V5.43H1.83a8 8 0 0 0 0 7.14l2.67-2.09z"/>
              <path fill="#EA4335" d="M8.98 3.58c1.32 0 2.5.46 3.44 1.35l2.54-2.54A8 8 0 0 0 1.83 5.43L4.5 7.5a4.77 4.77 0 0 1 4.48-3.92z"/>
            </svg>
            Continue with Google
        </a>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='display:flex;align-items:center;gap:8px;margin:10px 0 12px'>"
        "<div style='flex:1;height:1px;background:rgba(128,128,128,0.2)'></div>"
        "<span style='font-size:0.75rem;opacity:0.45'>or use password</span>"
        "<div style='flex:1;height:1px;background:rgba(128,128,128,0.2)'></div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _handle_google_oauth_callback() -> bool:
    """
    Called at the top of render_auth_page.
    Checks for ?g_at= (access token rewritten from hash by our JS snippet).
    Uses the token to fetch the user from Supabase, then creates/links their
    account in our users table.
    Returns True if the callback was handled (st.rerun() was called).
    """
    import requests as _req

    access_token = st.query_params.get("g_at")
    if not access_token:
        return False

    st.query_params.clear()

    # Fetch user info directly via Supabase REST — works with any supabase-py version
    try:
        supabase_url = st.secrets["SUPABASE_URL"].rstrip("/")
        anon_key     = st.secrets["SUPABASE_ANON_KEY"]
        resp = _req.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey":        anon_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        user_data = resp.json()
    except Exception as e:
        st.error(f"Google sign-in failed — could not verify token: {e}")
        return False

    email     = user_data.get("email", "")
    meta      = user_data.get("user_metadata") or {}
    full_name = meta.get("full_name") or meta.get("name") or ""

    if not email:
        st.error("Google sign-in did not return an email address. Please try again.")
        return False

    user = _get_or_create_google_user(email, full_name)
    if not user:
        return False

    _log_event(user["username"], "LOGIN", {"method": "google_oauth"})
    st.session_state.update({
        "authenticated": True,
        "username":      user["username"],
        "role":          user["role"],
        "user_id":       user.get("id"),
    })
    st.rerun()
    return True


def _get_or_create_google_user(email: str, full_name: str) -> dict | None:
    """
    Find an existing account by email, or auto-create one for first-time
    Google sign-in users. New accounts default to Caregiver/Evacuee role.
    """
    import secrets as _secrets

    sb = get_supabase()
    try:
        res = sb.table("users").select("*").ilike("email", email).execute()
        if res.data:
            return res.data[0]

        base = email.split("@")[0].replace(".", "_").replace("-", "_").lower()[:28]
        username = base
        n = 1
        while sb.table("users").select("username").eq("username", username).execute().data:
            username = f"{base}_{n}"
            n += 1

        salt   = _generate_salt()
        hashed = _hash_password(_secrets.token_hex(32), salt)

        sb.table("users").insert({
            "username":                      username,
            "email":                         email,
            "full_name":                     full_name,
            "password_hash":                 hashed,
            "password_salt":                 salt,
            "role":                          "Caregiver/Evacuee",
            "zip_code":                      "",
            "phone":                         "",
            "caregiver_verified":            False,
            "caregiver_verification_method": "google_oauth",
            "created_at":                    datetime.utcnow().isoformat(),
        }).execute()

        _log_event(username, "SIGNUP", {"role": "Caregiver/Evacuee", "method": "google_oauth"})
        return {"username": username, "role": "Caregiver/Evacuee", "id": None}

    except Exception as e:
        st.error(f"Could not set up your account: {e}")
        return None


# ── Login ─────────────────────────────────────────────────────────────────────

def _render_login_form():
    _render_google_signin_button()

    with st.form("login_form", clear_on_submit=False):
        identifier = st.text_input("Username or email")
        password   = st.text_input("Password", type="password")
        submitted  = st.form_submit_button("Sign In", use_container_width=True)

    # ── Forgot credentials toggle ──────────────────────────────────────────────
    if st.button("Forgot username or password?", key="forgot_toggle_btn", type="secondary"):
        st.session_state["show_forgot_form"] = not st.session_state.get("show_forgot_form", False)

    if st.session_state.get("show_forgot_form"):
        _render_forgot_credentials()

    if not submitted:
        return

    if not identifier or not password:
        st.error("Please enter your username/email and password.")
        return

    sb = get_supabase()
    try:
        res = sb.table("users").select("*").eq("username", identifier).execute()
        if not res.data:
            res = sb.table("users").select("*").eq("email", identifier).execute()
        if not res.data:
            st.error("No account found with that username or email.")
            return

        user = res.data[0]
        if not _verify_password(password, user["password_salt"], user["password_hash"]):
            st.error("Incorrect password.")
            return

        # Success
        sb.table("users").update({"last_login": datetime.utcnow().isoformat()}) \
          .eq("username", user["username"]).execute()

        _log_event(user["username"], "LOGIN")
        st.session_state.update({
            "authenticated": True,
            "username":      user["username"],
            "role":          user["role"],
            "user_id":       user["id"],
        })
        st.rerun()

    except Exception as e:
        st.error(f"Sign in failed: {e}")


# ── Forgot credentials ────────────────────────────────────────────────────────

def _render_forgot_credentials():
    """Inline account recovery panel shown below the sign-in form."""
    st.markdown(
        "<div style='margin-top:4px;padding:16px 18px;"
        "background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.09);"
        "border-radius:10px'>",
        unsafe_allow_html=True,
    )
    st.markdown("**Account Recovery**")

    recovery_type = st.radio(
        "I need to:",
        ["Look up my username", "Reset my password"],
        key="recovery_type_radio",
        horizontal=True,
    )

    with st.form("forgot_form", clear_on_submit=True):
        recovery_email = st.text_input(
            "Email address on your account",
            placeholder="The email you used when signing up",
        )
        col_sub, col_cancel = st.columns([3, 1])
        with col_sub:
            recovery_submitted = st.form_submit_button(
                "Submit", use_container_width=True, type="primary"
            )
        with col_cancel:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

    if cancelled:
        st.session_state["show_forgot_form"] = False
        st.rerun()

    if recovery_submitted:
        if not recovery_email.strip():
            st.error("Please enter the email address on your account.")
        else:
            _handle_account_recovery(recovery_email.strip(), recovery_type)


def _handle_account_recovery(email: str, recovery_type: str):
    import secrets
    import string

    sb = get_supabase()
    try:
        res = (
            sb.table("users")
            .select("username")
            .ilike("email", email)
            .execute()
        )
    except Exception as e:
        st.error(f"Account recovery failed: {e}")
        return

    if not res.data:
        st.warning(
            "No account found with that email address. "
            "Check the spelling, or create a new account."
        )
        return

    username = res.data[0]["username"]

    if recovery_type == "Look up my username":
        st.success(f"Your username is: **{username}**")

    else:  # Reset password
        alphabet = string.ascii_letters + string.digits
        temp_pw  = "Tmp" + "".join(secrets.choice(alphabet) for _ in range(8))
        salt     = _generate_salt()
        hashed   = _hash_password(temp_pw, salt)

        try:
            sb.table("users").update({
                "password_hash": hashed,
                "password_salt": salt,
            }).eq("username", username).execute()
        except Exception as e:
            st.error(f"Could not reset password: {e}")
            return

        _log_event(username, "PASSWORD_RESET", {"method": "self_service"})

        st.success(f"Password reset for **{username}**. Your temporary password is:")
        st.code(temp_pw, language=None)
        st.caption(
            "Sign in with this temporary password. "
            "Update it in your account settings after logging in."
        )


# ── Signup ────────────────────────────────────────────────────────────────────

def _render_signup_form():
    role_choice = st.selectbox("Account type", ROLES, key="su_role")

    if role_choice == "Caregiver/Evacuee":
        st.markdown(
            "<div class='role-note caregiver-note'>"
            "Community accounts are open to everyone — no code required. "
            "An optional caregiver invite code (e.g. <strong>EVAC-DEMO2025</strong>) "
            "will verify your account immediately."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='role-note restricted-note'>"
            f"<strong>{role_choice}</strong> accounts require an administrator "
            f"access code. Contact your system administrator if you don't have one."
            f"</div>",
            unsafe_allow_html=True,
        )

    with st.form("signup_form", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            new_username = st.text_input("Username")
        with col_b:
            new_fullname = st.text_input("Full name (optional)")

        new_email = st.text_input("Email address")

        col_c, col_d = st.columns(2)
        with col_c:
            new_pw  = st.text_input("Password (min 8 characters)", type="password")
        with col_d:
            new_pw2 = st.text_input("Confirm password", type="password")

        if role_choice == "Caregiver/Evacuee":
            access_code = st.text_input(
                "Caregiver invite code (optional)",
                placeholder="Leave blank if you don't have one",
            )
        else:
            access_code = st.text_input(
                "Administrator access code",
                placeholder="Required — contact your administrator",
            )

        col_e, col_f = st.columns(2)
        with col_e:
            zip_code = st.text_input("ZIP code (optional)")
        with col_f:
            phone = st.text_input("Phone (optional)")

        submitted = st.form_submit_button("Create Account", use_container_width=True)

    if submitted:
        _handle_signup(
            username=new_username, email=new_email, full_name=new_fullname,
            pw=new_pw, pw2=new_pw2, role=role_choice, access_code=access_code,
            zip_code=zip_code, phone=phone,
        )


def _handle_signup(username, email, full_name, pw, pw2, role, access_code, zip_code, phone):
    if not username or not email or not pw:
        st.error("Username, email, and password are required.")
        return
    if pw != pw2:
        st.error("Passwords do not match.")
        return
    if len(pw) < 8:
        st.error("Password must be at least 8 characters.")
        return

    sb = get_supabase()
    caregiver_verified = False
    caregiver_method   = ""

    # Staff roles — validate hardcoded code
    if role in _STAFF_CODES:
        if access_code.strip() != _STAFF_CODES[role]:
            st.error("Invalid access code. Contact your system administrator.")
            return

    # Caregiver — optionally validate DB invite code
    elif role == "Caregiver/Evacuee" and access_code.strip():
        try:
            code_res = (
                sb.table("caregiver_access_codes")
                .select("id, is_active")
                .eq("code", access_code.strip())
                .eq("is_active", True)
                .execute()
            )
            if code_res.data:
                caregiver_verified = True
                caregiver_method   = "invite_code"
            else:
                st.error("That caregiver invite code is not valid or has expired.")
                return
        except Exception as e:
            st.error(f"Could not verify invite code: {e}")
            return

    # Insert user
    try:
        salt   = _generate_salt()
        hashed = _hash_password(pw, salt)

        sb.table("users").insert({
            "username":                      username,
            "email":                         email,
            "full_name":                     full_name or "",
            "password_hash":                 hashed,
            "password_salt":                 salt,
            "role":                          role,
            "zip_code":                      zip_code or "",
            "phone":                         phone or "",
            "caregiver_verified":            caregiver_verified,
            "caregiver_verification_method": caregiver_method,
            "created_at":                    datetime.utcnow().isoformat(),
        }).execute()

        _log_event(username, "SIGNUP", {"role": role})
        st.success(
            f"Account created! Sign in as **{username}**."
            + (" Your caregiver account is verified." if caregiver_verified else "")
        )

    except Exception as e:
        err = str(e).lower()
        if "duplicate" in err or "unique" in err:
            if "username" in err:
                st.error("That username is already taken.")
            elif "email" in err:
                st.error("An account with that email already exists.")
            else:
                st.error("Account already exists.")
        else:
            st.error(f"Could not create account: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR PROFILE
# ─────────────────────────────────────────────────────────────────────────────

def render_user_profile_sidebar(username: str):
    sb = get_supabase()
    try:
        p = (
            sb.table("users")
            .select("full_name, created_at, caregiver_verified")
            .eq("username", username)
            .single()
            .execute()
        )
        if p.data:
            if p.data.get("full_name"):
                st.caption(p.data["full_name"])
            joined = (p.data.get("created_at") or "")[:10]
            if joined:
                st.caption(f"Member since {joined}")
            if p.data.get("caregiver_verified"):
                st.markdown(
                    "<span style='font-size:0.72rem;background:#0d2b1e;color:#00cc88;"
                    "padding:2px 9px;border-radius:10px;border:1px solid #00cc8844'>"
                    "Verified</span>",
                    unsafe_allow_html=True,
                )
    except Exception:
        pass

    try:
        visits = (
            sb.table("user_events")
            .select("event_type, metadata, created_at")
            .eq("username", username)
            .eq("event_type", "PAGE_VISIT")
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        if visits.data:
            with st.expander("Recent activity"):
                for v in visits.data:
                    page = (v.get("metadata") or {}).get("page", "—")
                    ts   = (v.get("created_at") or "")[:16].replace("T", "  ")
                    st.caption(f"{page}  ·  {ts}")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# EVENT LOGGING  →  public.user_events
# ─────────────────────────────────────────────────────────────────────────────

def _log_event(username: str, event_type: str, metadata: dict = None):
    try:
        get_supabase().table("user_events").insert({
            "username":   username,
            "event_type": event_type,
            "metadata":   metadata or {},
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception:
        pass


def log_page_visit(username: str, page: str):
    _log_event(username, "PAGE_VISIT", {"page": page})


def sign_out(username: str):
    _log_event(username, "LOGOUT")
    for k in list(st.session_state.keys()):
        del st.session_state[k]


# ─────────────────────────────────────────────────────────────────────────────
# EVACUATION PLAN  →  public.evacuation_plans  (PK = username)
# ─────────────────────────────────────────────────────────────────────────────

def get_evacuation_plan(username: str):
    try:
        res = (
            get_supabase()
            .table("evacuation_plans")
            .select("plan_data")
            .eq("username", username)
            .single()
            .execute()
        )
        return res.data.get("plan_data") if res.data else None
    except Exception:
        return None


def save_evacuation_plan(username: str, plan_data: dict) -> bool:
    try:
        get_supabase().table("evacuation_plans").upsert(
            {"username": username, "plan_data": plan_data,
             "updated_at": datetime.utcnow().isoformat()},
            on_conflict="username",
        ).execute()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# EVACUATION STATUS  →  public.evacuation_status
# status CHECK IN ('Evacuated', 'Not Evacuated')
# ─────────────────────────────────────────────────────────────────────────────

def _upsert_evac_status(reporter_username: str, person_name: str,
                        status: str, note: str = "") -> bool:
    if status not in EVAC_STATUSES:
        return False
    sb  = get_supabase()
    now = datetime.utcnow().isoformat()
    try:
        # Fetch previous status for changelog
        old_res = (
            sb.table("evacuation_status")
            .select("status")
            .eq("reporter_username", reporter_username)
            .eq("person_name", person_name)
            .execute()
        )
        old_status = old_res.data[0]["status"] if old_res.data else None

        # Upsert
        sb.table("evacuation_status").upsert(
            {
                "reporter_username": reporter_username,
                "person_name":       person_name,
                "status":            status,
                "note":              note,
                "updated_at":        now,
            },
            on_conflict="reporter_username,person_name",
        ).execute()

        # Changelog (only on actual change, skip gracefully if schema differs)
        if old_status != status:
            try:
                sb.table("evacuation_changelog").insert({
                    "reporter_username": reporter_username,
                    "person_name":       person_name,
                    "old_status":        old_status,
                    "new_status":        status,
                    "note":              note,
                    "changed_at":        now,
                }).execute()
            except Exception:
                pass  # changelog is non-critical

        return True
    except Exception:
        return False


def get_tracked_persons(reporter_username: str) -> list:
    try:
        res = (
            get_supabase()
            .table("evacuation_status")
            .select("*")
            .eq("reporter_username", reporter_username)
            .order("updated_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def render_evacuation_status_widget(username: str):
    """
    Full evacuation status widget — update YOUR OWN status or a MONITORED PERSON.

    Status values are binary to match the DB CHECK constraint:
      'Evacuated' | 'Not Evacuated'

    Usage in caregiver_start_page.py:
        from auth_supabase import render_evacuation_status_widget
        render_evacuation_status_widget(st.session_state.username)
    """
    st.markdown("### Update Evacuation Status")
    st.caption(
        "Report your own evacuation status or update someone you are monitoring. "
        "Emergency dispatchers can see these updates in real time."
    )

    update_for = st.radio(
        "Updating status for:",
        ["Myself", "Someone I am monitoring"],
        horizontal=True,
        key="evac_update_for",
    )

    if update_for == "Myself":
        person_name = username
        st.caption(f"Reporting as: **{username}**")
    else:
        person_name = st.text_input(
            "Person's name or identifier",
            placeholder="e.g. Mom, John Smith, Unit 4B",
            key="evac_monitored_person",
        )

    col_left, col_right = st.columns([1, 2])
    with col_left:
        status = st.radio("Status", EVAC_STATUSES, key="evac_status_radio")
        color  = _STATUS_COLORS.get(status, "#8892a4")
        st.markdown(
            f"<div style='padding:6px 12px;background:{color}22;"
            f"border:1px solid {color}66;border-radius:8px;color:{color};"
            f"font-weight:600;font-size:0.85rem;text-align:center;margin-top:4px'>"
            f"{status}</div>",
            unsafe_allow_html=True,
        )
    with col_right:
        note = st.text_area(
            "Note (location, needs, contact info)",
            height=96,
            key="evac_note_input",
            placeholder="e.g. At Westside shelter, needs medication pickup",
        )

    if st.button("Save Status", key="evac_save_btn", use_container_width=True, type="primary"):
        name = (person_name or "").strip()
        if not name:
            st.error("Please enter a name or identifier for the person.")
        else:
            ok = _upsert_evac_status(username, name, status, note)
            if ok:
                _log_event(username, "EVAC_STATUS_UPDATE", {"person": name, "status": status})
                st.success(f"Saved — **{name}** is now marked as **{status}**.")
            else:
                st.error("Failed to save. Please check your connection and try again.")

    # ── Tracked persons list ───────────────────────────────────────────────────
    tracked = get_tracked_persons(username)
    if tracked:
        st.markdown("---")
        st.markdown("**People you are monitoring:**")
        for p in tracked:
            c    = _STATUS_COLORS.get(p.get("status", "Not Evacuated"), "#8892a4")
            ts   = (p.get("updated_at") or "")[:16].replace("T", "  ")
            note_txt = p.get("note") or ""
            st.markdown(
                f"<div style='padding:10px 14px;background:rgba(128,128,128,0.06);"
                f"border-radius:10px;border-left:4px solid {c};margin:6px 0'>"
                f"<span style='font-weight:600'>{p['person_name']}</span> "
                f"<span style='background:{c}22;color:{c};padding:2px 9px;"
                f"border-radius:12px;font-size:0.82rem'>{p.get('status', '—')}</span><br>"
                f"<span style='font-size:0.8rem;opacity:0.65'>"
                f"{note_txt}{'  ·  ' if note_txt else ''}{ts}</span></div>",
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────────────────────────────────────

def _inject_auth_styles():
    st.markdown("""
    <style>
    .auth-title {
        text-align: center;
        font-size: 1.75rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        margin-top: 0.4rem;
        margin-bottom: 0.2rem;
    }
    .auth-subtitle {
        text-align: center;
        font-size: 0.88rem;
        opacity: 0.6;
        margin-bottom: 2rem;
    }
    .role-note {
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 0.84rem;
        margin-bottom: 0.8rem;
        line-height: 1.5;
    }
    .caregiver-note  { background:#edfaf4; border-left:3px solid #00a86b; color:#1a6645; }
    .restricted-note { background:#fdf6e3; border-left:3px solid #B3995D; color:#7a5c1e; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER SQL — run in Supabase SQL editor to add missing columns if needed
# ─────────────────────────────────────────────────────────────────────────────
# If evacuation_status is missing reporter_username / person_name / note:
#
#   ALTER TABLE public.evacuation_status
#     ADD COLUMN IF NOT EXISTS reporter_username text,
#     ADD COLUMN IF NOT EXISTS person_name       text DEFAULT 'self',
#     ADD COLUMN IF NOT EXISTS note              text DEFAULT '',
#     ADD COLUMN IF NOT EXISTS updated_at        timestamptz DEFAULT now();
#
#   ALTER TABLE public.evacuation_status
#     DROP CONSTRAINT IF EXISTS evac_status_unique_person,
#     ADD CONSTRAINT evac_status_unique_person
#       UNIQUE (reporter_username, person_name);
#
# If evacuation_changelog is missing reporter_username / person_name / old_status / changed_at:
#
#   ALTER TABLE public.evacuation_changelog
#     ADD COLUMN IF NOT EXISTS reporter_username text,
#     ADD COLUMN IF NOT EXISTS person_name       text DEFAULT 'self',
#     ADD COLUMN IF NOT EXISTS old_status        text,
#     ADD COLUMN IF NOT EXISTS note              text DEFAULT '',
#     ADD COLUMN IF NOT EXISTS changed_at        timestamptz DEFAULT now();
#
# To create test accounts quickly — run this Python snippet locally to get hashes:
#   import hashlib, os
#   for name, pw, role in [
#       ('caregiver_test',  'WiDS@2025!', 'Caregiver/Evacuee'),
#       ('dispatcher_test', 'WiDS@2025!', 'Emergency Worker'),
#       ('analyst_test',    'WiDS@2025!', 'Data Analyst'),
#   ]:
#       salt = os.urandom(32).hex()
#       hsh  = hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 260000).hex()
#       print(f"INSERT INTO public.users (username,email,password_hash,password_salt,role)")
#       print(f"VALUES ('{name}','{name}@wids.test','{hsh}','{salt}','{role}');")