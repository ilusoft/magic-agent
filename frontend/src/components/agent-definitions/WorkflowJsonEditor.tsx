import { CustomJsonEditor } from "./CustomJsonEditor";

interface WorkflowJsonEditorProps {
  value: string;
  error: string | null;
  onChange: (value: string) => void;
}

export function WorkflowJsonEditor({
  value,
  error,
  onChange,
}: WorkflowJsonEditorProps) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground/80">
        Raw Agent Definitions (JSON)
      </label>
      <CustomJsonEditor
        value={value}
        onChange={onChange}
        height="calc(97vh - 16rem)"
      />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
