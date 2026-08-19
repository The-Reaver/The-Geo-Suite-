import { Suspense } from "react";
import SalesWizard from "./SalesWizard";

export default function SalesPage() {
  return (
    <main className="min-h-screen bg-slate-50 flex flex-col p-4 md:p-8">
      <div className="max-w-md w-full mx-auto flex-1 flex flex-col justify-center">
        <Suspense fallback={<div className="text-center p-8">Loading...</div>}>
          <SalesWizard />
        </Suspense>
      </div>
    </main>
  );
}
