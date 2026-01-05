import { useState } from 'react';
import './Auth.css';

const Auth = ({ initialMode = true, onBack, onLoginSuccess }) => {
    const [isLogin, setIsLogin] = useState(initialMode);
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        fullName: ''
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        const endpoint = isLogin ? 'login' : 'register';

        try {
            const payload = isLogin
                ? { email: formData.email, password: formData.password }
                : { email: formData.email, password: formData.password, full_name: formData.fullName };

            const response = await fetch(`http://127.0.0.1:8000/auth/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            if (response.ok) {
                if (isLogin) {
                    localStorage.setItem('token', data.access_token);
                    if (onLoginSuccess) onLoginSuccess();
                } else {
                    alert('Registration Successful! Please login.');
                    setIsLogin(true);
                }
            } else {
                alert(data.detail || 'Something went wrong');
            }
        } catch (err) {
            console.error('Connection Error:', err);
            alert('Could not connect to backend server. Make sure backend is running on port 8000.');
        }
    };

    return (
        <div className="auth-container">
            <button className="back-btn" onClick={onBack}>← Back</button>
            <div className="premium-card auth-card">
                <div className="auth-header">
                    <h1 className="gradient-text">{isLogin ? 'Welcome Back' : 'Create Account'}</h1>
                    <p>{isLogin ? 'Access your QuantFlow dashboard' : 'Start your institutional trading journey'}</p>
                </div>

                <form onSubmit={handleSubmit} className="auth-form">
                    {!isLogin && (
                        <div className="form-group">
                            <label>Full Name</label>
                            <input
                                type="text"
                                className="input-field"
                                placeholder="John Doe"
                                value={formData.fullName}
                                onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                                required={!isLogin}
                            />
                        </div>
                    )}

                    <div className="form-group">
                        <label>Email Address</label>
                        <input
                            type="email"
                            className="input-field"
                            placeholder="name@company.com"
                            value={formData.email}
                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Password</label>
                        <input
                            type="password"
                            className="input-field"
                            placeholder="••••••••"
                            value={formData.password}
                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                            required
                        />
                    </div>

                    <button type="submit" className="btn-primary w-full">
                        {isLogin ? 'Sign In' : 'Create Account'}
                    </button>
                </form>

                <div className="auth-footer">
                    <p>
                        {isLogin ? "Don't have an account?" : "Already have an account?"}
                        <span onClick={() => setIsLogin(!isLogin)}>
                            {isLogin ? ' Register here' : ' Login here'}
                        </span>
                    </p>
                </div>
            </div>
        </div>
    );
};

export default Auth;
