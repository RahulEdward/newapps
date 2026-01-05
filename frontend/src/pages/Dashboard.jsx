import { useState, useEffect, useCallback } from 'react';
import DataManager from './DataManager';
import './Dashboard.css';

const Dashboard = ({ onLogout }) => {
    const [activeTab, setActiveTab] = useState('Welcome');
    const [brokers, setBrokers] = useState([]);
    const [showAddBroker, setShowAddBroker] = useState(false);
    const [loading, setLoading] = useState(false);

    const navItems = [
        { name: 'Brokers', icon: 'LINK' },
        { name: 'Data Level', icon: 'BASE' },
        { name: 'Strategies', icon: 'CODE' },
        { name: 'Backtest', icon: 'STATS' },
        { name: 'Live', icon: 'LIVE' }
    ];

    const [editBroker, setEditBroker] = useState(null);
    const [instruments, setInstruments] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [watchlist, setWatchlist] = useState([]);
    const [prices, setPrices] = useState({});

    const fetchLTP = useCallback(async (inst) => {
        try {
            const activeBroker = brokers.find(b => b.status === 'Session Active');
            if (!activeBroker) return;

            const token = localStorage.getItem('token');
            const response = await fetch(`http://127.0.0.1:8000/brokers/angelone/ltp?client_code=${activeBroker.client_code}&exchange=${inst.brexchange}&symbol=${inst.brsymbol}&token=${inst.token}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            if (data.status && data.data) {
                setPrices(prev => ({
                    ...prev,
                    [inst.token]: data.data.ltp
                }));
            }
        } catch (err) {
            console.error('LTP Error:', err);
        }
    }, [brokers]);

    const addToWatchlist = (inst) => {
        if (watchlist.find(w => w.token === inst.token)) {
            alert('Symbol already in watchlist');
            return;
        }
        setWatchlist([...watchlist, inst]);
        fetchLTP(inst);
    };



    // Auto-update watchlist prices
    useEffect(() => {
        if (watchlist.length > 0) {
            const interval = setInterval(() => {
                watchlist.forEach(inst => fetchLTP(inst));
            }, 5000); // Update every 5s
            return () => clearInterval(interval);
        }
    }, [watchlist, fetchLTP]);


    const fetchBrokers = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('http://127.0.0.1:8000/brokers/', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setBrokers(data);
            }
        } catch (error) {
            console.error('Error fetching brokers:', error);
        }
    };

    useEffect(() => {
        fetchBrokers();
    }, []);

    // Real-time search for instruments
    useEffect(() => {
        const delayDebounceFn = setTimeout(() => {
            if (searchQuery.length >= 2) {
                const searchInstruments = async () => {
                    try {
                        const token = localStorage.getItem('token');
                        const response = await fetch(`http://127.0.0.1:8000/brokers/angelone/instruments?q=${searchQuery}`, {
                            headers: { 'Authorization': `Bearer ${token}` }
                        });
                        const data = await response.json();
                        if (Array.isArray(data)) {
                            setInstruments(data);
                        } else {
                            console.error('Invalid search response:', data);
                            setInstruments([]);
                        }
                    } catch (err) {
                        console.error('Search error:', err);
                    }
                };
                searchInstruments();
            } else if (searchQuery.length === 0) {
                setInstruments([]);
            }
        }, 300);

        return () => clearTimeout(delayDebounceFn);
    }, [searchQuery]);

    // New function to handle edit click
    const handleEditClick = (broker) => {
        setEditBroker(broker);
        setShowAddBroker(true);
    };

    const handleAddBroker = async (e) => {
        e.preventDefault();
        setLoading(true);
        const formData = new FormData(e.target);
        const brokerType = formData.get('brokerType');

        const configData = {
            api_key: formData.get('apiKey'),
            client_code: formData.get('clientId'),
            pin: formData.get('pin'),
            totp_secret: formData.get('totpSecret') || ""
        };

        try {
            const token = localStorage.getItem('token');
            let endpoint = '';
            if (brokerType === 'Angel One') endpoint = 'http://127.0.0.1:8000/brokers/angelone/configure';

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(configData)
            });

            if (response.ok) {
                await fetchBrokers();
                setShowAddBroker(false);
                setEditBroker(null); // Reset editBroker state on success
            } else {
                const error = await response.json();
                alert(error.detail || 'Failed to connect broker');
            }
        } catch (error) {
            console.error('Error connecting broker:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteBroker = async (id) => {
        if (!window.confirm('Are you sure you want to delete this broker?')) return;
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`http://127.0.0.1:8000/brokers/angelone/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) fetchBrokers();
        } catch (error) {
            console.error('Error deleting broker:', error);
        }
    };

    const handleBrokerLogout = async (clientCode) => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch(`http://127.0.0.1:8000/brokers/angelone/logout?client_code=${clientCode}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) fetchBrokers();
        } catch (error) {
            console.error('Error logging out broker:', error);
        }
    };

    return (
        <div className="dashboard-container">
            <nav className="top-nav">
                <div className="nav-left" onClick={() => setActiveTab('Welcome')} style={{ cursor: 'pointer' }}>
                    <h1 className="brand-logo">MAVEN</h1>
                </div>

                <div className="nav-center">
                    {navItems.map((item) => (
                        <div
                            key={item.name}
                            className={`nav-link ${activeTab === item.name ? 'active' : ''}`}
                            onClick={() => setActiveTab(item.name)}
                        >
                            <span className="nav-text-icon">{item.icon}</span>
                            <span className="nav-text">{item.name}</span>
                        </div>
                    ))}
                </div>

                <div className="nav-right">
                    <div className="nav-tool-text">THEME</div>
                    <div className="nav-line"></div>
                    <div className="nav-tool-text logout-link" onClick={onLogout}>LOGOUT</div>
                </div>
            </nav>

            <main className="main-viewport">
                {activeTab === 'Welcome' && (
                    <div className="welcome-screen">
                        <h1 className="welcome-title">Welcome to Trading Maven</h1>
                        <p className="welcome-subtitle">First, connect your broker to start trading.</p>
                        <div className="welcome-grid">
                            <div className="welcome-card highlight" onClick={() => setActiveTab('Brokers')}>
                                <h3>Step 1: Connect Broker</h3>
                                <p>Add your Angel One, Dhan or Zerodha credentials.</p>
                            </div>
                            <div className="welcome-card" onClick={() => setActiveTab('Strategies')}>
                                <h3>Step 2: Strategies</h3>
                                <p>Define your entry and exit rules.</p>
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'Brokers' && (
                    <div className="broker-view fade-in">
                        <div className="section-header">
                            <h2 className="section-title">Broker Connections</h2>
                            <div style={{ display: 'flex', gap: '12px' }}>
                                <button className="btn-primary-small" onClick={() => {
                                    setEditBroker(null);
                                    setShowAddBroker(true);
                                }}>+ Add New Broker</button>
                            </div>
                        </div>

                        {showAddBroker && (
                            <div className="modal-overlay">
                                <div className="premium-card broker-modal">
                                    <h3>{editBroker ? 'Update Broker Credentials' : 'Connect New Broker'}</h3>
                                    <form onSubmit={handleAddBroker} className="broker-form">
                                        <div className="form-group">
                                            <label>Select Broker</label>
                                            <select name="brokerType" className="input-field" defaultValue={editBroker ? editBroker.broker : "Angel One"}>
                                                <option value="Angel One">Angel One</option>
                                                <option value="Zerodha" disabled>Zerodha (Coming Soon)</option>
                                                <option value="Dhan" disabled>Dhan (Coming Soon)</option>
                                            </select>
                                        </div>
                                        <div className="form-group">
                                            <label>API Key</label>
                                            <input name="apiKey" className="input-field" type="password" placeholder="Enter API Key" required />
                                        </div>
                                        <div className="form-group">
                                            <label>Client ID</label>
                                            <input
                                                name="clientId"
                                                className="input-field"
                                                placeholder="Enter Client ID"
                                                defaultValue={editBroker ? editBroker.client_code : ""}
                                                readOnly={!!editBroker}
                                                required
                                            />
                                        </div>
                                        <div className="form-group">
                                            <label>4-Digit PIN</label>
                                            <input name="pin" type="password" maxLength="4" className="input-field" placeholder="Broker PIN" required />
                                        </div>
                                        <div className="form-group">
                                            <label>TOTP Secret Key (Optional - leave blank for manual entry)</label>
                                            <input
                                                name="totpSecret"
                                                className="input-field"
                                                placeholder="e.g., JBSWY3DPEHPK3PXP (only for auto-login)"
                                            />
                                            <small style={{ color: '#888', fontSize: '11px', marginTop: '4px', display: 'block' }}>
                                                Leave this blank if you prefer to enter the 6-digit code manually when logging in.
                                            </small>
                                        </div>
                                        <div className="modal-actions">
                                            <button type="button" className="btn-outline" onClick={() => {
                                                setShowAddBroker(false);
                                                setEditBroker(null);
                                            }}>Cancel</button>
                                            <button type="submit" className="btn-primary" disabled={loading}>
                                                {loading ? 'Processing...' : (editBroker ? 'Update' : 'Connect')}
                                            </button>
                                        </div>
                                    </form>
                                </div>
                            </div>
                        )}

                        <div className="broker-list">
                            {brokers.length === 0 ? (
                                <div className="empty-state">
                                    <p>No brokers connected yet. Start by adding one.</p>
                                </div>
                            ) : (
                                brokers.map(broker => (
                                    <div key={broker.id} className="premium-card broker-card">
                                        <div className="broker-header-row">
                                            <div className="broker-info">
                                                <span className="broker-tag">{broker.broker}</span>
                                                <h4>{broker.client_code}</h4>
                                            </div>
                                            <div className="broker-actions">
                                                <button className="action-btn edit-btn" onClick={() => handleEditClick(broker)} title="Edit Configuration">📝</button>
                                                <button className="action-btn delete-btn" onClick={() => handleDeleteBroker(broker.id)} title="Delete Connection">🗑️</button>
                                            </div>
                                        </div>

                                        <div className="broker-status-row">
                                            <div className="status-box">
                                                <span className={`status-indicator ${broker.status === 'Session Active' ? 'live' : ''}`}></span>
                                                <span className="status-text">{broker.status}</span>
                                            </div>

                                            <div className="session-actions">
                                                {broker.status === 'Session Active' ? (
                                                    <button className="btn-outline-small" onClick={() => handleBrokerLogout(broker.client_code)}>Logout</button>
                                                ) : (
                                                    <button
                                                        className="btn-login"
                                                        onClick={() => {
                                                            const totp = prompt("Enter TOTP for " + broker.client_code);
                                                            if (totp) {
                                                                const token = localStorage.getItem('token');
                                                                fetch(`http://127.0.0.1:8000/brokers/angelone/login?client_code=${broker.client_code}&totp=${totp}`, {
                                                                    method: 'POST',
                                                                    headers: { 'Authorization': `Bearer ${token}` }
                                                                }).then(r => r.json()).then(data => {
                                                                    if (data.status === 'success') {
                                                                        alert('Broker session active!');
                                                                        fetchBrokers();
                                                                    } else {
                                                                        alert('Login failed: ' + (data.detail || 'Unknown error'));
                                                                    }
                                                                });
                                                            }
                                                        }}
                                                    >
                                                        Login Session
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                )}

                {activeTab !== 'Welcome' && activeTab !== 'Brokers' && activeTab !== 'Data Level' && activeTab !== 'Strategies' && activeTab !== 'Backtest' && activeTab !== 'Live' && (
                    <div className="content-placeholder fade-in">
                        <h2 className="section-title">{activeTab}</h2>
                        <div className="empty-state">
                            <p>Please connect a broker first to enable {activeTab} features.</p>
                            <div className="mock-empty-box"></div>
                        </div>
                    </div>
                )}


                {activeTab === 'Data Level' && (
                    <div className="data-level-view fade-in">
                        <div className="section-header">
                            <h2 className="section-title">📊 Historical Data Management</h2>
                        </div>
                        <DataManager
                            brokers={brokers}
                            searchQuery={searchQuery}
                            setSearchQuery={setSearchQuery}
                            instruments={instruments}
                        />
                    </div>
                )}
            </main>
        </div>
    );
};

export default Dashboard;
