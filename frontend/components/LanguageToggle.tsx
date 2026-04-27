"use client";

import { Language } from "@/lib/api";

interface LanguageToggleProps {
  language: Language;
  onToggle: () => void;
  disabled?: boolean;
}

const LABELS: Record<Language, string> = {
  en: "English",
  sv: "Svenska",
};

export default function LanguageToggle({ language, onToggle, disabled }: LanguageToggleProps) {
  return (
    <div className="flex flex-col gap-1 items-start">
      <span className="text-[0.6rem] md:text-xs font-medium tracking-[0.2em] text-slate-500 uppercase">
        Speech Language
      </span>
      <button
        type="button"
        onClick={onToggle}
        disabled={disabled}
        className="text-xs md:text-sm font-semibold text-slate-300 tracking-wide hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center gap-1.5"
        aria-label={`Switch language. Currently ${LABELS[language]}.`}
      >
        <span className="uppercase tracking-[0.15em]">{language}</span>
        <span className="text-slate-500">·</span>
        <span>{LABELS[language]}</span>
      </button>
    </div>
  );
}
