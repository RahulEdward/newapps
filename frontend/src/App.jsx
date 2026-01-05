import { useState } from 'react';
import Landing from './Landing';
import Dashboard from './pages/Dashboard';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // In real app, we would verify token here
  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsAuthenticated(false);
  };

  return (
    <div className="app-wrapper">
      {isAuthenticated ? (
        <Dashboard onLogout={handleLogout} />
      ) : (
        <Landing onLoginSuccess={handleLoginSuccess} />
      )}
    </div>
  );
}

export default App;
