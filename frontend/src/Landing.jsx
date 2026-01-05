import { useState } from 'react';
import Auth from './pages/Auth';
import logo from './assets/logo.png';
import './Landing.css';

const Landing = ({ onLoginSuccess }) => {
    const [showAuth, setShowAuth] = useState(false);
    const [authType, setAuthType] = useState('login'); // 'login' or 'register'

    const openAuth = (type) => {
        setAuthType(type);
        setShowAuth(true);
    };

    if (showAuth) {
        return <Auth initialMode={authType === 'login'} onBack={() => setShowAuth(false)} onLoginSuccess={onLoginSuccess} />;
    }

    return (
        <div className="landing-container">
            <div className="landing-content">
                <img src={logo} alt="Trading Maven Logo" className="landing-logo" />
                <h1 className="hero-title">TRADING MAVEN</h1>
                <p className="hero-subtitle">Elevate Your Trading to Institutional Standards</p>

                <div className="landing-actions">
                    <button
                        className="btn-primary"
                        onClick={() => openAuth('register')}
                    >
                        Get Started
                    </button>
                    <button
                        className="btn-outline"
                        onClick={() => openAuth('login')}
                    >
                        Sign In
                    </button>
                </div>
            </div>

            {/* Abstract Background Elements */}
            <div className="bg-glow"></div>
        </div>
    );
};

export default Landing;
