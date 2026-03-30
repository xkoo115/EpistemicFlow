/**
 * WorkflowCanvas 演示页面
 * 展示不同状态下的 WorkflowCanvas 组件效果
 */

import React, { useState } from 'react';
import { WorkflowCanvas } from '@/components/workflow';
import type { WorkflowStatus, AutoGenerationData, HitlSuspensionData } from '@/types/workflow';

export const WorkflowCanvasDemo: React.FC = () => {
  // 当前状态
  const [status, setStatus] = useState<WorkflowStatus>('RUNNING');

  // 自动生成数据
  const autoGenerationData: AutoGenerationData = {
    content: `# AI 驱动的科研综述生成系统

## 摘要

本文介绍了一种基于大语言模型的自动化科研综述生成系统。该系统能够自动检索、分析和综合相关文献，生成高质量的学术综述。

## 1. 引言

随着科研文献数量的爆炸式增长，研究人员面临着信息过载的挑战。传统的文献综述撰写过程耗时且容易遗漏重要信息。我们提出了一种基于 AI 的自动化解决方案。

## 2. 方法论

### 2.1 文献检索

系统使用语义搜索引擎从多个数据库中检索相关文献：
- PubMed
- arXiv
- Google Scholar
- Semantic Scholar

### 2.2 内容分析

采用大语言模型进行深度语义分析：
- 关键概念提取
- 研究方法分类
- 结果对比分析
- 趋势识别

### 2.3 综述生成

基于分析结果，系统自动生成结构化的综述文档，包括：
- 研究背景
- 主要发现
- 方法对比
- 未来展望

## 3. 实验结果

在 1000 篇文献的测试集上，系统达到了：
- 准确率：92.3%
- 召回率：88.7%
- F1 分数：90.4%

## 4. 结论

本系统显著提高了科研综述的撰写效率，同时保证了内容的质量和准确性。

---

**生成时间**: 2024-03-30
**文献数量**: 156 篇
**模型**: GPT-4-Turbo
`,
    contentType: 'markdown',
    title: '科研综述草稿 - AI 驱动的文献分析',
    progress: status === 'RUNNING' ? 75 : 100,
  };

  // HITL 挂起数据
  const hitlData: HitlSuspensionData = {
    nodeId: 'node-review-001',
    originalProposal: `# 科研综述草稿（待审核）

## 摘要
本综述总结了近年来深度学习在医学影像分析中的应用进展...

## 主要发现
1. 卷积神经网络在肿瘤检测中达到 95% 准确率
2. Transformer 架构在多模态融合中表现优异
3. 联邦学习解决了数据隐私问题

## 建议修改
- 增加更多对比实验
- 补充最新文献（2024年）
- 优化图表展示
`,
    currentHyperparameters: {
      temperature: 0.7,
      topP: 0.9,
      maxTokens: 2048,
      datasetPath: '/data/medical_imaging_v2.csv',
    },
    availableDatasets: [
      '/data/medical_imaging_v1.csv',
      '/data/medical_imaging_v2.csv',
      '/data/radiology_2024.csv',
    ],
    reason: '系统检测到综述内容可能需要人工审核和补充，请确认以下内容是否符合预期。',
  };

  // 处理恢复工作流
  const handleResume = async (payload: any) => {
    console.log('用户提交的干预数据:', payload);
    alert(`干预已提交！\n\n修改内容长度: ${payload.modifiedContent.length} 字符\nTemperature: ${payload.hyperparameters.temperature}\n数据集: ${payload.hyperparameters.datasetPath}`);
    // 模拟恢复后切换到 RUNNING 状态
    setTimeout(() => setStatus('RUNNING'), 1000);
  };

  return (
    <div className="min-h-screen bg-background p-6">
      {/* 控制面板 */}
      <div className="mb-6 p-4 bg-card rounded-lg border border-border">
        <h2 className="text-lg font-semibold mb-4">WorkflowCanvas 状态切换演示</h2>
        <div className="flex gap-3 flex-wrap">
          <button
            onClick={() => setStatus('RUNNING')}
            className={`px-4 py-2 rounded-md transition-colors ${
              status === 'RUNNING'
                ? 'bg-blue-500 text-white'
                : 'bg-secondary text-foreground hover:bg-secondary/80'
            }`}
          >
            RUNNING（执行中）
          </button>
          <button
            onClick={() => setStatus('WAITING_FOR_HUMAN')}
            className={`px-4 py-2 rounded-md transition-colors ${
              status === 'WAITING_FOR_HUMAN'
                ? 'bg-amber-500 text-white'
                : 'bg-secondary text-foreground hover:bg-secondary/80'
            }`}
          >
            WAITING_FOR_HUMAN（等待干预）
          </button>
          <button
            onClick={() => setStatus('COMPLETED')}
            className={`px-4 py-2 rounded-md transition-colors ${
              status === 'COMPLETED'
                ? 'bg-green-500 text-white'
                : 'bg-secondary text-foreground hover:bg-secondary/80'
            }`}
          >
            COMPLETED（已完成）
          </button>
          <button
            onClick={() => setStatus('ERROR')}
            className={`px-4 py-2 rounded-md transition-colors ${
              status === 'ERROR'
                ? 'bg-red-500 text-white'
                : 'bg-secondary text-foreground hover:bg-secondary/80'
            }`}
          >
            ERROR（出错）
          </button>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">
          当前状态: <span className="font-mono font-semibold">{status}</span>
        </p>
      </div>

      {/* WorkflowCanvas 展示区域 */}
      <div className="h-[calc(100vh-200px)] bg-card rounded-lg border border-border overflow-hidden">
        <WorkflowCanvas
          status={status}
          sessionId="demo-session-001"
          autoGenerationData={autoGenerationData}
          hitlData={hitlData}
          onResume={handleResume}
        />
      </div>
    </div>
  );
};

export default WorkflowCanvasDemo;
