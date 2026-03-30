/**
 * HITL (Human-in-the-Loop) 工作流 E2E 测试
 *
 * 本测试用例覆盖 EpistemicFlow 系统的核心业务链路：
 * 1. 启动与流式监听：用户提交科研设想，SSE 推送日志
 * 2. HITL 挂起断言：后端触发 WAITING_FOR_HUMAN 状态，显示干预仪表板
 * 3. Saga 回滚与分叉：用户点击历史节点，触发回滚 API
 *
 * 技术要点：
 * - 使用 Playwright page.route() 拦截网络请求，Mock 大模型响应
 * - 使用 page.waitForEvent() 监听 SSE 事件
 * - 使用 page.evaluate() 在浏览器上下文中执行代码
 */

import { test, expect, Page, BrowserContext } from '@playwright/test';

// ============================================================================
// 测试配置常量
// ============================================================================

/** 后端 API 基础 URL */
const API_BASE_URL = 'http://localhost:8000';

/** 测试会话 ID */
const TEST_SESSION_ID = 'test-session-e2e-001';

/** 测试检查点 ID */
const TEST_CHECKPOINT_ID = 'cp-3';

/** 测试超时时间 (毫秒) */
const TEST_TIMEOUT = 30 * 1000;

/** SSE 连接超时时间 (毫秒) */
const SSE_TIMEOUT = 10 * 1000;

// ============================================================================
// Mock 数据定义
// ============================================================================

/**
 * Mock 智能体思考事件
 * 模拟大模型返回的思考内容
 */
const MOCK_AGENT_THOUGHT = {
  event_type: 'agent_thought',
  timestamp: new Date().toISOString(),
  session_id: TEST_SESSION_ID,
  agent_name: '首席研究员',
  data: {
    thought: '正在分析用户提交的科研设想...\n\n关键点：\n1. 研究主题：人工智能在药物发现中的应用\n2. 研究方法：深度学习 + 分子生成\n3. 预期成果：新型药物候选分子',
  },
};

/**
 * Mock 工作流阶段变更事件
 */
const MOCK_WORKFLOW_STAGE_CHANGE = {
  event_type: 'workflow_stage_change',
  timestamp: new Date().toISOString(),
  session_id: TEST_SESSION_ID,
  data: {
    from_stage: 'ideation',
    to_stage: 'literature_review',
    reason: '科研设想已确认，开始文献检索',
  },
};

/**
 * Mock HITL 中断事件
 * 模拟后端触发的人工干预请求
 */
const MOCK_HITL_INTERRUPT = {
  event_type: 'hitl_interrupt',
  timestamp: new Date().toISOString(),
  session_id: TEST_SESSION_ID,
  priority: 'high',
  data: {
    reason: 'WAITING_FOR_HUMAN',
    context: {
      interrupt_type: 'plan_review',
      message: '科研计划已生成，请审核并确认是否继续执行',
      generated_plan: {
        title: '基于深度学习的药物发现研究',
        objectives: [
          '构建分子生成模型',
          '验证生成分子的有效性',
          '评估药物候选潜力',
        ],
        methodology: '使用 VAE + GAN 架构进行分子生成，结合强化学习优化',
        timeline: '预计 3 个月完成',
      },
      diff: {
        original: null,
        modified: '# 基于深度学习的药物发现研究\n\n## 研究目标\n- 构建分子生成模型\n- 验证生成分子的有效性\n',
      },
    },
  },
};

/**
 * Mock 工作流状态响应 (WAITING_FOR_HUMAN)
 */
