mkdir -p supabase/ui/pages
pbpaste > supabase/ui/pages/20_add_treatments.py
git add supabase/ui/pages/20_add_treatments.py supabase/queries.py
git commit -m "ui: add minimal Add Treatments page (compatible schema)"