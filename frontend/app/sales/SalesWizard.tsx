"use client";

import { useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Loader2, ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react";
import { auditCurrentSite, submitLead } from "./actions";

// 2026-08-16, SITE_GENERATOR_FINDINGS_2026-08-16.md item 3: subtype/street/
// region/postalCode/telephone are the fields BusinessFactsReq already accepts
// that this form never collected. Optional -- the fast three-field pitch flow
// stays exactly as fast; filling these in just improves the proposed score.
const initialFormSchema = z.object({
  businessName: z.string().min(1, "Business Name is required"),
  city: z.string().min(1, "City is required"),
  websiteUrl: z.string().url("Must be a valid URL").min(1, "URL is required"),
  subtype: z.string().optional(),
  street: z.string().optional(),
  region: z.string().optional(),
  postalCode: z.string().optional(),
  telephone: z.string().optional(),
});

const leadFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email"),
  phone: z.string().min(10, "Phone is required"),
  consent: z.boolean().refine(val => val === true, {
    message: "You must check the consent box to proceed."
  }),
});

export default function SalesWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const step = searchParams.get("step") || "1";
  
  const currentScore = searchParams.get("currentScore");
  const proposedScore = searchParams.get("proposedScore");
  const previewUrl = searchParams.get("previewUrl");

  const [formError, setFormError] = useState<string | null>(null);
  const [showMoreDetails, setShowMoreDetails] = useState(false);

  const initialForm = useForm<z.infer<typeof initialFormSchema>>({
    resolver: zodResolver(initialFormSchema),
    defaultValues: {
      businessName: searchParams.get("name") || "",
      city: searchParams.get("city") || "",
      websiteUrl: searchParams.get("url") || "",
      subtype: "",
      street: "",
      region: "",
      postalCode: "",
      telephone: "",
    }
  });

  const leadForm = useForm<z.infer<typeof leadFormSchema>>({
    resolver: zodResolver(leadFormSchema),
    defaultValues: {
      name: "",
      email: "",
      phone: "",
      consent: false,
    }
  });

  const onInitialSubmit = async (values: z.infer<typeof initialFormSchema>) => {
    setFormError(null);
    const formData = new FormData();
    formData.append("businessName", values.businessName);
    formData.append("city", values.city);
    formData.append("websiteUrl", values.websiteUrl);
    if (values.subtype) formData.append("subtype", values.subtype);
    if (values.street) formData.append("street", values.street);
    if (values.region) formData.append("region", values.region);
    if (values.postalCode) formData.append("postalCode", values.postalCode);
    if (values.telephone) formData.append("telephone", values.telephone);

    startTransition(async () => {
      const res = await auditCurrentSite(formData);
      if (res.error) {
        setFormError(res.error);
        return;
      }
      if (res.data) {
        const params = new URLSearchParams();
        params.set("step", "2");
        params.set("name", values.businessName);
        params.set("city", values.city);
        params.set("url", values.websiteUrl);
        params.set("currentScore", res.data.currentScore.toString());
        params.set("proposedScore", res.data.proposedScore.toString());
        params.set("previewUrl", res.data.previewUrl);
        router.push(`?${params.toString()}`);
      }
    });
  };

  const onLeadSubmit = async (values: z.infer<typeof leadFormSchema>) => {
    setFormError(null);
    const formData = new FormData();
    formData.append("name", values.name);
    formData.append("email", values.email);
    formData.append("phone", values.phone);
    formData.append("consent", values.consent ? "true" : "false");

    startTransition(async () => {
      const res = await submitLead(formData);
      if (res.error) {
        setFormError(res.error);
        return;
      }
      if (res.success) {
        router.push("?step=4");
      }
    });
  };

  if (step === "1") {
    return (
      <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-6 md:p-8 space-y-8 animate-in fade-in zoom-in-95 duration-300">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Instant Site Audit</h1>
          <p className="text-slate-500 text-sm">See how your current website performs against modern standards.</p>
        </div>

        <form onSubmit={initialForm.handleSubmit(onInitialSubmit)} className="space-y-5">
          <div className="space-y-1.5">
            <label className="text-sm font-semibold text-slate-700">Business Name</label>
            <input 
              {...initialForm.register("businessName")}
              className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
              placeholder="e.g. Acme Corp"
            />
            {initialForm.formState.errors.businessName && (
              <p className="text-red-500 text-xs font-medium">{initialForm.formState.errors.businessName.message}</p>
            )}
          </div>
          
          <div className="space-y-1.5">
            <label className="text-sm font-semibold text-slate-700">City</label>
            <input 
              {...initialForm.register("city")}
              className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
              placeholder="e.g. Austin, TX"
            />
            {initialForm.formState.errors.city && (
              <p className="text-red-500 text-xs font-medium">{initialForm.formState.errors.city.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-semibold text-slate-700">Current Website URL</label>
            <input 
              {...initialForm.register("websiteUrl")}
              className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
              placeholder="https://example.com"
              type="url"
            />
            {initialForm.formState.errors.websiteUrl && (
              <p className="text-red-500 text-xs font-medium">{initialForm.formState.errors.websiteUrl.message}</p>
            )}
          </div>

          <div className="border-t border-slate-100 pt-4">
            <button
              type="button"
              onClick={() => setShowMoreDetails((v) => !v)}
              className="text-sm font-semibold text-blue-600 hover:text-blue-700 transition-colors"
            >
              {showMoreDetails ? "Hide extra details" : "+ Add more details (improves the proposed score)"}
            </button>

            {showMoreDetails && (
              <div className="space-y-4 mt-4 animate-in fade-in duration-200">
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-slate-700">Business Type</label>
                  <input
                    {...initialForm.register("subtype")}
                    className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
                    placeholder="e.g. Dentist, Chiropractor, Plumber"
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-slate-700">Street Address</label>
                  <input
                    {...initialForm.register("street")}
                    className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
                    placeholder="e.g. 123 Main St"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-sm font-semibold text-slate-700">State</label>
                    <input
                      {...initialForm.register("region")}
                      className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
                      placeholder="e.g. TX"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-semibold text-slate-700">ZIP Code</label>
                    <input
                      {...initialForm.register("postalCode")}
                      className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
                      placeholder="e.g. 78701"
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-semibold text-slate-700">Phone Number</label>
                  <input
                    {...initialForm.register("telephone")}
                    className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400"
                    placeholder="e.g. (512) 555-0100"
                    type="tel"
                  />
                </div>
              </div>
            )}
          </div>

          {formError && (
            <div className="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-100 font-medium">
              {formError}
            </div>
          )}

          <button 
            type="submit" 
            disabled={isPending}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-70 active:scale-[0.98] shadow-sm shadow-blue-600/20"
          >
            {isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : <ArrowRight className="w-5 h-5" />}
            <span>Run Audit</span>
          </button>
        </form>
      </div>
    );
  }

  if (step === "2") {
    return (
      <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-6 md:p-8 space-y-10 animate-in slide-in-from-right-4 fade-in duration-300">
        <div className="text-center space-y-2">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">Audit Complete</h2>
          <p className="text-slate-500 text-sm">Here is how your site compares to our optimized standard.</p>
        </div>

        <div className="flex gap-4 items-center justify-center py-4">
          <div className="flex-1 text-center space-y-3">
            <div className="text-sm font-bold tracking-wider text-slate-400 uppercase">Current</div>
            <div className="text-5xl font-black text-slate-900 tracking-tighter">{currentScore}</div>
            <div className="text-xs font-medium text-slate-400">/ 100</div>
          </div>
          <div className="w-px h-24 bg-slate-100"></div>
          <div className="flex-1 text-center space-y-3">
            <div className="text-sm font-bold tracking-wider text-emerald-500 uppercase">Proposed</div>
            <div className="text-5xl font-black text-emerald-500 tracking-tighter">{proposedScore}</div>
            <div className="text-xs font-medium text-slate-400">/ 100</div>
          </div>
        </div>

        <div className="space-y-3">
          <button 
            onClick={() => window.open(previewUrl || "#", "_blank")}
            className="w-full bg-slate-900 hover:bg-slate-800 text-white font-bold py-4 rounded-xl transition-all active:scale-[0.98] shadow-sm"
          >
            View Full-Screen Preview
          </button>
          
          <button 
            onClick={() => {
              const params = new URLSearchParams(searchParams.toString());
              params.set("step", "3");
              router.push(`?${params.toString()}`);
            }}
            className="w-full bg-blue-50 text-blue-600 hover:bg-blue-100 font-bold py-4 rounded-xl transition-all active:scale-[0.98]"
          >
            Claim This Design
          </button>
        </div>
      </div>
    );
  }

  if (step === "3") {
    return (
      <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-6 md:p-8 space-y-8 animate-in slide-in-from-bottom-4 fade-in duration-300">
        <div className="text-center space-y-2">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">Let's Make It Yours</h2>
          <p className="text-slate-500 text-sm">Enter your details to secure this design for your business.</p>
        </div>

        <form onSubmit={leadForm.handleSubmit(onLeadSubmit)} className="space-y-5">
          <div className="space-y-1.5">
            <input 
              {...leadForm.register("name")}
              className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400 font-medium"
              placeholder="Full Name"
            />
            {leadForm.formState.errors.name && (
              <p className="text-red-500 text-xs font-medium">{leadForm.formState.errors.name.message}</p>
            )}
          </div>
          
          <div className="space-y-1.5">
            <input 
              {...leadForm.register("email")}
              className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400 font-medium"
              placeholder="Email Address"
              type="email"
            />
            {leadForm.formState.errors.email && (
              <p className="text-red-500 text-xs font-medium">{leadForm.formState.errors.email.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <input 
              {...leadForm.register("phone")}
              className="w-full px-4 py-3.5 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 outline-none transition-all placeholder:text-slate-400 font-medium"
              placeholder="Phone Number"
              type="tel"
            />
            {leadForm.formState.errors.phone && (
              <p className="text-red-500 text-xs font-medium">{leadForm.formState.errors.phone.message}</p>
            )}
          </div>

          <div className="bg-slate-50 p-5 rounded-xl border border-slate-200 flex items-start gap-4">
            <div className="mt-0.5">
              <input 
                type="checkbox"
                id="consent"
                {...leadForm.register("consent")}
                className="w-5 h-5 rounded border-slate-300 text-blue-600 focus:ring-blue-500/20 cursor-pointer transition-all"
              />
            </div>
            <div className="flex-1">
              <label htmlFor="consent" className="text-xs text-slate-600 cursor-pointer block leading-relaxed font-medium">
                By checking this box, I agree to receive text messages and emails about my inquiry. I understand consent is required to proceed.
              </label>
              {leadForm.formState.errors.consent && (
                <p className="text-red-500 text-xs mt-2 font-bold">{leadForm.formState.errors.consent.message}</p>
              )}
            </div>
          </div>

          {formError && (
            <div className="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-100 font-medium">
              {formError}
            </div>
          )}

          <button 
            type="submit" 
            disabled={isPending}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-70 active:scale-[0.98] shadow-sm shadow-blue-600/20"
          >
            {isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : <ShieldCheck className="w-5 h-5" />}
            <span>Secure My Design</span>
          </button>
        </form>
      </div>
    );
  }

  if (step === "4") {
    return (
      <div className="bg-white rounded-3xl shadow-xl border border-slate-100 p-8 text-center space-y-4 animate-in zoom-in-95 fade-in duration-300">
        <div className="w-20 h-20 bg-emerald-50 text-emerald-500 rounded-full flex items-center justify-center mx-auto mb-6 shadow-inner">
          <CheckCircle2 className="w-10 h-10" />
        </div>
        <h2 className="text-3xl font-bold tracking-tight text-slate-900">You're All Set!</h2>
        <p className="text-slate-500 font-medium">We've sent the details to your email. One of our specialists will be in touch shortly.</p>
        <div className="pt-6">
          <button 
            onClick={() => router.push("/")}
            className="text-slate-500 font-semibold hover:text-slate-800 transition-colors"
          >
            Return Home
          </button>
        </div>
      </div>
    );
  }

  return null;
}
