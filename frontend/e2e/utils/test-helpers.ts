/**
 * Playwright E2E 测试辅助工具
 *
 * 提供常用的测试辅助函数和 Mock 数据生成器
 */

import { Page, BrowserContext, expect } from '@playwright/test';

// ============================================================================
// 常量定义
// ============================================================================

/** 后端 API 基础 URL */
export const API_BASE_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/** 前端基础 URL */
export const FRONTEND_BASE_URL = process.env.FRONTEND_URL || 'http://localhost:5173';

/** 默认测试超时时间 */
export const DEFAULT_TIMEOUT = 30 * 1000;

/** SSE 连接超时时间 */
export const SSE_TIMEOUT = 10 * 1000;

// ============================================================================
// Mock 数据生成器
// ============================================================================

/**
 * 生成 Mock SSE 事件
 *
 * @param eventType 事件类型
 * @param sessionId 会话 ID
 * @param data 事件数据
 * @returns Mock SSE 事件对象
 */
export function createMockSSEEvent(
  eventType: string,
  sessionId: string,
  data: Record<string, any>
): Record<string, any> {
  return {
    event_type: eventType,
    timestamp: new Date().toISOString(),
    session_id: sessionId,
    data,
  };
}

/**
 * 生成 Mock 智能体思考事件
 */
export function createMockAgentThought(
  sessionId: string,
  agentName: string,
  thought: string
): Record<string, any> {
  return createMockSSEEvent('agent_thought', sessionId, {
    thought,
    agent_name: agentName,
  });
}

/**
 * 生成 Mock HITL 中断事件
 */
export function createMockHITLInterrupt(
  sessionId: string,
  reason: string,
  context: Record<string, any>
): Record<string, any> {
  return {
    event_type: 'hitl_interrupt',
    timestamp: new Date().toISOString(),
    session_id: sessionId,
    priority: 'high',
    data: {
      reason,
      context,
    },
  };
}

/**
 * 生成 Mock 工作流状态
 */
export function createMockWorkflowState(
  sessionId: string,
  status: string,
  stage: string
): Record<string, any> {
  return {
    id: Math.floor(Math.random() * 1000),
    session_id: sessionId,
    workflow_name: 'research_workflow',
    current_stage: stage,
    status,
    agent_state: {},
    human_feedback: null,
    error_message: null,
    metadata: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

// ============================================================================
// 网络请求 Mock 辅助函数
// ============================================================================

/**
 * 设置大模型 API Mock
 * 拦截所有大模型 API 调用，返回 Mock 响应
 *
 * @param page Playwright Page 对象
 */
export async function mockLLMAPI(page: Page): Promise<void> {
  await page.route('**/v1/chat/completions*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'mock-completion-id',
        object: 'chat.completion',
        created: Date.now(),
        model: 'gpt-4-mock',
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: '这是一个 Mock 的大模型响应，用于 E2E 测试。',
            },
            finish_reason: 'stop',
          },
        ],
        usage: {
          prompt_tokens: 100,
          completion_tokens: 50,
          total_tokens: 150,
        },
      }),
    });
  });
}

/**
 * 设置工作流 API Mock
 *
 * @param page Playwright Page 对象
 * @param sessionId 会话 ID
 * @param mockState Mock 工作流状态
 */