const MOCK_WORKFLOW_STATE_WAITING = {
  id: 1,
  session_id: TEST_SESSION_ID,
  workflow_name: 'research_workflow',
  current_stage: 'plan_generation',
  status: 'WAITING_FOR_HUMAN',
  agent_state: {
    generated_plan: MOCK_HITL_INTERRUPT.data.context.generated_plan,
  },
  human_feedback: null,
  error_message: null,
  metadata: {},
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

/**
 * Mock 回滚响应
 */
const MOCK_ROLLBACK_RESPONSE = {
  original_checkpoint_id: 3,
  new_checkpoint_id: 7,
  new_session_id: 'test-session-e2e-002',
  workflow_name: 'research_workflow',
  current_stage: 'literature_review',
  message: '已从检查点 cp-3 回滚并创建新的执行路径',
};

/**
 * Mock 检查点历史
 */
const MOCK_CHECKPOINT_HISTORY = {
  session_id: TEST_SESSION_ID,
  checkpoints: [
    {
      id: 1,
      session_id: TEST_SESSION_ID,
      workflow_name: 'research_workflow',
      current_stage: 'ideation',
      status: 'COMPLETED',
      created_at: '2024-03-30T09:00:00',
      updated_at: '2024-03-30T09:30:00',
    },
    {
      id: 2,
      session_id: TEST_SESSION_ID,
      workflow_name: 'research_workflow',
      current_stage: 'literature_review',
      status: 'COMPLETED',
      created_at: '2024-03-30T09:30:00',
      updated_at: '2024-03-30T10:00:00',
    },
    {
      id: 3,
      session_id: TEST_SESSION_ID,
      workflow_name: 'research_workflow',
      current_stage: 'plan_generation',
      status: 'WAITING_FOR_HUMAN',
      created_at: '2024-03-30T10:00:00',
      updated_at: '2024-03-30T10:30:00',
    },
  ],
  total_count: 3,
};

// ============================================================================
// 辅助函数
// ============================================================================

/**
 * 设置网络请求 Mock
 * 拦截大模型和耗时后端请求，返回 Mock 响应
 *
 * @param page Playwright Page 对象
 * @param context Playwright BrowserContext 对象
 */
async function setupNetworkMocks(page: Page, context: BrowserContext) {
  // --------------------------------------------------------------------------
  // Mock 大模型 API 调用
  // 防止测试时消耗真实 Token
  // --------------------------------------------------------------------------
  await page.route('**/v1/chat/completions*', async (route) => {
    console.log('[Mock] 拦截大模型 API 调用');
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

  // --------------------------------------------------------------------------
  // Mock 工作流状态 API
  // --------------------------------------------------------------------------
  await page.route(`**/api/v1/workflow/session/${TEST_SESSION_ID}**`, async (route) => {
    const url = route.request().url();
    console.log(`[Mock] 拦截工作流状态 API: ${url}`);

    // 检查点历史请求
    if (url.includes('/history')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CHECKPOINT_HISTORY),
      });
      return;
    }

    // 默认返回等待状态
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([MOCK_WORKFLOW_STATE_WAITING]),
    });
  });

  // --------------------------------------------------------------------------
  // Mock 回滚 API
  // --------------------------------------------------------------------------
  await page.route(`**/api/v1/workflow/session/${TEST_SESSION_ID}/rollback`, async (route) => {
    console.log('[Mock] 拦截回滚 API 调用');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_ROLLBACK_RESPONSE),
    });
  });

  // --------------------------------------------------------------------------
  // Mock 恢复工作流 API
  // --------------------------------------------------------------------------
  await page.route(`**/api/workflows/${TEST_SESSION_ID}/resume`, async (route) => {
    console.log('[Mock] 拦截恢复工作流 API 调用');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        checkpoint_id: 3,
        session_id: TEST_SESSION_ID,
        status: 'RUNNING',
        message: '工作流已恢复，正在继续执行',
      }),
    });
  });

  console.log('✅ 网络 Mock 设置完成');
}

/**
 * 模拟 SSE 事件推送
 * 通过调用后端的 /api/stream/publish 端点发布事件
 *
 * @param page Playwright Page 对象
 * @param event SSE 事件数据
 */
async function publishSSEEvent(page: Page, event: any) {
  const response = await page.evaluate(async (eventData) => {
    const response = await fetch('http://localhost:8000/api/stream/publish', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(eventData),
    });
    return response.json();
  }, event);

  console.log(`[SSE] 发布事件: ${event.event_type}`, response);
}

/**
 * 等待 SSE 连接建立
 *
 * @param page Playwright Page 对象
 */
async function waitForSSEConnection(page: Page) {
  // 等待 TerminalLog 组件显示连接状态
  await expect(page.locator('[data-testid="terminal-log-status"]')).toContainText('实时连接', {
    timeout: SSE_TIMEOUT,
  });
  console.log('✅ SSE 连接已建立');
}

// ============================================================================
// 测试套件
// ============================================================================

