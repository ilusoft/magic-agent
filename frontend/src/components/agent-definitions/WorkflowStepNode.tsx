import clsx from 'clsx';
import type { NodeProps } from 'reactflow';
import { Handle, Position } from 'reactflow';

import type { WorkflowNodeData } from './types';

export function WorkflowStepNode({ data, selected }: NodeProps<WorkflowNodeData>) {
  const isPlaceholder = data.kind === 'placeholder';

  return (
    <div
      className={clsx(
        'relative rounded-lg border bg-card px-4 py-3 text-sm shadow-sm transition-shadow',
        selected ? 'ring-2 ring-primary' : 'ring-1 ring-transparent',
        isPlaceholder ? 'border-dashed border-border/70 text-foreground/70' : 'border-border text-foreground'
      )}
    >
      <Handle id="input" type="target" position={Position.Top} />
      <Handle id="outcomes" type="source" position={Position.Bottom} />
      <Handle
        id="tools"
        type="source"
        position={Position.Right}
        style={{ background: 'rgb(30 64 175)' }}
      />
      <span>{data.label}</span>
    </div>
  );
}
