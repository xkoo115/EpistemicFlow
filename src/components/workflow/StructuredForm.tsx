import React, { useState, useCallback, useEffect } from 'react';
import * as Slider from '@radix-ui/react-slider';
import * as Select from '@radix-ui/react-select';
import * as Label from '@radix-ui/react-label';
import { ChevronDown, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StructuredFormProps, Hyperparameters } from '@/types/workflow';

/**
 * StructuredForm 组件
 * 用于 HITL 干预时的超参数调整
 */
export const StructuredForm: React.FC<StructuredFormProps> = ({
  initialValues,
  availableDatasets = [],
  onChange,
  onSubmit,
  isSubmitting = false,
}) => {
  // 表单状态
  const [values, setValues] = useState<Hyperparameters>(initialValues);

  /**
   * 同步表单值到父组件
   * 当任何参数变更时，通知父组件
   */
  useEffect(() => {
    onChange(values);
  }, [values, onChange]);

  /**
   * 更新单个参数值
   */
  const updateValue = useCallback(
    <K extends keyof Hyperparameters>(key: K, value: Hyperparameters[K]) => {
      setValues((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  /**
   * 处理表单提交
   */
  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit();
    },
    [onSubmit]
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-6 p-6 bg-card rounded-lg border border-border">
      <h3 className="text-lg font-semibold text-foreground mb-4">
        超参数调整
      </h3>

      {/* Temperature 滑块 */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label.Root
            htmlFor="temperature"
            className="text-sm font-medium text-foreground"
          >
            Temperature（温度）
          </Label.Root>
          <span className="text-sm text-muted-foreground font-mono">
            {values.temperature.toFixed(2)}
          </span>
        </div>
        <Slider.Root
          id="temperature"
          className="relative flex items-center select-none touch-none w-full h-5"
          value={[values.temperature]}
          onValueChange={([val]) => updateValue('temperature', val)}
          min={0}
          max={2}
          step={0.01}
        >
          <Slider.Track className="bg-secondary relative grow rounded-full h-2">
            <Slider.Range className="absolute bg-primary rounded-full h-full" />
          </Slider.Track>
          <Slider.Thumb
            className="block w-5 h-5 bg-background rounded-full shadow-lg border-2 border-primary hover:bg-accent focus:outline-none focus:ring-2 focus:ring-primary"
            aria-label="Temperature 值"
          />
        </Slider.Root>
        <p className="text-xs text-muted-foreground">
          控制生成随机性。值越高，输出越随机；值越低，输出越确定。
        </p>
      </div>

      {/* Top-P 滑块 */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label.Root
            htmlFor="topP"
            className="text-sm font-medium text-foreground"
          >
            Top-P（核采样）
          </Label.Root>
          <span className="text-sm text-muted-foreground font-mono">
            {values.topP.toFixed(2)}
          </span>
        </div>
        <Slider.Root
          id="topP"
          className="relative flex items-center select-none touch-none w-full h-5"
          value={[values.topP]}
          onValueChange={([val]) => updateValue('topP', val)}
          min={0}
          max={1}
          step={0.01}
        >
          <Slider.Track className="bg-secondary relative grow rounded-full h-2">
            <Slider.Range className="absolute bg-primary rounded-full h-full" />
          </Slider.Track>
          <Slider.Thumb
            className="block w-5 h-5 bg-background rounded-full shadow-lg border-2 border-primary hover:bg-accent focus:outline-none focus:ring-2 focus:ring-primary"
            aria-label="Top-P 值"
          />
        </Slider.Root>
        <p className="text-xs text-muted-foreground">
          核采样阈值。模型将从累积概率达到 Top-P 的最小词集中采样。
        </p>
      </div>

      {/* Max Tokens 滑块 */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label.Root
            htmlFor="maxTokens"
            className="text-sm font-medium text-foreground"
          >
            Max Tokens（最大生成长度）
          </Label.Root>
          <span className="text-sm text-muted-foreground font-mono">
            {values.maxTokens}
          </span>
        </div>
        <Slider.Root
          id="maxTokens"
          className="relative flex items-center select-none touch-none w-full h-5"
          value={[values.maxTokens]}
          onValueChange={([val]) => updateValue('maxTokens', val)}
          min={100}
          max={4096}
          step={100}
        >
          <Slider.Track className="bg-secondary relative grow rounded-full h-2">
            <Slider.Range className="absolute bg-primary rounded-full h-full" />
          </Slider.Track>
          <Slider.Thumb
            className="block w-5 h-5 bg-background rounded-full shadow-lg border-2 border-primary hover:bg-accent focus:outline-none focus:ring-2 focus:ring-primary"
            aria-label="Max Tokens 值"
          />
        </Slider.Root>
        <p className="text-xs text-muted-foreground">
          限制生成的最大 token 数量，防止输出过长。
        </p>
      </div>

      {/* 数据集路径选择 */}
      {availableDatasets.length > 0 && (
        <div className="space-y-3">
          <Label.Root
            htmlFor="datasetPath"
            className="text-sm font-medium text-foreground"
          >
            数据集路径
          </Label.Root>
          <Select.Root
            value={values.datasetPath}
            onValueChange={(val) => updateValue('datasetPath', val)}
          >
            <Select.Trigger
              id="datasetPath"
              className="inline-flex items-center justify-between w-full px-3 py-2 text-sm bg-background border border-border rounded-md hover:bg-accent focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="选择数据集路径"
            >
              <Select.Value placeholder="选择数据集" />
              <Select.Icon>
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              </Select.Icon>
            </Select.Trigger>

            <Select.Portal>
              <Select.Content
                className="overflow-hidden bg-popover border border-border rounded-md shadow-lg"
                position="popper"
                sideOffset={5}
              >
                <Select.Viewport className="p-1">
                  {availableDatasets.map((dataset) => (
                    <Select.Item
                      key={dataset}
                      value={dataset}
                      className="flex items-center justify-between px-3 py-2 text-sm text-foreground rounded cursor-pointer hover:bg-accent focus:outline-none focus:bg-accent"
                    >
                      <Select.ItemText>{dataset}</Select.ItemText>
                      <Select.ItemIndicator>
                        <Check className="w-4 h-4 text-primary" />
                      </Select.ItemIndicator>
                    </Select.Item>
                  ))}
                </Select.Viewport>
              </Select.Content>
            </Select.Portal>
          </Select.Root>
          <p className="text-xs text-muted-foreground">
            选择用于后续处理的数据集文件路径。
          </p>
        </div>
      )}

      {/* 提交按钮 */}
      <div className="pt-4 border-t border-border">
        <button
          type="submit"
          disabled={isSubmitting}
          className={cn(
            'w-full px-4 py-2.5 text-sm font-medium rounded-md transition-colors',
            'bg-primary text-primary-foreground hover:bg-primary/90',
            'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center gap-2">
              <svg
                className="animate-spin h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
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
              提交中...
            </span>
          ) : (
            '确认并恢复工作流'
          )}
        </button>
      </div>
    </form>
  );
};

export default StructuredForm;
