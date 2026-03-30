import React, { useState, useCallback } from 'react';
import ReactDiffViewer from 'react-diff-viewer-continued';
import { cn } from '@/lib/utils';
import type { DiffViewerProps } from '@/types/workflow';

/**
 * DiffViewer 组件
 * 使用 react-diff-viewer-continued 实现差异对比功能
 */
export const DiffViewer: React.FC<DiffViewerProps> = ({
  original,
  modified,
  onChange,
  showLineNumbers = true,
  darkMode = true,
}) => {
  // 本地编辑状态
  const [localModified, setLocalModified] = useState(modified);

  /**
   * 处理右侧内容变更
   * 当用户在右侧编辑区修改内容时触发
   */
  const handleTextChange = useCallback(
    (value: string) => {
      setLocalModified(value);
      onChange(value);
    },
    [onChange]
  );

  /**
   * 深色模式样式配置
   * 自定义 react-diff-viewer 的样式以适配深色主题
   */
  const darkModeStyles = {
    // 变量差异样式
    variables: {
      light: {
        diffViewerBackground: '#1e1e1e',
        diffViewerColor: '#e0e0e0',
        addedBackground: 'rgba(46, 160, 67, 0.15)',
        addedColor: '#2ea043',
        removedBackground: 'rgba(248, 81, 73, 0.15)',
        removedColor: '#f85149',
        wordAddedBackground: 'rgba(46, 160, 67, 0.3)',
        wordRemovedBackground: 'rgba(248, 81, 73, 0.3)',
        addedGutterBackground: 'rgba(46, 160, 67, 0.1)',
        removedGutterBackground: 'rgba(248, 81, 73, 0.1)',
        gutterBackground: '#252526',
        gutterColor: '#858585',
        codeFoldGutterBackground: '#2d2d30',
        codeFoldBackground: '#1e1e1e',
        codeFoldContentBackground: '#252526',
        diffViewerTitleBackground: '#2d2d30',
        diffViewerTitleColor: '#cccccc',
        diffViewerTitleBorderColor: '#3c3c3c',
      },
    },
  };

  return (
    <div className={cn('w-full h-full', darkMode && 'dark')}>
      <ReactDiffViewer
        // 原始内容（左侧，只读）
        oldValue={original}
        // 修改后内容（右侧，可编辑）
        newValue={localModified}
        // 视图模式：分割视图
        splitView={true}
        // 是否显示行号
        showDiffOnly={false}
        // 使用深色主题
        useDarkTheme={darkMode}
        // 样式配置
        styles={darkMode ? darkModeStyles : undefined}
        // 左侧标题
        leftTitle="原始 AI 提案（只读）"
        // 右侧标题
        rightTitle="人类修改版本（可编辑）"
        // 自定义渲染行号
        hideLineNumbers={!showLineNumbers}
        // 右侧内容变更回调
        onTextChange={handleTextChange}
      />
    </div>
  );
};

export default DiffViewer;
