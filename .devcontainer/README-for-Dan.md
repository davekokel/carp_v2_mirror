# Staging Access Guide (Read-Only)

Hi Dan,

Here’s everything you need to connect to our **staging database** safely in read-only mode.

---

## 1. Database DSN (Read-Only)

Use this connection string (don’t check into GitHub):

```
postgresql://teammate_ro:C9CjEFOP6XeYmH8tz765rhGK@db.zebzrvjbalhazztvhhcm.supabase.co:5432/postgres?sslmode=require
```

### Test it with `psql`
```bash
psql "postgresql://teammate_ro:C9CjEFOP6XeYmH8tz765rhGK@db.zebzrvjbalhazztvhhcm.supabase.co:5432/postgres?sslmode=require"   -Atc "select now(), current_user, current_database();"
```

You should connect fine, but **writes will be denied** (read-only role).

---

## 2. Streamlit Secrets Setup

Inside your devcontainer, create `.streamlit/secrets.toml`:

```toml
DB_URL = "postgresql://teammate_ro:C9CjEFOP6XeYmH8tz765rhGK@db.zebzrvjbalhazztvhhcm.supabase.co:5432/postgres?sslmode=require"
SUPABASE_URL = "https://zebzrvjbalhazztvhhcm.supabase.co"
SUPABASE_ANON_KEY = "<anon-key-placeholder>"
APP_PASSWORD = "letmein"
READ_ONLY = "true"
```

---

## 3. Run Streamlit

From inside the devcontainer:

```bash
cd /workspace/carp_v2
streamlit run supabase/ui/streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501), enter the app password **`letmein`**, and you’ll be in.

---

✅ This account is **read-only**. You can explore staging data safely without risk of modifying anything.
