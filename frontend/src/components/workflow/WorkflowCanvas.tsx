import React, { useCallback } from 'react';
import { cn } from '@/lib/utils';
import { AutoGenerationView } from './AutoGenerationView';
import { InterventionDashboard } from './InterventionDashboard';
import type {
  WorkflowCanvasProps,
  InterventionPayload,
  WorkflowStatus,
} from '@/types/workflow';

/**
 * 判断是否应该显示自动生成视图
 * RUNNING、COMPLETED、ERROR 状态都显示自动生成视图
 */
const shouldShowAutoGeneration = (status: WorkflowStatus): boolean => {
  return ['RUNNING', 'COMPLETED', 'ERROR'].includes(status);
};

/**
 * WorkflowCanvas 主组件
 * 根据工作流状态渲染对应的视图
 */
export const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({
  status,
  sessionId,
  autoGenerationData,
  hitlData,
  onResume,
  className,
}) => {
  /**
   * 处理恢复工作流的提交
   * 模拟调用后端 API 并实现防抖和 Loading 状态
   */
  const handleResume = useCallback(
    async (payload: InterventionPayload) => {
      // 如果没有提供 onResume 回调，使用默认实现
      if (onResume) {
        await onResume(payload);
        return;
      }

      // 默认实现：模拟 API 调用
      try {
        console.log('恢复工作流 - 请求载荷:', payload);

        // 模拟调用后端 POST /workflows/{session_id}/resume 接口
        const response = await fetch(
          `/api/workflows/${sessionId}/resume`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          }
        );

        if (!response.ok) {
          throw new Error(`API 请求失败: ${response.status}`);
        }

        const result = await response.json();
        console.log('工作流恢复成功:', result);
      } catch (error) {
        console.error('恢复工作流失败:', error);
        throw error;
      }
    },
    [sessionId, onResume]
  );

  /**
   * 渲染空状态
   * 当缺少必要数据时显示
   */
  const renderEmptyState = () => (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
          <svg
            className="w-8 h-8 text-muted-foreground"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        </div>
        <p className="text-muted-foreground">等待内容生成...</p>
      </div>
    </div>
  );

  /**
   * 渲染错误状态
   */
  const renderErrorState = () => (
    <div className="flex items-center justify-center h-full">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-destructive/10 flex items-center justify-center">
          <svg
            className="w-8 h-8 text-destructive"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-foreground mb-2">
          执行出错
        </h3>
        <p className="text-sm text-muted-foreground">
          工作流执行过程中发生错误，请检查日志或联系管理员。
        </p>
      </div>
    </div>
  );

  /**
   * 根据状态渲染对应视图
   */
  const renderContent = () => {
    // 错误状态
    if (status === 'ERROR') {
      return renderErrorState();
    }

    // 自动生成视图（RUNNING 或 COMPLETED）
    if (shouldShowAutoGeneration(status)) {
      if (!autoGenerationData) {
        return renderEmptyState();
      }
      return <AutoGenerationView data={autoGenerationData} />;
    }

    // 结构化干预仪表板（WAITING_FOR_HUMAN）
    if (status === 'WAITING_FOR_HUMAN') {
      if (!hitlData) {
        return renderEmptyState();
      }
      return (
        <InterventionDashboard
          hitlData={hitlData}
          sessionId={sessionId}
          onResume={handleResume}
        />
      );
    }

    // 默认：空状态
    return renderEmptyState();
  };

  return (
    <div
      className={cn(
        'relative w-full h-full bg-background overflow-hidden',
        'transition-all duration-300 ease-in-out',
        className
      )}
      data-testid="workflow-canvas"
    >
      {/* 状态指示器（右上角） */}
      <div className="absolute top-4 right-4 z-10" data-testid="workflow-status-indicator">
        <div
          className={cn(
            'px-3 py-1.5 rounded-full text-xs font-medium',
            'flex items-center gap-2 shadow-sm',
            status === 'RUNNING' && 'bg-blue-500/10 text-blue-500',
            status === 'WAITING_FOR_HUMAN' && 'bg-amber-500/10 text-amber-500',
            status === 'COMPLETED' && 'bg-green-500/10 text-green-500',
            status === 'ERROR' && 'bg-red-500/10 text-red-500'
          )}
        >
          {/* 状态图标 */}
          {status === 'RUNNING' && (
            <svg
              className="w-3.5 h-3.5 animate-spin"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.162 5.826 3 7.936l3-2.647z"
              />
            </svg>
          )}
          {status === 'WAITING_FOR_HUMAN' && (
            <svg
              className="w-3.5 h-3.5"
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
          )}
          {status === 'COMPLETED' && (
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          )}
          {status === 'ERROR' && (
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          )}
          {/* 状态文本 */}
          <span>
            {status === 'RUNNING' && '执行中'}
            {status === 'WAITING_FOR_HUMAN' && '等待干预'}
            {status === 'COMPLETED' && '已完成'}
            {status === 'ERROR' && '出错'}
          </span>
        </div>
      </div>

      {/* 主内容区域 */}
      {renderContent()}
    </div>
  );
};

export default WorkflowCanvas;
