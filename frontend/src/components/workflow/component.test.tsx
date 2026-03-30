/**
 * 简单组件测试
 */

import React from 'react';
import { render, screen } from '@testing-library/react';

test('renders a simple component', () => {
  render(<div>Hello World</div>);
  expect(screen.getByText('Hello World')).toBeDefined();
});