export async function mockWorkflowAPI(
  page: Page,
  sessionId: string,
  mockState: Record<string, any>
): Promise<void> {
  await page.route(`**/api/v1/workflow/session/${sessionId}**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([mockState]),
    });
  });
}

/**
 * 设置回滚 API Mock
 *
 * @param page Playwright Page 对象
 * @param sessionId 会话 ID
 * @param mockResponse Mock 回滚响应
 */
export async function mockRollbackAPI(
  page: Page,
  sessionId: string,
  mockResponse: Record<string, any>
): Promise<void> {
  await page.route(
    `**/api/v1/workflow/session/${sessionId}/rollback`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockResponse),
      });
    }
  );
}

// ============================================================================
// SSE 辅助函数
// ============================================================================

/**
 * 发布 SSE 事件到后端
 *
 * @param page Playwright Page 对象
 * @param event SSE 事件数据
 */
export async function publishSSEEvent(
  page: Page,
  event: Record<string, any>
): Promise<void> {
  await page.evaluate(async (eventData) => {
    const response = await fetch(`${API_BASE_URL}/api/stream/publish`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(eventData),
    });
    return response.json();
  }, event);
}

/**
 * 等待 SSE 连接建立
 *
 * @param page Playwright Page 对象
 * @param timeout 超时时间 (毫秒)
 */
export async function waitForSSEConnection(
  page: Page,
  timeout: number = SSE_TIMEOUT
): Promise<void> {
  await expect(page.locator('[data-testid="terminal-log-status"]')).toContainText(
    '实时连接',
    { timeout }
  );
}

// ============================================================================
// 页面交互辅助函数
// ============================================================================

/**
 * 等待页面加载完成
 *
 * @param page Playwright Page 对象
 */
export async function waitForPageReady(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
}

/**
 * 提交科研设想
 *
 * @param page Playwright Page 对象
 * @param idea 科研设想文本
 */
export async function submitResearchIdea(page: Page, idea: string): Promise<void> {
  const inputField = page.locator('[data-testid="research-idea-input"]');
  if (await inputField.isVisible()) {
    await inputField.fill(idea);
    await page.keyboard.press('Enter');
  }
}

/**
 * 点击 Saga 树中的历史节点
 *
 * @param page Playwright Page 对象
 * @param checkpointId 检查点 ID
 */
export async function clickSagaNode(
  page: Page,
  checkpointId: string
): Promise<void> {
  const node = page.locator(`[data-id="${checkpointId}"]`);
  await expect(node).toBeVisible();
  await node.click();
}

/**
 * 在回滚模态框中提交回滚请求
 *
 * @param page Playwright Page 对象
 * @param instruction 修改指令
 */
export async function submitRollback(
  page: Page,
  instruction: string
): Promise<void> {
  const modal = page.locator('[data-testid="rollback-modal"]');
  await expect(modal).toBeVisible();

  const input = modal.locator('textarea');
  await input.fill(instruction);

  const submitButton = modal.locator('button[type="submit"]');
  await submitButton.click();

  // 等待模态框关闭
  await expect(modal).not.toBeVisible();
}

/**
 * 在干预仪表板中提交反馈
 *
 * @param page Playwright Page 对象
 * @param feedback 反馈内容
 */
export async function submitHITLFeedback(
  page: Page,
  feedback: string
): Promise<void> {
  const dashboard = page.locator('[data-testid="intervention-dashboard"]');
  await expect(dashboard).toBeVisible();

  const input = dashboard.locator('textarea');
  if (await input.isVisible()) {
    await input.fill(feedback);
  }

  const submitButton = dashboard.locator('button:has-text("继续执行")');
  if (await submitButton.isVisible()) {
    await submitButton.click();
  }
}

// ============================================================================
// 断言辅助函数
// ============================================================================

/**
 * 断言 TerminalLog 包含指定日志内容
 *
 * @param page Playwright Page 对象
 * @param content 期望的日志内容
 */
export async function assertTerminalLogContains(
  page: Page,
  content: string
): Promise<void> {
  const terminalLog = page.locator('[data-testid="terminal-log"]');
  await expect(terminalLog).toContainText(content);
}

/**
 * 断言工作流状态指示器显示指定状态
 *
 * @param page Playwright Page 对象
 * @param status 期望的状态文本
 */
export async function assertWorkflowStatus(
  page: Page,
  status: string
): Promise<void> {
  const indicator = page.locator('[data-testid="workflow-status-indicator"]');
  await expect(indicator).toContainText(status);
}

/**
 * 断言干预仪表板可见
 *
 * @param page Playwright Page 对象
 */
export async function assertInterventionDashboardVisible(
  page: Page
): Promise<void> {
  const dashboard = page.locator('[data-testid="intervention-dashboard"]');
  await expect(dashboard).toBeVisible();
}

/**
 * 断言回滚模态框可见
 *
 * @param page Playwright Page 对象
 */
export async function assertRollbackModalVisible(page: Page): Promise<void> {
  const modal = page.locator('[data-testid="rollback-modal"]');
  await expect(modal).toBeVisible();
}
