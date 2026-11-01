import { SecondsField } from '../components/Toolbar'
export const SecondsFieldForTest = ({ value, onCommit }: { value: number; onCommit: (n: number) => void }) =>
  <SecondsField value={value} disabled={false} label="seconds" onCommit={onCommit} />
