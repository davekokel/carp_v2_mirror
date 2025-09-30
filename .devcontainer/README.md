Devcontainer for carp_v2

This devcontainer builds a lightweight Python 3.11 environment and installs Python dependencies during image build.

What it does
- Builds from official python:3.11-slim
- Creates a non-root `vscode` user
- Copies `supabase/ui/requirements.txt` into the image and installs them during Docker build
- Runs `streamlit run supabase/ui/streamlit_app.py` to launch streamlit.  You can then visit the site using a browser on the host: http://localhost:8501/

Usage
0. Have supabase running (or set it up to connect to the cloud)
1. Open this repository in VS Code
2. Click the green "><" icon in the bottom-left and choose "Reopen in Container"
3. Open http://localhost:8501/ on the host

Notes
- Dependency installation happens at build time. If you change `requirements.txt`, rebuild the devcontainer to pick up changes.
- If you need extra system packages, edit `.devcontainer/Dockerfile`.


# 2025-09-30
# Devcontainer

1) Open the repo in VS Code → **Reopen in Container**  
2) Inside the container:
   ```bash
   mkdir -p .streamlit
   # Fill with your own creds (don’t commit this file)
   cat > .streamlit/secrets.toml <<'TOML'
   DB_URL = "postgresql://…"
   SUPABASE_URL = "https://…"
   SUPABASE_ANON_KEY = "…"
   APP_PASSWORD = "letmein"
   READ_ONLY = "true"
   TOML