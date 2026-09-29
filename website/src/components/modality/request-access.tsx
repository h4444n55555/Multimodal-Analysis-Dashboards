"use client";

import { useRef, useState, type FormEvent, type ReactNode } from "react";
import Link from "next/link";
import { Dialog } from "radix-ui";
import { ArrowLeft, ArrowRight, Lock, MailCheck, X } from "lucide-react";
import { MODALITIES } from "@/lib/modalities";
import { DATA_REQUEST_EMAIL } from "@/lib/links";
import {
  AGREEMENT_TITLE,
  AGREEMENT_VERSION,
  CLAUSES,
  DURATIONS,
  ETHICS_OPTIONS,
  MODALITY_CONTENTS,
  PERSONAL_EMAIL,
  POSITIONS,
  STUDENT_POSITIONS,
} from "@/lib/data-agreement";
import { cn } from "@/lib/utils";

const control =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-foreground/50 focus-visible:ring-2 focus-visible:ring-ring/40";

const STEPS = ["You", "Project", "Agreement"] as const;

/**
 * "Request access" call-to-action and its pop-up form — the same on every
 * modality page. There's no backend yet: sending opens the applicant's email
 * app with the full request written out, addressed to the study team (and
 * copied to a student's supervisor). The team approves by reply.
 */
