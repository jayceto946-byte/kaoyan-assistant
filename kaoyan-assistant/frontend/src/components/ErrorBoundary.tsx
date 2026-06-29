import React, { Component } from 'react';
import type { ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  resetKey?: string | number;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ChatMessage render error:', error, errorInfo);
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: undefined });
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="max-w-[85%] rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-[var(--danger)]">
          <p className="font-medium">{'消息渲染出错'}</p>
          <p className="mt-1 opacity-80">请尝试刷新页面或缩短问题。</p>
        </div>
      );
    }
    return this.props.children;
  }
}
