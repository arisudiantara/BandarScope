import { cn } from "@/lib/utils";

/** Color a cell based on a -100..+100 score. */
function flowToColor(value: number): { bg: string; text: string } {
  const abs = Math.abs(value);
  if (value >= 60)   return { bg: "rgba(21, 128, 61, 0.85)",  text: "#fff" };  // bright green
  if (value >= 40)   return { bg: "rgba(34, 197, 94, 0.75)",  text: "#fff" };
  if (value >= 20)   return { bg: "rgba(74, 222, 128, 0.55)", text: "#fff" };
  if (value >= 5)    return { bg: "rgba(74, 222, 128, 0.30)", text: "#bbf7d0" };
  if (value > -5)    return { bg: "rgba(71, 85, 105, 0.30)",  text: "#94a3b8" };  // neutral
  if (value > -20)   return { bg: "rgba(248, 113, 113, 0.30)",text: "#fecaca" };
  if (value > -40)   return { bg: "rgba(248, 113, 113, 0.55)",text: "#fff" };
  if (value > -60)   return { bg: "rgba(239, 68, 68, 0.75)",  text: "#fff" };
  return { bg: "rgba(153, 27, 27, 0.85)", text: "#fff" };
}

interface FlowCellsProps {
  values: number[]; // length 6, oldest first (dn-5..dn-0)
  prefix?: "d" | "w";
}

export function FlowCells({ values, prefix = "d" }: FlowCellsProps) {
  return (
    <>
      {values.map((v, i) => {
        const idx = values.length - 1 - i;
        const colors = flowToColor(v);
        return (
          <td
            key={`${prefix}-${i}`}
            className="px-1 py-1 text-center tabular text-[10px] font-bold border-r border-bg/40"
            style={{ background: colors.bg, color: colors.text, minWidth: 42 }}
            title={`${prefix}n-${idx}: ${v >= 0 ? "+" : ""}${v.toFixed(1)}`}
          >
            {v > 0 ? "+" : ""}
            {v.toFixed(0)}
          </td>
        );
      })}
    </>
  );
}

export function FlowHeader({ prefix }: { prefix: "d" | "w" }) {
  return (
    <>
      {[5, 4, 3, 2, 1, 0].map((n) => (
        <th
          key={`${prefix}-h-${n}`}
          className="px-1 py-2 text-center text-[10px] font-medium text-text-muted border-r border-border/40 tabular"
          style={{ minWidth: 42 }}
        >
          {prefix}n-{n}
        </th>
      ))}
    </>
  );
}

/** MA flag cell: shows ✓/✗ + percentage distance. */
interface MAFlagProps {
  above: boolean;
  distance: number | null;
}

export function MAFlag({ above, distance }: MAFlagProps) {
  if (distance === null) {
    return (
      <td className="px-1 py-1 text-center text-text-muted text-[10px]">
        -
      </td>
    );
  }
  return (
    <td
      className={cn(
        "px-1 py-1 text-center text-[10px] tabular border-r border-border/30",
        above
          ? "text-accent-green bg-accent-green/5"
          : "text-accent-red bg-accent-red/5"
      )}
      title={`${above ? "✓" : "✗"} ${distance >= 0 ? "+" : ""}${distance.toFixed(2)}%`}
    >
      <div className="font-bold leading-tight">{above ? "✓" : "✗"}</div>
      <div className="text-[9px] opacity-70 leading-tight">
        {distance >= 0 ? "+" : ""}
        {distance.toFixed(1)}%
      </div>
    </td>
  );
}
