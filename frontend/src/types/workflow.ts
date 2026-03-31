/**
 * WorkflowCanvas 相关的 TypeScript 接口定义
 * 用于主画布组件的状态管理和数据交互
 */

/**
 * 工作流执行状态枚举
 * - PENDING: 待处理
 * - RUNNING: 正常执行中，显示自动生成视图
 * - PAUSED: HITL 挂起，显示结构化干预仪表板
 * - COMPLETED: 工作流完成
 * - FAILED: 执行出错
 * - CANCELLED: 已取消
 */
export enum WorkflowStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

/**
 * 工作流阶段枚举
 */
export enum WorkflowStage {
  INITIALIZATION = 'initialization',
  CONCEPTION = 'conception',
  LITERATURE_REVIEW = 'literature_review',
  METHODOLOGY_DESIGN = 'methodology_design',
  DATA_COLLECTION = 'data_collection',
  ANALYSIS = 'analysis',
  WRITING = 'writing',
  REVIEW = 'review',
  COMPLETION = 'completion',
  ERROR = 'error',
}

/**
 * 论文类型枚举
 */
export enum PaperType {
  RESEARCH_PAPER = 'research_paper',
  SURVEY_PAPER = 'survey_paper',
}

/**
 * 超参数配置接口
 * 用于结构化干预表单中的参数调整
 */
export interface Hyperparameters {
  /** 模型温度参数，控制生成随机性 (0-2) */
  temperature: number;
  /** Top-p 采样参数 (0-1) */
  topP: number;
  /** 最大生成 token 数 */
  maxTokens: number;
  /** 数据集路径 */
  datasetPath: string;
  /** 可选：模型选择 */
  model?: string;
}

/**
 * HITL 干预请求数据接口
 * 当用户完成干预后，提交给后端的数据结构
 */
export interface InterventionPayload {
  /** 会话 ID */
  sessionId: string;
  /** 修改后的文本内容 */
  modifiedContent: string;
  /** 原始 AI 提案内容 */
  originalContent: string;
  /** 调整后的超参数 */
  hyperparameters: Hyperparameters;
  /** 用户干预时间戳 */
  timestamp: string;
  /** 可选：用户备注 */
  userNote?: string;
}

/**
 * HITL 挂起状态数据接口
 * 后端返回的挂起状态详细信息
 */
export interface HitlSuspensionData {
  /** 挂起节点 ID */
  nodeId: string;
  /** 原始 AI 提案内容 */
  originalProposal: string;
  /** 当前超参数配置 */
  currentHyperparameters: Hyperparameters;
  /** 可选的数据集路径列表 */
  availableDatasets?: string[];
  /** 挂起原因说明 */
  reason: string;
}

/**
 * 自动生成视图的渲染数据接口
 */
export interface AutoGenerationData {
  /** Markdown 格式的内容 */
  content: string;
  /** 内容类型标识 */
  contentType: 'markdown' | 'code' | 'mixed';
  /** 可选：标题 */
  title?: string;
  /** 可选：生成进度 (0-100) */
  progress?: number;
}

/**
 * WorkflowCanvas 主组件的 Props 接口
 */
export interface WorkflowCanvasProps {
  /** 当前工作流状态 */
  status: WorkflowStatus;
  /** 会话 ID */
  sessionId: string;
  /** 自动生成视图数据 */
  autoGenerationData?: AutoGenerationData;
  /** HITL 挂起数据 */
  hitlData?: HitlSuspensionData;
  /** 恢复工作流的回调函数 */
  onResume?: (payload: InterventionPayload) => Promise<void>;
  /** 可选：自定义类名 */
  className?: string;
}

/**
 * Diff 视图组件的 Props 接口
 */
export interface DiffViewerProps {
  /** 原始内容（左侧） */
  original: string;
  /** 修改后的内容（右侧，可编辑） */
  modified: string;
  /** 内容变更回调 */
  onChange: (value: string) => void;
  /** 可选：是否显示行号 */
  showLineNumbers?: boolean;
  /** 可选：是否启用深色模式 */
  darkMode?: boolean;
}

/**
 * 结构化表单组件的 Props 接口
 */
export interface StructuredFormProps {
  /** 初始超参数值 */
  initialValues: Hyperparameters;
  /** 可选的数据集列表 */
  availableDatasets?: string[];
  /** 表单值变更回调 */
  onChange: (values: Hyperparameters) => void;
  /** 表单提交回调 */
  onSubmit: () => void;
  /** 是否处于提交中状态 */
  isSubmitting?: boolean;
}
