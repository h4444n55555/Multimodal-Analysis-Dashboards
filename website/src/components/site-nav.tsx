"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { ChevronDown, Menu } from "lucide-react";
import { AnimatedThemeToggler } from "@/components/ui/animated-theme-toggler";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MODALITIES } from "@/lib/modalities";

// On-page sections (home route) — tabs scroll here.
const sections = [
  { id: "hero", label: "Overview" },
  { id: "why", label: "Why This Research" },
  { id: "sensors", label: "Data" },
  { id: "tasks", label: "Tasks" },
  { id: "apps", label: "Built with the Data" },
  { id: "status", label: "Research Pipeline" },
  { id: "team", label: "Team" },
];

export function SiteNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [active, setActive] = useState("hero");
  const [menuOpen, setMenuOpen] = useState(false);
  // The sheet's scroll lock and focus restore run as it closes and would undo
  // a hash jump, so the menu scrolls to its target only once it has closed.
  const pendingSection = useRef<string | null>(null);

  useEffect(() => {
    if (pathname !== "/") return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(entry.target.id);
        }
      },
      { rootMargin: "-45% 0px -50% 0px", threshold: 0 },
    );

    const elements = sections
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => el !== null);
    elements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [pathname]);

  const onHome = pathname === "/";

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/60 bg-background/80 backdrop-blur print:hidden">
      <div className="mx-auto grid h-16 w-full max-w-7xl grid-cols-[1fr_auto_1fr] items-center px-6">
        <Link href="/" className="flex items-center justify-self-start">
          <Image
            src="/Logo-Light.png"
            alt="IIT Ropar"
            width={56}
            height={56}
            className="h-14 w-14 dark:hidden"
            priority
          />
          <Image
            src="/Logo-Dark.png"
            alt="IIT Ropar"
            width={56}
            height={56}
            className="hidden h-14 w-14 dark:block"
            priority
          />
        </Link>
        <nav className="hidden items-center gap-6 text-sm xl:flex">
          {sections.map((s) =>
            s.id === "sensors" ? (
              <DropdownMenu key={s.id}>
                {/* styled as a button so it reads as clickable (P5 in testing) */}
                <DropdownMenuTrigger
                  className={cn(
                    "flex items-center gap-1 rounded-full border border-border bg-muted/60 px-3 py-1 font-medium text-foreground outline-none transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 aria-expanded:bg-muted",
                    onHome && active === s.id && "border-foreground/40",
                  )}
                >
                  {s.label}
                  <ChevronDown className="size-3.5" aria-hidden="true" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="center" className="w-72">
                  {MODALITIES.map((m) =>
                    m.href ? (
                      <DropdownMenuItem key={m.key} asChild>
                        <Link href={m.href} className="flex flex-col items-start gap-0.5">
                          <span className="font-medium">{m.title}</span>
                          <span className="text-xs text-muted-foreground">{m.measures}</span>
                        </Link>
                      </DropdownMenuItem>
                    ) : (
                      <DropdownMenuItem key={m.key} disabled className="flex flex-col items-start gap-0.5">
                        <span className="font-medium">{m.title} · soon</span>
                        <span className="text-xs text-muted-foreground">{m.measures}</span>
                      </DropdownMenuItem>
                    ),
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <Link
                key={s.id}
                href={`/#${s.id}`}
                className={cn(
                  "text-muted-foreground transition-colors hover:text-foreground",
                  onHome && active === s.id && "text-foreground font-medium",
                )}
              >
                {s.label}
              </Link>
            ),
          )}
        </nav>
        <div className="flex items-center justify-self-end gap-6">
          <AnimatedThemeToggler className="text-muted-foreground transition-colors hover:text-foreground" />
          <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
            <SheetTrigger
              aria-label="Open menu"
              className="text-muted-foreground transition-colors hover:text-foreground xl:hidden"
            >
              <Menu />
            </SheetTrigger>
            <SheetContent
              side="right"
              className="px-6 pt-14"
              onCloseAutoFocus={(e) => {
                const id = pendingSection.current;
                if (!id) return;
                e.preventDefault();
                pendingSection.current = null;
                if (onHome) {
                  document.getElementById(id)?.scrollIntoView();
                  history.replaceState(null, "", `/#${id}`);
                } else {
                  router.push(`/#${id}`);
                }
              }}
            >
              <SheetTitle className="sr-only">Sections</SheetTitle>
              <nav className="flex flex-col gap-4 text-base">
                {sections.map((s) => (
                  <div key={s.id} className="flex flex-col gap-3">
                    <a
                      href={`/#${s.id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        pendingSection.current = s.id;
                        setMenuOpen(false);
                      }}
                      className={cn(
                        "text-muted-foreground transition-colors hover:text-foreground",
                        onHome &&
                          active === s.id &&
                          "text-foreground font-medium",
                      )}
                    >
                      {s.label}
                    </a>
                    {s.id === "sensors" && (
                      <div className="flex flex-col gap-3 border-l border-border/60 pl-4 text-sm">
                        {MODALITIES.map((m) =>
                          m.href ? (
                            <Link
                              key={m.key}
                              href={m.href}
                              onClick={() => setMenuOpen(false)}
                              className="text-muted-foreground transition-colors hover:text-foreground"
                            >
                              {m.title}
                            </Link>
                          ) : (
                            <span
                              key={m.key}
                              className="flex items-center gap-2 text-muted-foreground"
                            >
                              {m.title}
                              <span className="text-xs">Soon</span>
                            </span>
                          ),
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
