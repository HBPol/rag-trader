import { render, screen } from '@testing-library/react';
import Home from '../src/app/page';

describe('Home page scaffold', () => {
  it('renders the project headline', () => {
    render(<Home />);
    expect(screen.getByText('RAGTrader')).toBeInTheDocument();
  });
});
