/**
 * Workflow 组件导出索引
 */

export { WorkflowCanvas } from './WorkflowCanvas';
export { AutoGenerationView } from './AutoGenerationView';
export { InterventionDashboard } from './InterventionDashboard';
export { DiffViewer } from './DiffViewer';
export { StructuredForm } from './StructuredForm';

// 导出类型定义
export type {
  WorkflowStatus,
  Hyperparameters,
  InterventionPayload,
  HitlSuspensionData,
  AutoGenerationData,
  WorkflowCanvasProps,
  DiffViewerProps,
  StructuredFormProps,
} from '@/types/workflow';
