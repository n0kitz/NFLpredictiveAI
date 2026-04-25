import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div style={{ padding: '4rem 2rem', textAlign: 'center', color: 'var(--color-text)' }}>
      <h1 style={{ fontSize: '4rem', fontWeight: 800, margin: 0, color: 'var(--color-accent)' }}>404</h1>
      <p style={{ fontSize: '1.25rem', color: 'var(--color-text-muted)', margin: '0.5rem 0 1.5rem' }}>
        Page not found
      </p>
      <Link
        to="/"
        style={{
          padding: '0.5rem 1.25rem',
          background: 'var(--color-accent)',
          color: '#fff',
          borderRadius: '6px',
          textDecoration: 'none',
          fontWeight: 600,
        }}
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
