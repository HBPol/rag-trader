import { render, screen } from '@testing-library/react';
import { AuthProvider } from '../src/app/layout';
import Home from '../src/app/page';

describe('Home page scaffold', () => {
  it('renders the project headline', () => {
    render(
      <AuthProvider value={{ isAuthenticated: true }}>
        <Home />
      </AuthProvider>,
    );
    expect(screen.getByText('RAGTrader')).toBeInTheDocument();
  });

  it('hides the app shell for unauthenticated visitors', () => {
    render(
      <AuthProvider value={{ isAuthenticated: false }}>
        <Home />
      </AuthProvider>,
    );

    expect(
      screen.getByText('Sign in to unlock market insights, watchlists, and custom retrieval workflows.'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText('You are signed in via the mock auth provider—swap the environment flag to review the locked experience.'),
    ).not.toBeInTheDocument();
  });

  it('shows the app shell when authenticated', () => {
    render(
      <AuthProvider value={{ isAuthenticated: true }}>
        <Home />
      </AuthProvider>,
    );

    expect(
      screen.getByText('You are signed in via the mock auth provider—swap the environment flag to review the locked experience.'),
    ).toBeInTheDocument();
    expect(
      screen.queryByText('Sign in to unlock market insights, watchlists, and custom retrieval workflows.'),
    ).not.toBeInTheDocument();
  });
});
