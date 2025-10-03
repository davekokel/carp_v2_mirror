mkdir -p supabase/ui/components
pbpaste > supabase/ui/components/overview_browser.py
# paste the component code, press Enter

pbpaste > supabase/ui/pages/30_new_cross.py
# paste the updated page code, press Enter

git add supabase/ui/components/overview_browser.py supabase/ui/pages/30_new_cross.py
git commit -m "ui(cross): overview-style picker w/ checkboxes + swap; reusable component"
kill -9 $(lsof -ti :8501) 2>/dev/null || true
source .venv/bin/activate
python3 -m streamlit run supabase/ui/streamlit_app.py --server.address 0.0.0.0 --server.port 8501