export function RequestAccess() {
  return (
    <Dialog.Root>
      <section className="flex flex-col items-start justify-between gap-4 rounded-3xl border border-border bg-card p-6 sm:flex-row sm:items-center">
        <div className="flex items-start gap-3">
          <Lock className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div>
            <p className="font-semibold">Want to use this data?</p>
            <p className="text-sm text-muted-foreground">
              Shared for non-commercial research, on approval, under the{" "}
              <Link href="/data-agreement" className="underline underline-offset-4 hover:text-foreground">
                data use agreement
              </Link>
              .
            </p>
          </div>
        </div>
        <Dialog.Trigger className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-background transition-opacity hover:opacity-85">
          Request access <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Dialog.Trigger>
      </section>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
        <Dialog.Content
          onInteractOutside={(e) => e.preventDefault()}
          className="viz fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-3xl border border-border bg-background shadow-2xl data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95"
        >
          <RequestForm />
          <Dialog.Close
            className="absolute right-4 top-4 rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Field({ label, hint, className, children }: { label: string; hint?: ReactNode; className?: string; children: ReactNode }) {
  return (
    <label className={cn("flex flex-col gap-1 text-xs text-muted-foreground", className)}>
      {label}
      {children}
      {hint}
    </label>
  );
}

function RequestForm() {
  const formRef = useRef<HTMLFormElement>(null);
  const stepRefs = useRef<(HTMLFieldSetElement | null)[]>([]);
  const [step, setStep] = useState(0);
  const [position, setPosition] = useState("");
  const [email, setEmail] = useState("");
  const [modalities, setModalities] = useState<string[]>([]);
  const [ethics, setEthics] = useState("");
  const [modalityError, setModalityError] = useState(false);
  const [signError, setSignError] = useState(false);
  const [sent, setSent] = useState(false);
  const isStudent = STUDENT_POSITIONS.has(position);

  // validates only the visible step, using the browser's own field messages
  const stepValid = () => {
    const fields = stepRefs.current[step]?.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
      "input, select, textarea",
    );
    for (const el of fields ?? []) {
      if (!el.checkValidity()) {
        el.reportValidity();
        return false;
      }
    }
    if (step === 1 && modalities.length === 0) {
      setModalityError(true);
      return false;
    }
    return true;
  };

  const next = () => {
    if (!stepValid()) return;
    setStep((s) => s + 1);
    formRef.current?.closest("[role=dialog]")?.querySelector("[data-scroll]")?.scrollTo(0, 0);
  };

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (step < STEPS.length - 1) return next();
    if (!stepValid()) return;
    const f = new FormData(e.currentTarget);
    const get = (k: string) => String(f.get(k) ?? "").trim();
    if (get("signature").toLowerCase() !== get("name").toLowerCase()) {
      setSignError(true);
      return;
    }

    const titles = MODALITIES.filter((m) => modalities.includes(m.key)).map((m) => m.title);
    const today = new Date().toISOString().slice(0, 10);
    const lines = [
      `DATA ACCESS REQUEST — ${titles.join(", ")}`,
      "",
      "APPLICANT",
      `Name: ${get("name")}`,
      `Position: ${get("position")}`,
      `Institutional email: ${get("email")}`,
      `Institution / department: ${get("institution")} — ${get("department")}`,
      `Country: ${get("country")}`,
      get("homepage") ? `Profile page: ${get("homepage")}` : null,
      ...(isStudent
        ? ["", "SUPERVISOR", `Name: ${get("supName")}`, `Position: ${get("supTitle")}`, `Email: ${get("supEmail")}`]
        : []),
      "",
      "PROJECT",
      `Title: ${get("project")}`,
      `Modalities: ${titles.join(", ")}`,
      `Intended use: ${get("purpose")}`,
      `Ethics approval: ${get("ethics")}${get("ethicsRef") ? ` (ref. ${get("ethicsRef")})` : ""}`,
      `Access period: ${get("duration")}`,
      `People who will access the data: ${get("team")}`,
      "",
      "AGREEMENT",
      `I agree to the ${AGREEMENT_TITLE}, version ${AGREEMENT_VERSION} (clauses 1–${CLAUSES.length}).`,
      isStudent ? "My supervisor, copied on this email, has read and approves this request." : null,
      `Signed: ${get("signature")}`,
      `Date: ${today}`,
    ].filter((l) => l !== null);

    const params = new URLSearchParams({ subject: `Data access request — ${get("name")}, ${get("institution")}` });
    if (isStudent) params.set("cc", get("supEmail"));
    const query = params.toString().replace(/\+/g, "%20");
    window.location.href = `mailto:${DATA_REQUEST_EMAIL}?${query}&body=${encodeURIComponent(lines.join("\n"))}`;
    setSent(true);
  };

  if (sent) {
    return (
      <div className="flex flex-col items-start gap-3 p-7 pr-12">
        <MailCheck className="h-7 w-7" aria-hidden="true" />
        <Dialog.Title className="text-xl font-semibold">Almost done — send the email</Dialog.Title>
        <Dialog.Description className="text-sm leading-relaxed text-muted-foreground">
          Your email app should have opened with the full request written out
          {isStudent ? ", copied to your supervisor" : ""}. Send it from your institutional address and we’ll reply once
          it’s reviewed. If nothing opened, email{" "}
          <a href={`mailto:${DATA_REQUEST_EMAIL}`} className="font-medium text-foreground underline underline-offset-4">
            {DATA_REQUEST_EMAIL}
          </a>
          .
        </Dialog.Description>
        <button type="button" onClick={() => setSent(false)} className="text-sm text-muted-foreground underline-offset-4 hover:underline">
          Back to the form
        </button>
      </div>
    );
  }

  return (
    <form ref={formRef} onSubmit={submit} noValidate className="flex min-h-0 flex-col">
      {/* header + progress */}
      <div className="border-b border-border px-6 pb-4 pt-6 pr-12">
        <Dialog.Title className="text-xl font-semibold">Request access</Dialog.Title>
        <Dialog.Description className="mt-0.5 text-sm text-muted-foreground">
          For non-commercial academic research. Every request is reviewed by the study team.
        </Dialog.Description>
        <ol className="mt-4 grid grid-cols-3 gap-2" aria-label="Steps">
          {STEPS.map((s, i) => (
            <li key={s} className="flex flex-col gap-1.5" aria-current={i === step ? "step" : undefined}>
              <span className={cn("h-1 rounded-full", i <= step ? "bg-foreground" : "bg-muted")} />
              <span className={cn("text-xs", i === step ? "font-medium text-foreground" : "text-muted-foreground")}>
                {i + 1} · {s}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <div data-scroll className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        {/* 1 · applicant */}
        <fieldset ref={(el) => void (stepRefs.current[0] = el)} hidden={step !== 0} className="grid gap-3 sm:grid-cols-2">
          <Field label="Full name">
            <input name="name" required autoComplete="name" className={control} />
          </Field>
          <Field label="Position">
            <select name="position" required value={position} onChange={(e) => setPosition(e.target.value)} className={control}>
              <option value="" disabled>
                Choose…
              </option>
              {POSITIONS.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </Field>
          <Field
            label="Institutional email"
            className="sm:col-span-2"
            hint={
              PERSONAL_EMAIL.test(email) && (
                <span style={{ color: "var(--status-critical)" }}>
                  Please use your university or institute address — requests from personal email may not be approved.
                </span>
              )
            }
          >
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={control}
            />
          </Field>
          <Field label="Institution">
            <input name="institution" required autoComplete="organization" className={control} />
          </Field>
          <Field label="Department">
            <input name="department" required className={control} />
          </Field>
          <Field label="Country">
            <input name="country" required autoComplete="country-name" className={control} />
          </Field>
          <Field label="Profile page (optional)">
            <input name="homepage" type="url" placeholder="https://" className={control} />
          </Field>

          {isStudent && (
            <div className="mt-2 grid gap-3 rounded-xl border border-border p-4 sm:col-span-2 sm:grid-cols-2">
              <p className="text-sm font-medium sm:col-span-2">
                Supervisor
                <span className="block text-xs font-normal text-muted-foreground">
                  Students apply through their supervisor, who is copied on the request.
                </span>
              </p>
              <Field label="Supervisor’s name">
                <input name="supName" required className={control} />
              </Field>
              <Field label="Supervisor’s position">
                <input name="supTitle" required placeholder="e.g. Assistant Professor" className={control} />
              </Field>
              <Field label="Supervisor’s institutional email" className="sm:col-span-2">
                <input name="supEmail" type="email" required className={control} />
              </Field>
            </div>
          )}
        </fieldset>

        {/* 2 · project */}
        <fieldset ref={(el) => void (stepRefs.current[1] = el)} hidden={step !== 1} className="flex flex-col gap-3">
          <Field label="Project title">
            <input name="project" required className={control} />
          </Field>

          <div className="flex flex-col gap-1.5">
            <p className="text-xs text-muted-foreground">Modalities</p>
            {MODALITIES.map((m) => {
              const on = modalities.includes(m.key);
              return (
                <label
                  key={m.key}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-2.5 transition-colors",
                    on ? "border-foreground/60 bg-muted/60" : "border-border hover:border-foreground/30",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => {
                      setModalityError(false);
                      setModalities((p) => (on ? p.filter((k) => k !== m.key) : [...p, m.key]));
                    }}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="block text-sm font-medium">{m.title}</span>
                    <span className="block text-xs text-muted-foreground">{MODALITY_CONTENTS[m.key]}</span>
                  </span>
                </label>
              );
            })}
            {modalityError && (
              <p role="alert" className="text-xs" style={{ color: "var(--status-critical)" }}>
                Choose at least one modality.
              </p>
            )}
          </div>

          <Field label="How will you use the data? (research question and methods)">
            <textarea name="purpose" required minLength={50} rows={4} className={cn(control, "resize-y")} />
          </Field>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Ethics approval">
              <select name="ethics" required value={ethics} onChange={(e) => setEthics(e.target.value)} className={control}>
                <option value="" disabled>
                  Choose…
                </option>
                {ETHICS_OPTIONS.map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </Field>
            <Field label={ethics === ETHICS_OPTIONS[0] ? "Approval reference" : "Approval reference (if any)"}>
              <input name="ethicsRef" required={ethics === ETHICS_OPTIONS[0]} className={control} />
            </Field>
            <Field label="Access needed for">
              <select name="duration" required defaultValue="" className={control}>
                <option value="" disabled>
                  Choose…
                </option>
                {DURATIONS.map((d) => (
                  <option key={d}>{d}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Everyone who will handle the data (names and roles)">
            <textarea name="team" required rows={2} placeholder="e.g. Jane Doe (PI), John Roe (PhD student)" className={cn(control, "resize-y")} />
          </Field>
        </fieldset>

        {/* 3 · agreement */}
        <fieldset ref={(el) => void (stepRefs.current[2] = el)} hidden={step !== 2} className="flex flex-col gap-4">
          <div>
            <p className="text-sm font-medium">
              {AGREEMENT_TITLE} <span className="font-normal text-muted-foreground">· v{AGREEMENT_VERSION}</span>
            </p>
            <Link href="/data-agreement" target="_blank" className="text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground">
              Open the full agreement in a new tab
            </Link>
          </div>
          <ol className="max-h-64 list-decimal space-y-2 overflow-y-auto rounded-xl border border-border bg-muted/40 py-3 pl-9 pr-4 text-xs leading-relaxed">
            {CLAUSES.map((c) => (
              <li key={c.title}>
                <span className="font-medium text-foreground">{c.title}.</span>{" "}
                <span className="text-muted-foreground">{c.text}</span>
              </li>
            ))}
          </ol>

          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" name="agree" required className="mt-1" />
            I have read the agreement and accept all {CLAUSES.length} terms on behalf of everyone listed in my request.
          </label>
          {isStudent && (
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" name="supAgree" required className="mt-1" />
              My supervisor has read this agreement and approves the request.
            </label>
          )}

          <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
            <Field
              label="Signature — type your full name"
              hint={
                signError && (
                  <span role="alert" style={{ color: "var(--status-critical)" }}>
                    Type your name exactly as in step 1.
                  </span>
                )
              }
            >
              <input
                name="signature"
                required
                onChange={() => setSignError(false)}
                className={cn(control, "font-serif italic")}
              />
            </Field>
            <Field label="Date">
              <input readOnly tabIndex={-1} value={new Date().toISOString().slice(0, 10)} className={cn(control, "tabular-nums text-muted-foreground")} />
            </Field>
          </div>
        </fieldset>
      </div>

      {/* footer actions */}
      <div className="flex items-center justify-between gap-3 border-t border-border px-6 py-4">
        {step > 0 ? (
          <button
            type="button"
            onClick={() => setStep((s) => s - 1)}
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
        ) : (
          <span />
        )}
        <button
          type="submit"
          className="inline-flex items-center gap-1.5 rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background"
        >
          {step < STEPS.length - 1 ? (
            <>
              Continue <ArrowRight className="h-4 w-4" />
            </>
          ) : (
            "Sign and send request"
          )}
        </button>
      </div>
    </form>
  );
}
