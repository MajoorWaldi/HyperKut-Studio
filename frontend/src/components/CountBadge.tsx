/** A small round number beside a title: how many things are switched on or changed inside it. Nothing when there are none. */
export function CountBadge({ count, label }: { count: number; label: string }) {
  return count > 0 ? <span className="count-badge" role="img" aria-label={`${count} ${label}`}>{count}</span> : null
}
