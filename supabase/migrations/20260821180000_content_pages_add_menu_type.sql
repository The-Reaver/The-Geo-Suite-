-- Widens content_pages.page_type's CHECK constraint to allow 'menu',
-- matching the new menu.html page site_engine.py now generates for
-- food-service businesses with real menu_items.
--
-- 2026-08-21, Opus 5 review of the menu-page slice: menu.html fell through
-- site_pipeline.py's _page_type_for() to the "other" fallback, which the
-- ORIGINAL version of this constraint (20260820160000_site_pipeline_tables.sql)
-- rejects -- every food-service business with real menu_items generated a
-- site that passed the audit and compliance gates and then failed to save
-- with a raw ValueError, the exact "silently mislabeled/rejected page type"
-- defect class that migration's own comment already documents being fixed
-- once for privacy.html/accessibility.html.
--
-- The original migration file is left untouched (already applied to the
-- live project, immutable history); this is the real follow-up ALTER that
-- brings the live database's constraint in line with
-- content_pages_repository.py's now-widened _VALID_PAGE_TYPES.
alter table public.content_pages
  drop constraint if exists content_pages_page_type_check;

alter table public.content_pages
  add constraint content_pages_page_type_check
  check (page_type in ('home', 'service', 'menu', 'faq', 'about', 'privacy', 'accessibility'));
