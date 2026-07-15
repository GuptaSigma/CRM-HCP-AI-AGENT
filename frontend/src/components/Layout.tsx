import type { ReactNode } from 'react';

type LayoutProps = {
  children: ReactNode;
};

export function Layout({ children }: LayoutProps) {
  return <div className="app-shell">{children}</div>;
}
