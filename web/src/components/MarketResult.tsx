import { Link } from "react-router-dom";
import type {
  AssetComparison,
  AssetDossier,
  CompanyPipeline,
  IndicationMap,
  Landscape,
  LandscapeDiff,
  MarketAnswer,
  MilestoneRadar,
  MoaLandscape,
} from "../lib/types";
import { ApprovalsList } from "./ApprovalsList";
import { ChangeFeed } from "./ChangeFeed";
import { CompareView } from "./CompareView";
import { Icon } from "./Icon";
import { MoaView } from "./MoaView";
import { PipelineBoard } from "./PipelineBoard";
import { RadarView } from "./RadarView";

// The front-door renderer: switch a routed answer's payload to the SAME component
// its dedicated view uses — existing screens (landscape/company/dossier/indication)
// and new lenses (changes/compare/radar/moa) alike. This is what ties it together.
export function MarketResult({ answer }: { answer: MarketAnswer }) {
  const r = answer.result;
  switch (answer.tool) {
    case "changes":
      return <ChangeFeed diff={r as LandscapeDiff} />;
    case "radar":
      return <RadarView radar={r as MilestoneRadar} />;
    case "compare":
      return <CompareView comparison={r as AssetComparison} />;
    case "moa":
      return <MoaView moa={r as MoaLandscape} />;
    case "company": {
      const cp = r as CompanyPipeline;
      return (
        <div className="space-y-3">
          <PipelineBoard cells={cp.cells} asOf={cp.as_of} condition={cp.sponsor} indication={null} />
          {cp.approvals.length > 0 && <ApprovalsList approvals={cp.approvals} />}
          <Link
            to={`/company/${encodeURIComponent(cp.sponsor)}`}
            className="inline-flex items-center gap-1 text-[13px] text-accent hover:underline"
          >
            Open {cp.sponsor}'s full pipeline <Icon name="arrow_forward" size={14} />
          </Link>
        </div>
      );
    }
    case "dossier": {
      const d = r as AssetDossier;
      return (
        <div className="rounded-md hairline bg-card-light p-4">
          <div className="text-[15px] font-medium text-ink-light">{d.asset.name}</div>
          <div className="mt-1 text-[13px] text-ink-muted-light">
            {d.trials.length} trial{d.trials.length === 1 ? "" : "s"} · {d.readouts.length} readout
            {d.readouts.length === 1 ? "" : "s"} · {d.approvals.length} approval
            {d.approvals.length === 1 ? "" : "s"}
          </div>
          <Link
            to={`/asset/${encodeURIComponent(d.asset.name)}`}
            className="mt-2 inline-flex items-center gap-1 text-[13px] text-accent hover:underline"
          >
            Open the full dossier <Icon name="arrow_forward" size={14} />
          </Link>
        </div>
      );
    }
    case "indication": {
      const im = r as IndicationMap;
      return (
        <div className="rounded-md hairline bg-card-light p-4">
          <div className="text-[15px] font-medium text-ink-light">{im.indication}</div>
          <div className="mt-1 text-[13px] text-ink-muted-light">
            {im.nodes.length} sub-population{im.nodes.length === 1 ? "" : "s"}
          </div>
          <Link
            to={`/indication/${encodeURIComponent(im.indication)}`}
            className="mt-2 inline-flex items-center gap-1 text-[13px] text-accent hover:underline"
          >
            Open the indication map <Icon name="arrow_forward" size={14} />
          </Link>
        </div>
      );
    }
    default: {
      const ls = r as Landscape;
      return (
        <PipelineBoard cells={ls.cells} asOf={ls.as_of} condition={ls.condition} indication={null} />
      );
    }
  }
}
