import React, { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { DiffViewer } from './DiffViewer';
import { StructuredForm } from './StructuredForm';
import type {
  HitlSuspensionData,
  InterventionPayload,
  Hyperparameters,
} from '@/types/workflow';

/**
 * InterventionDashboard 组件 Props
 */
interface InterventionDashboardProps {
  /** HITL 挂起数据 */
  hitlData: HitlSuspensionData;
  /** 会话 ID */
  sessionId: string;
  /** 恢复工作流的回调函数 */
  onResume: (payload: InterventionPayload) => Promise<void>;
  /** 可选：自定义类名 */
  className?: string;
}

/**
 * 结构化干预仪表板组件
 * 整合 Diff 视图和结构化表单，处理 HITL 干预流程
 */
export const InterventionDashboard: React.FC<InterventionDashboardProps> = ({
  hitlData,
  sessionId,
  onResume,
  className,
}) => {
  // 修改后的内容状态（初始值为原始提案）
  const [modifiedContent, setModifiedContent] = useState<string>(
    hitlData.originalProposal
  );

  // 超参数状态
  const [hyperparameters, setHyperparameters] = useState<Hyperparameters>(
    hitlData.currentHyperparameters
  );

  // 提交状态
  const [isSubmitting, setIsSubmitting] = useState(false);

  /**
   * 处理 Diff 视图中的内容变更
   */
  const handleContentChange = useCallback((value: string) => {
    setModifiedContent(value);
  }, []);

  /**
   * 处理超参数变更
   */
  const handleHyperparametersChange = useCallback((values: Hyperparameters) => {
    setHyperparameters(values);
  }, []);

  /**
   * 处理表单提交
   * 收集所有修改并调用 onResume 回调
   */
  const handleSubmit = useCallback(async () => {
    setIsSubmitting(true);

    try {
      // 构建提交载荷
      const payload: InterventionPayload = {
        sessionId,
        modifiedContent,
        originalContent: hitlData.originalProposal,
        hyperparameters,
        timestamp: new Date().toISOString(),
      };

      // 调用恢复回调
      await onResume(payload);
    } catch (error) {
      console.error('恢复工作流失败:', error);
      // 这里可以添加错误处理逻辑，如显示错误提示
    } finally {
      setIsSubmitting(false);
    }
  }, [sessionId, modifiedContent, hitlData.originalProposal, hyperparameters, onResume]);

  return (
    <div className={cn('flex flex-col h-full', className)} data-testid="intervention-dashboard">
      {/* 顶部说明区域 */}
      <div className="px-6 py-4 border-b border-border bg-card">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-500/10 flex items-center justify-center">
            <svg
              className="w-5 h-5 text-amber-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-foreground">
              需要人工干预
            </h3>
            <p className="text-sm text-muted-foreground mt-1">
              {hitlData.reason}
            </p>
          </div>
        </div>
      </div>

      {/* 主内容区域：Diff 视图 + 表单 */}
      <div className="flex-1 overflow-hidden flex flex-col lg:flex-row">
        {/* Diff 视图区域 */}
        <div className="flex-1 overflow-auto p-6 border-b lg:border-b-0 lg:border-r border-border">
          <DiffViewer
            original={hitlData.originalProposal}
            modified={modifiedContent}
            onChange={handleContentChange}
            showLineNumbers={true}
            darkMode={true}
          />
        </div>

        {/* 结构化表单区域 */}
        <div className="lg:w-96 overflow-auto p-6 bg-muted/30">
          <StructuredForm
            initialValues={hitlData.currentHyperparameters}
            availableDatasets={hitlData.availableDatasets}
            onChange={handleHyperparametersChange}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting}
          />
        </div>
      </div>
    </div>
  );
};

export default InterventionDashboard;