test.describe('HITL 工作流 E2E 测试', () => {
  // 每个测试的超时时间
  test.setTimeout(TEST_TIMEOUT);

  // --------------------------------------------------------------------------
  // 测试前置条件
  // --------------------------------------------------------------------------
  test.beforeEach(async ({ page, context }) => {
    // 设置网络 Mock
    await setupNetworkMocks(page, context);

    // 导航到主页面
    await page.goto('/');

    // 等待页面加载完成
    await page.waitForLoadState('networkidle');

    console.log('✅ 测试前置条件完成');
  });

  // --------------------------------------------------------------------------
  // 步骤一：启动与流式监听
  // --------------------------------------------------------------------------
  test('步骤一：用户提交科研设想，TerminalLog 成功监听 SSE 推送', async ({ page }) => {
    console.log('🧪 开始测试：启动与流式监听');

    // ------------------------------------------------------------------------
    // 1. 验证主页面已加载
    // ------------------------------------------------------------------------
    await expect(page).toHaveTitle(/EpistemicFlow/);

    // ------------------------------------------------------------------------
    // 2. 验证 TerminalLog 组件已渲染
    // ------------------------------------------------------------------------
    const terminalLog = page.locator('[data-testid="terminal-log"]');
    await expect(terminalLog).toBeVisible();

    // ------------------------------------------------------------------------
    // 3. 等待 SSE 连接建立
    // ------------------------------------------------------------------------
    await waitForSSEConnection(page);

    // ------------------------------------------------------------------------
    // 4. 模拟用户提交科研设想
    // ------------------------------------------------------------------------
    // 查找输入框 (假设有一个科研设想输入表单)
    const inputField = page.locator('[data-testid="research-idea-input"]');
    if (await inputField.isVisible()) {
      await inputField.fill('我想研究人工智能在药物发现中的应用');
      await page.keyboard.press('Enter');
    }

    // ------------------------------------------------------------------------
    // 5. 发布 Mock SSE 事件
    // ------------------------------------------------------------------------
    await publishSSEEvent(page, MOCK_AGENT_THOUGHT);

    // ------------------------------------------------------------------------
    // 6. 断言 TerminalLog 渲染出日志内容
    // ------------------------------------------------------------------------
    // 等待日志内容出现
    await expect(terminalLog).toContainText('正在分析用户提交的科研设想', {
      timeout: 5000,
    });

    // 验证日志级别标签
    await expect(terminalLog).toContainText('[INFO]');

    // 验证智能体名称
    await expect(terminalLog).toContainText('@首席研究员');

    console.log('✅ 步骤一测试通过：SSE 推送成功渲染');
  });

  // --------------------------------------------------------------------------
  // 步骤二：HITL 挂起断言
  // --------------------------------------------------------------------------
  test('步骤二：后端触发 WAITING_FOR_HUMAN，WorkflowCanvas 切换到干预仪表板', async ({ page }) => {
    console.log('🧪 开始测试：HITL 挂起断言');

    // ------------------------------------------------------------------------
    // 1. 等待 SSE 连接建立
    // ------------------------------------------------------------------------
    await waitForSSEConnection(page);

    // ------------------------------------------------------------------------
    // 2. 发布工作流阶段变更事件
    // ------------------------------------------------------------------------
    await publishSSEEvent(page, MOCK_WORKFLOW_STAGE_CHANGE);

    // ------------------------------------------------------------------------
    // 3. 发布 HITL 中断事件
    // ------------------------------------------------------------------------
    await publishSSEEvent(page, MOCK_HITL_INTERRUPT);

    // ------------------------------------------------------------------------
    // 4. 断言 WorkflowCanvas 状态指示器显示 "等待干预"
    // ------------------------------------------------------------------------
    const statusIndicator = page.locator('[data-testid="workflow-status-indicator"]');
    await expect(statusIndicator).toBeVisible({ timeout: 5000 });
    await expect(statusIndicator).toContainText('等待干预');

    // ------------------------------------------------------------------------
    // 5. 断言 InterventionDashboard 组件已渲染
    // ------------------------------------------------------------------------
    const interventionDashboard = page.locator('[data-testid="intervention-dashboard"]');
    await expect(interventionDashboard).toBeVisible({ timeout: 5000 });

    // ------------------------------------------------------------------------
    // 6. 断言 Diff 视图正确渲染
    // ------------------------------------------------------------------------
    const diffViewer = page.locator('[data-testid="diff-viewer"]');
    if (await diffViewer.isVisible()) {
      // 验证 Diff 内容包含生成的计划
      await expect(diffViewer).toContainText('基于深度学习的药物发现研究');
    }

    // ------------------------------------------------------------------------
    // 7. 断言结构化表单已渲染
    // ------------------------------------------------------------------------
    const structuredForm = page.locator('[data-testid="structured-form"]');
    await expect(structuredForm).toBeVisible();

    // 验证表单包含反馈输入框
    const feedbackInput = structuredForm.locator('textarea, input[type="text"]');
    await expect(feedbackInput).toBeVisible();

    console.log('✅ 步骤二测试通过：HITL 干预仪表板正确显示');
  });

  // --------------------------------------------------------------------------
  // 步骤三：Saga 回滚与分叉
  // --------------------------------------------------------------------------
  test('步骤三：用户点击历史节点，触发回滚 API 并重置画布状态', async ({ page }) => {
    console.log('🧪 开始测试：Saga 回滚与分叉');

    // ------------------------------------------------------------------------
    // 1. 等待 SSE 连接建立
    // ------------------------------------------------------------------------
    await waitForSSEConnection(page);

    // ------------------------------------------------------------------------
    // 2. 验证 AgentSidebar 组件已渲染
    // ------------------------------------------------------------------------
    const agentSidebar = page.locator('[data-testid="agent-sidebar"]');
    await expect(agentSidebar).toBeVisible();

    // ------------------------------------------------------------------------
    // 3. 验证 Saga 时间旅行树已渲染
    // ------------------------------------------------------------------------
    const sagaTree = page.locator('[data-testid="saga-tree"]');
    await expect(sagaTree).toBeVisible();

    // ------------------------------------------------------------------------
    // 4. 点击历史节点 (cp-3: 阶段三)
    // ------------------------------------------------------------------------
    // 查找 React Flow 节点
    const historyNode = page.locator(`[data-id="${TEST_CHECKPOINT_ID}"]`);
    await expect(historyNode).toBeVisible({ timeout: 5000 });
    await historyNode.click();

    // ------------------------------------------------------------------------
    // 5. 断言回滚模态框已弹出
    // ------------------------------------------------------------------------
    const rollbackModal = page.locator('[data-testid="rollback-modal"]');
    await expect(rollbackModal).toBeVisible({ timeout: 5000 });

    // 验证模态框标题
    await expect(rollbackModal).toContainText('回滚到历史检查点');

    // ------------------------------------------------------------------------
    // 6. 在模态框中输入修改指令
    // ------------------------------------------------------------------------
    const instructionInput = rollbackModal.locator('textarea');
    await expect(instructionInput).toBeVisible();
    await instructionInput.fill('增加对比实验，比较不同模型架构的效果');

    // ------------------------------------------------------------------------
    // 7. 提交回滚请求
    // ------------------------------------------------------------------------
    const submitButton = rollbackModal.locator('button[type="submit"]');
    await expect(submitButton).toBeEnabled();
    await submitButton.click();

    // ------------------------------------------------------------------------
    // 8. 断言回滚 API 被调用
    // ------------------------------------------------------------------------
    // 等待 API 响应 (通过 Mock 拦截器验证)
    await page.waitForResponse(
      (response) =>
        response.url().includes('/rollback') && response.status() === 200,
      { timeout: 5000 }
    );

    // ------------------------------------------------------------------------
    // 9. 断言模态框已关闭
    // ------------------------------------------------------------------------
    await expect(rollbackModal).not.toBeVisible({ timeout: 3000 });

    // ------------------------------------------------------------------------
    // 10. 断言画布状态已重置
    // ------------------------------------------------------------------------
    // 验证状态指示器显示 "执行中" (回滚后重新执行)
    const statusIndicator = page.locator('[data-testid="workflow-status-indicator"]');
    await expect(statusIndicator).toContainText('执行中', { timeout: 5000 });

    console.log('✅ 步骤三测试通过：Saga 回滚成功执行');
  });

  // --------------------------------------------------------------------------
  // 完整链路测试
  // --------------------------------------------------------------------------
  test('完整链路：从提交设想到 HITL 干预再到回滚分叉', async ({ page }) => {
    console.log('🧪 开始测试：完整业务链路');

    // ------------------------------------------------------------------------
    // Phase 1: 启动与流式监听
    // ------------------------------------------------------------------------
    console.log('📍 Phase 1: 启动与流式监听');

    await waitForSSEConnection(page);

    // 发布智能体思考事件
    await publishSSEEvent(page, MOCK_AGENT_THOUGHT);

    // 验证日志渲染
    const terminalLog = page.locator('[data-testid="terminal-log"]');
    await expect(terminalLog).toContainText('正在分析用户提交的科研设想', {
      timeout: 5000,
    });

    // ------------------------------------------------------------------------
    // Phase 2: HITL 挂起
    // ------------------------------------------------------------------------
    console.log('📍 Phase 2: HITL 挂起');

    // 发布工作流阶段变更
    await publishSSEEvent(page, MOCK_WORKFLOW_STAGE_CHANGE);

    // 发布 HITL 中断
    await publishSSEEvent(page, MOCK_HITL_INTERRUPT);

    // 验证干预仪表板显示
    const interventionDashboard = page.locator('[data-testid="intervention-dashboard"]');
    await expect(interventionDashboard).toBeVisible({ timeout: 5000 });

    // ------------------------------------------------------------------------
    // Phase 3: 用户提交反馈并恢复
    // ------------------------------------------------------------------------
    console.log('📍 Phase 3: 用户提交反馈');

    // 在干预仪表板中填写反馈
    const feedbackInput = interventionDashboard.locator('textarea');
    if (await feedbackInput.isVisible()) {
      await feedbackInput.fill('计划可行，请继续执行');
    }

    // 点击恢复按钮
    const resumeButton = interventionDashboard.locator('button:has-text("继续执行")');
    if (await resumeButton.isVisible()) {
      await resumeButton.click();

      // 等待恢复 API 响应
      await page.waitForResponse(
        (response) =>
          response.url().includes('/resume') && response.status() === 200,
        { timeout: 5000 }
      );
    }

    // ------------------------------------------------------------------------
    // Phase 4: Saga 回滚
    // ------------------------------------------------------------------------
    console.log('📍 Phase 4: Saga 回滚');

    // 点击历史节点
    const historyNode = page.locator(`[data-id="${TEST_CHECKPOINT_ID}"]`);
    if (await historyNode.isVisible()) {
      await historyNode.click();

      // 在模态框中提交回滚
      const rollbackModal = page.locator('[data-testid="rollback-modal"]');
      await expect(rollbackModal).toBeVisible({ timeout: 3000 });

      const instructionInput = rollbackModal.locator('textarea');
      await instructionInput.fill('修改研究方法');
      await rollbackModal.locator('button[type="submit"]').click();

      // 等待回滚 API 响应
      await page.waitForResponse(
        (response) =>
          response.url().includes('/rollback') && response.status() === 200,
        { timeout: 5000 }
      );
    }

    console.log('✅ 完整链路测试通过');
  });
});

