/**
 * WorkflowCanvas 组件单元测试
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WorkflowCanvas } from './WorkflowCanvas';
import type {
  WorkflowCanvasProps,
  AutoGenerationData,
  HitlSuspensionData,
  InterventionPayload,
} from '@/types/workflow';

// Mock ResizeObserver (Radix UI 需要)
class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
global.ResizeObserver = ResizeObserverMock as any;

// Mock fetch API
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('WorkflowCanvas', () => {
  // 默认测试数据
  const defaultSessionId = 'test-session-123';

  const defaultAutoGenerationData: AutoGenerationData = {
    content: '# 测试标题\n\n这是一段测试内容。',
    contentType: 'markdown',
    title: '科研综述草稿',
    progress: 75,
  };

  const defaultHitlData: HitlSuspensionData = {
    nodeId: 'node-456',
    originalProposal: '原始 AI 提案内容\n第二行内容',
    currentHyperparameters: {
      temperature: 0.7,
      topP: 0.9,
      maxTokens: 2048,
      datasetPath: '/data/default.csv',
    },
    availableDatasets: [
      '/data/default.csv',
      '/data/alternative.csv',
    ],
    reason: '需要人工审核生成的综述内容',
  };

  // 清理 mock
  beforeEach(() => {
    mockFetch.mockClear();
  });

  /**
   * 测试 1: RUNNING 状态应渲染 AutoGenerationView
   */
  it('RUNNING 状态时应渲染自动生成视图', () => {
    const props: WorkflowCanvasProps = {
      status: 'RUNNING',
      sessionId: defaultSessionId,
      autoGenerationData: defaultAutoGenerationData,
    };

    render(<WorkflowCanvas {...props} />);

    // 验证标题渲染
    expect(screen.getByText('科研综述草稿')).toBeDefined();

    // 验证进度显示
    expect(screen.getByText('生成进度')).toBeDefined();
    expect(screen.getByText('75%')).toBeDefined();

    // 验证状态指示器
    expect(screen.getByText('执行中')).toBeDefined();
  });

  /**
   * 测试 2: COMPLETED 状态应渲染 AutoGenerationView
   */
  it('COMPLETED 状态时应渲染自动生成视图', () => {
    const props: WorkflowCanvasProps = {
      status: 'COMPLETED',
      sessionId: defaultSessionId,
      autoGenerationData: defaultAutoGenerationData,
    };

    render(<WorkflowCanvas {...props} />);

    expect(screen.getByText('科研综述草稿')).toBeDefined();
    expect(screen.getByText('已完成')).toBeDefined();
  });

  /**
   * 测试 3: ERROR 状态应渲染错误视图
   */
  it('ERROR 状态时应渲染错误视图', () => {
    const props: WorkflowCanvasProps = {
      status: 'ERROR',
      sessionId: defaultSessionId,
    };

    render(<WorkflowCanvas {...props} />);

    expect(screen.getByText('执行出错')).toBeDefined();
    expect(screen.getByText('出错')).toBeDefined();
  });

  /**
   * 测试 4: WAITING_FOR_HUMAN 状态应渲染 InterventionDashboard
   */
  it('WAITING_FOR_HUMAN 状态时应渲染干预仪表板', () => {
    const props: WorkflowCanvasProps = {
      status: 'WAITING_FOR_HUMAN',
      sessionId: defaultSessionId,
      hitlData: defaultHitlData,
    };

    render(<WorkflowCanvas {...props} />);

    // 验证干预提示
    expect(screen.getByText('需要人工干预')).toBeDefined();
    expect(screen.getByText('需要人工审核生成的综述内容')).toBeDefined();

    // 验证超参数表单
    expect(screen.getByText('超参数调整')).toBeDefined();
    expect(screen.getByText('Temperature（温度）')).toBeDefined();

    // 验证状态指示器
    expect(screen.getByText('等待干预')).toBeDefined();
  });

  /**
   * 测试 5: 缺少数据时应渲染空状态
   */
  it('缺少必要数据时应渲染空状态', () => {
    const props: WorkflowCanvasProps = {
      status: 'RUNNING',
      sessionId: defaultSessionId,
    };

    render(<WorkflowCanvas {...props} />);

    expect(screen.getByText('等待内容生成...')).toBeDefined();
  });

  /**
   * 测试 6: 结构化表单提交应输出预期结构的 JSON 对象
   */
  it('结构化表单提交应输出预期结构的 JSON 对象', async () => {
    const user = userEvent.setup();
    const mockOnResume = vi.fn().mockResolvedValue(undefined);

    const props: WorkflowCanvasProps = {
      status: 'WAITING_FOR_HUMAN',
      sessionId: defaultSessionId,
      hitlData: defaultHitlData,
      onResume: mockOnResume,
    };

    render(<WorkflowCanvas {...props} />);

    // 点击提交按钮
    const submitButton = screen.getByText('确认并恢复工作流');
    await user.click(submitButton);

    // 验证回调被调用
    await waitFor(() => {
      expect(mockOnResume).toHaveBeenCalledTimes(1);
    });

    // 验证提交载荷的结构
    const calledPayload: InterventionPayload = mockOnResume.mock.calls[0][0];

    // 断言：载荷包含所有必需字段
    expect(calledPayload).toHaveProperty('sessionId');
    expect(calledPayload).toHaveProperty('modifiedContent');
    expect(calledPayload).toHaveProperty('originalContent');
    expect(calledPayload).toHaveProperty('hyperparameters');
    expect(calledPayload).toHaveProperty('timestamp');

    // 断言：sessionId 正确
    expect(calledPayload.sessionId).toBe(defaultSessionId);

    // 断言：原始内容正确
    expect(calledPayload.originalContent).toBe(defaultHitlData.originalProposal);

    // 断言：超参数结构正确
    expect(calledPayload.hyperparameters).toHaveProperty('temperature');
    expect(calledPayload.hyperparameters).toHaveProperty('topP');
    expect(calledPayload.hyperparameters).toHaveProperty('maxTokens');
    expect(calledPayload.hyperparameters).toHaveProperty('datasetPath');

    // 断言：timestamp 是有效的 ISO 字符串
    expect(new Date(calledPayload.timestamp).toISOString()).toBe(calledPayload.timestamp);
  });

  /**
   * 测试 7: 提交按钮应有 Loading 状态
   */
  it('提交按钮应有 Loading 状态', async () => {
    const user = userEvent.setup();

    // 创建一个延迟的 mock 函数
    const mockOnResume = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 1000))
    );

    const props: WorkflowCanvasProps = {
      status: 'WAITING_FOR_HUMAN',
      sessionId: defaultSessionId,
      hitlData: defaultHitlData,
      onResume: mockOnResume,
    };

    render(<WorkflowCanvas {...props} />);

    // 点击提交按钮
    const submitButton = screen.getByText('确认并恢复工作流');
    await user.click(submitButton);

    // 验证 Loading 状态显示
    await waitFor(() => {
      expect(screen.getByText('提交中...')).toBeDefined();
    });
  });

  /**
   * 测试 8: 默认 API 调用应使用正确的端点
   */
  it('默认 API 调用应使用正确的端点', async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });

    const props: WorkflowCanvasProps = {
      status: 'WAITING_FOR_HUMAN',
      sessionId: defaultSessionId,
      hitlData: defaultHitlData,
      // 不提供 onResume，使用默认实现
    };

    render(<WorkflowCanvas {...props} />);

    // 点击提交按钮
    const submitButton = screen.getByText('确认并恢复工作流');
    await user.click(submitButton);

    // 验证 fetch 被调用
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    // 验证请求参数
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe(`/api/workflows/${defaultSessionId}/resume`);
    expect(options.method).toBe('POST');
    expect(options.headers['Content-Type']).toBe('application/json');

    // 验证请求体是有效的 JSON
    const body = JSON.parse(options.body);
    expect(body).toHaveProperty('sessionId');
    expect(body).toHaveProperty('modifiedContent');
    expect(body).toHaveProperty('hyperparameters');
  });
});
