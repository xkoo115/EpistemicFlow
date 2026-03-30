import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';
import type { AutoGenerationData } from '@/types/workflow';

/**
 * AutoGenerationView 组件 Props
 */
interface AutoGenerationViewProps {
  /** 自动生成数据 */
  data: AutoGenerationData;
  /** 可选：自定义类名 */
  className?: string;
}

/**
 * 自动生成视图组件
 * 负责渲染 Markdown 格式的 AI 生成内容
 */
export const AutoGenerationView: React.FC<AutoGenerationViewProps> = ({
  data,
  className,
}) => {
  const { content, title, progress } = data;

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* 标题区域 */}
      {title && (
        <div className="px-6 py-4 border-b border-border">
          <h2 className="text-xl font-semibold text-foreground">
            {title}
          </h2>
          {/* 进度条（如果存在） */}
          {progress !== undefined && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-sm text-muted-foreground mb-1">
                <span>生成进度</span>
                <span>{progress}%</span>
              </div>
              <div className="w-full h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Markdown 内容渲染区域 */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <article className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              // 自定义标题样式 - 深色模式优化
              h1: ({ children }) => (
                <h1 className="text-2xl font-bold mt-8 mb-4 text-foreground border-b border-border pb-2">
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-xl font-semibold mt-6 mb-3 text-foreground">
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-lg font-medium mt-4 mb-2 text-foreground">
                  {children}
                </h3>
              ),
              // 自定义段落样式 - 优化行高和字间距
              p: ({ children }) => (
                <p className="text-foreground leading-relaxed my-3">
                  {children}
                </p>
              ),
              // 自定义代码块样式
              code: ({ className: codeClassName, children, ...props }) => {
                const isInline = !codeClassName;
                if (isInline) {
                  return (
                    <code
                      className="px-1.5 py-0.5 rounded bg-secondary text-foreground font-mono text-sm"
                      {...props}
                    >
                      {children}
                    </code>
                  );
                }
                return (
                  <code
                    className={cn(
                      'block p-4 rounded-lg bg-secondary overflow-x-auto',
                      'font-mono text-sm leading-relaxed',
                      codeClassName
                    )}
                    {...props}
                  >
                    {children}
                  </code>
                );
              },
              // 自定义引用块样式
              blockquote: ({ children }) => (
                <blockquote className="border-l-4 border-primary pl-4 my-4 italic text-muted-foreground">
                  {children}
                </blockquote>
              ),
              // 自定义列表样式
              ul: ({ children }) => (
                <ul className="list-disc list-inside my-3 space-y-1 text-foreground">
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal list-inside my-3 space-y-1 text-foreground">
                  {children}
                </ol>
              ),
              // 自定义表格样式 - 支持深色模式
              table: ({ children }) => (
                <div className="overflow-x-auto my-4">
                  <table className="min-w-full border border-border rounded-lg overflow-hidden">
                    {children}
                  </table>
                </div>
              ),
              thead: ({ children }) => (
                <thead className="bg-secondary">{children}</thead>
              ),
              th: ({ children }) => (
                <th className="px-4 py-2 text-left text-foreground font-semibold border-b border-border">
                  {children}
                </th>
              ),
              td: ({ children }) => (
                <td className="px-4 py-2 text-foreground border-b border-border">
                  {children}
                </td>
              ),
              // 自定义链接样式
              a: ({ href, children }) => (
                <a
                  href={href}
                  className="text-primary hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {children}
                </a>
              ),
            }}
          >
            {content}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  );
};

export default AutoGenerationView;
