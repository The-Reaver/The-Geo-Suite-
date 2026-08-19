"""Service layer for the backend.

Services wrap external providers so route handlers never talk to a
provider SDK directly. Every service reads its secrets from the config
loader, which pulls values from environment files only. No key ever
lives in code.

Current services:
- supabase_client: shared Supabase client used for database access and
  the /health database status check.

Later tasks add services for Stripe, Twilio, and Resend behind the same
pattern.
"""