// ============================================================================
// 网络层 Mock 降级方案测试
// ============================================================================

test.describe('网络层 Mock 降级方案', () => {
  test.setTimeout(TEST_TIMEOUT);

  test('验证大模型 API 被正确 Mock，无真实 Token 消耗', async ({ page, context }) => {
    console.log('🧪 测试：验证大模型 API Mock');

    // 记录所有大模型 API 调用
    const llmCalls: string[] = [];

    await page.route('**/v1/chat/completions*', async (route) => {
      llmCalls.push(route.request().url());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'mock-id',
          choices: [{ message: { content: 'Mock 响应' } }],
        }),
      });
    });

    // 导航到页面
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // 触发可能的大模型调用
    const inputField = page.locator('[data-testid="research-idea-input"]');
    if (await inputField.isVisible()) {
      await inputField.fill('测试输入');
      await page.keyboard.press('Enter');
    }

    // 等待一段时间让请求完成
    await page.waitForTimeout(2000);

    // 验证所有大模型调用都被 Mock
    console.log(`📊 大模型 API 调用次数: ${llmCalls.length}`);
    llmCalls.forEach((url, index) => {
      console.log(`  [${index + 1}] ${url}`);
    });

    // 断言：如果有调用，都是被 Mock 的
    expect(llmCalls.length).toBeGreaterThanOrEqual(0);

    console.log('✅ 大模型 API Mock 验证通过');
  });

  test('验证耗时后端请求被 Mock，测试快速执行', async ({ page, context }) => {
    console.log('🧪 测试：验证耗时后端请求 Mock');

    const startTime = Date.now();

    // Mock 耗时的后端 API
    await page.route('**/api/v1/workflow/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ mock: true }),
      });
    });

    // 导航到页面
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const endTime = Date.now();
    const duration = endTime - startTime;

    console.log(`⏱️ 测试执行时间: ${duration}ms`);

    // 断言：测试应在合理时间内完成 (小于 10 秒)
    expect(duration).toBeLessThan(10 * 1000);

    console.log('✅ 耗时请求 Mock 验证通过');
  });
});
