export type Mode = "fast" | "stealth" | "deep";

export interface Step {
  step: number;
  action: string;
  argument?: string;
  ai_reasoning?: string;
  status: string;
  screenshot?: string;
  answer?: string;
  error?: string;
  url?: string;
  page_title?: string;
  duration_ms?: number;
  model?: string;
  observation?: string;
  thinking?: string;
  timestamp: number;
}

export const ACTION_CONFIG: Record<string, { icon: string; color: string }> = {
  navigate:   { icon: "Globe",       color: "text-blue-400"    },
  click:      { icon: "MousePointer", color: "text-amber-400"   },
  type:       { icon: "Type",        color: "text-emerald-400" },
  scroll:     { icon: "ScrollText",  color: "text-zinc-400"    },
  wait:       { icon: "Timer",       color: "text-zinc-400"    },
  screenshot: { icon: "Camera",      color: "text-pink-400"    },
  done:       { icon: "CheckCircle2",color: "text-emerald-400" },
  error:      { icon: "AlertCircle", color: "text-red-400"     },
  check:      { icon: "CheckCircle2",color: "text-cyan-400"    },
  submit:     { icon: "Rocket",      color: "text-violet-400"  },
  thinking:   { icon: "Brain",       color: "text-violet-400"  },
  paused:     { icon: "Pause",      color: "text-amber-400"   },
};

export const MODE_STYLES: Record<Mode, { label: string; color: string; border: string; bg: string }> = {
  fast:   { label: "Fast",   color: "text-amber-400",   border: "border-amber-500/40",   bg: "bg-amber-500/10"   },
  stealth:{ label: "Stealth", color: "text-slate-300",   border: "border-slate-500/40",   bg: "bg-slate-500/10"   },
  deep:   { label: "Deep",   color: "text-violet-400",  border: "border-violet-500/40", bg: "bg-violet-500/10"  },
};

export const QUICK_SITES = [
  {
    name: "Pizza Form",
    icon: "🍕",
    url: "https://httpbin.org/forms/post",
    task: "Fill and submit the pizza order form: Type John Connor in name, 07123456789 in phone, john@example.com in email. Select Large pizza size. Check Bacon topping. Click Submit. Report the result page.",
  },
  {
    name: "Login Flow",
    icon: "🔐",
    url: "https://httpbin.org/basic-auth/user/passwd",
    task: "Navigate to the page. Type user in the username field and passwd in the password field. Click the submit button. Report the result.",
  },
  {
    name: "Job Board",
    icon: "💼",
    url: "https://boards.greenhouse.io/embed/job_board?for_first=True",
    task: "Navigate to the job board. Report all visible job listings including job title, company name, and location.",
  },
  {
    name: "Travel Search",
    icon: "✈️",
    url: "https://www.booking.com",
    task: "Navigate to Booking.com. Report the page title and what search fields are visible. Do not fill anything in.",
  },
];
