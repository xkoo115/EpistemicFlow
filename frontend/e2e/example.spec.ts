/**
 * E2E 测试示例
 *
 * 本文件展示如何使用测试辅助工具编写简洁的 E2E 测试
 */

import { test, expect } from '@playwright/test';
import {
  DEFAULT_TIMEOUT,
  createMockAgentThought,
  createMockHITLInterrupt,
  createMockWorkflowState,
  mockLLMAPI,
  mockWorkflowAPI,
  mockRollbackAPI,
  publishSSEEvent,
  waitForSSEConnection,
  waitForPageReady,
  submitResearchIdea,
  clickSagaNode,
  submitRollback,
  submitHITLFeedback,
  assertTerminalLogContains,
  assertWorkflowStatus,
  assertInterventionDashboardVisible,
  assertRollbackModalVisible,
} from './utils/test-helpers';

// ============================================================================
// 测试配置
// ============================================================================

const TEST_SESSION_ID = 'test-session-example';

test.describe('E2E 测试示例', () => {
  test.setTimeout(DEFAULT_TIMEOUT);

  test.beforeEach(async ({ page }) => {
    // 设置 Mock
    await mockLLMAPI(page);

    // 导航到页面
    await page.goto('/');
    await waitForPageReady(page);
  });

  test('使用辅助函数简化测试代码', async ({ page }) => {
    // 1. 等待 SSE 连接
    await waitForSSEConnection(page);

    // 2. 提交科研设想
    await submitResearchIdea(page, '研究人工智能在药物发现中的应用');

    // 3. 发布 Mock SSE 事件
    const thoughtEvent = createMockAgentThought(
      TEST_SESSION_ID,
      '首席研究员',
      '正在分析科研设想...'
    );
    await publishSSEEvent(page, thoughtEvent);

    // 4. 断言日志渲染
    await assertTerminalLogContains(page, '正在分析科研设想');

    console.log('✅ 测试通过');
  });

  test('HITL 干预流程', async ({ page }) => {
    // 设置工作流状态 Mock
    const mockState = createMockWorkflowState(
      TEST_SESSION_ID,
      'WAITING_FOR_HUMAN',
      'plan_generation'
    );
    await mockWorkflowAPI(page, TEST_SESSION_ID, mockState);

    // 等待 SSE 连接
    await waitForSSEConnection(page);

    // 发布 HITL 中断事件
    const hitlEvent = createMockHITLInterrupt(
      TEST_SESSION_ID,
      'WAITING_FOR_HUMAN',
      {
        message: '请审核科研计划',
        generated_plan: { title: '测试计划' },
      }
    );
    await publishSSEEvent(page, hitlEvent);

    // 断言干预仪表板显示
    await assertInterventionDashboardVisible(page);

    // 断言状态指示器
    await assertWorkflowStatus(page, '等待干预');

    console.log('✅ HITL 干预流程测试通过');
  });

  test('Saga 回滚流程', async ({ page }) => {
    // 设置回滚 API Mock
    await mockRollbackAPI(page, TEST_SESSION_ID, {
      original_checkpoint_id: 1,
      new_checkpoint_id: 2,
      new_session_id: 'new-session',
      message: '回滚成功',
    });

    // 等待 SSE 连接
    await waitForSSEConnection(page);

    // 点击历史节点
    await clickSagaNode(page, 'cp-2');

    // 断言回滚模态框显示
    await assertRollbackModalVisible(page);

    // 提交回滚
    await submitRollback(page, '修改研究方法');

    // 断言状态更新
    await assertWorkflowStatus(page, '执行中');

    console.log('✅ Saga 回滚流程测试通过');
  });
});
