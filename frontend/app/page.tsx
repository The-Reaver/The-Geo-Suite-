// frontend/app/page.tsx
//
// Root entry point for GEO Suite. Redirects to /login, matching the fix
// applied in Stag-GEO-Platform on 2026-08-19 (that repo's root page had
// shipped as an unedited dev scaffold placeholder for weeks before anyone
// noticed) -- this repo starts with the correct behavior from day one.

import { redirect } from "next/navigation";

export default function HomePage() {
  redirect("/login");
}
