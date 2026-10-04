import { useState } from "react";
import type { TrajectoryPoint } from "../lib/trajectory";
import { formatCpm, formatLog2, formatMetaAge } from "../lib/format";

interface Props {
  points: TrajectoryPoint[];
  symbol: string;
}

/** Plain-table view of everything the chart shows — the no-hover fallback. */
export function SampleTable({ points, symbol }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <section className="table-section">
      <button
        type="button"
        className="table-toggle"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={`table-chevron${open ? " is-open" : ""}`} aria-hidden="true">
          ▸
        </span>
        {open ? "Hide" : "Show"} sample table
        <span className="table-count">{points.length} rows</span>
      </button>
      {open && (
        <div className="table-scroll" role="region" aria-label={`${symbol} expression by sample`} tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th scope="col">Sample</th>
                <th scope="col">Age</th>
                <th scope="col">Period</th>
                <th scope="col">Sex</th>
                <th scope="col" className="num">CPM</th>
                <th scope="col" className="num">log₂(CPM+10⁻³)</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.sample.id}>
                  <td>{p.sample.id}</td>
                  <td>{formatMetaAge(p.sample)}</td>
                  <td>P{p.sample.period}</td>
                  <td>{p.sample.sex}</td>
                  <td className="num">{formatCpm(p.cpm)}</td>
                  <td className="num">{formatLog2(p.y)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
