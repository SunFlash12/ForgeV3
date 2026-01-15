import { Link } from 'react-router-dom';
import { Home, AlertTriangle } from 'lucide-react';
import { Button } from '../components/common';

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center p-6">
      <div className="text-center">
        <AlertTriangle className="w-16 h-16 mx-auto text-amber-500 mb-4" />
        <h1 className="text-4xl font-bold text-slate-800 dark:text-white mb-2">404</h1>
        <h2 className="text-xl text-slate-600 dark:text-slate-300 mb-6">Page Not Found</h2>
        <p className="text-slate-500 dark:text-slate-400 mb-8 max-w-md">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <Link to="/">
          <Button variant="primary">
            <Home className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
