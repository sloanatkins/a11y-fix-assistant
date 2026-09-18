import type { Level } from "../api";
import { LEVEL_LABELS } from "../labels";

function LevelBadge({ level }: { level: Level }) {
  return <span className={`badge badge-${level}`}>{LEVEL_LABELS[level]}</span>;
}

export default LevelBadge;
