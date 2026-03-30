/**
 * Playwright 全局设置文件
 *
 * 在所有测试运行前执行，用于：
 * - 初始化测试环境
 * - 清理测试数据
 * - 设置全局 Mock
 */

import { FullConfig, request } from '@playwright/test';

/**
 * 全局 Setup 函数
 * 在所有测试运行前执行一次
 */
export default async function globalSetup(config: FullConfig) {
  console.log('🚀 开始全局设置...');

  // 获取配置中的 baseURL
  const { baseURL } = config.projects[0].use;
  console.log(`📍 基础 URL: ${baseURL}`);

  // 获取后端 API URL
  const backendURL = 'http://localhost:8000';
  console.log(`📍 后端 URL: ${backendURL}`);

  // --------------------------------------------------------------------------
  // 初始化测试上下文
  // --------------------------------------------------------------------------
  const context = await request.newContext({
    baseURL: backendURL,
  });

  try {
    // --------------------------------------------------------------------------
    // 检查后端 API 健康状态
    // --------------------------------------------------------------------------
    console.log('🔍 检查后端 API 健康状态...');
    const healthResponse = await context.get('/api/v1/workflow/statistics/summary?days=1');

    if (healthResponse.ok()) {
      console.log('✅ 后端 API 连接正常');
    } else {
      console.warn(`⚠️ 后端 API 返回非 200 状态: ${healthResponse.status()}`);
    }

    // --------------------------------------------------------------------------
    // 清理测试数据 (可选)
    // --------------------------------------------------------------------------
    // 如果需要清理测试数据，可以在这里调用清理 API
    // await context.post('/api/v1/workflow/cleanup/old', { days: 0 });

  } catch (error) {
    console.error('❌ 全局设置失败:', error);
    throw error;
  } finally {
    await context.dispose();
  }

  console.log('✅ 全局设置完成');
}
