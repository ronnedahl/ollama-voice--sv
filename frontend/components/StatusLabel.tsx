interface StatusLabelProps {
  label: string;
  value: string;
  align?: "left" | "right";
}

export default function StatusLabel({ label, value, align = "left" }: StatusLabelProps) {
  return (
    <div className={`flex flex-col gap-1 ${align === "right" ? "items-end" : "items-start"}`}>
      <span className="text-[0.6rem] md:text-xs font-medium tracking-[0.2em] text-slate-500 uppercase">
        {label}
      </span>
      <span className="text-xs md:text-sm font-semibold text-slate-300 tracking-wide">
        {value}
      </span>
    </div>
  );
}
