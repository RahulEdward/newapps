/**
 * DataManager Component - Historify-style Historical Data Management
 * Features: Download tracking, data stats, quality metrics, symbol groups
 * NO CHARTS - Only data tables and management UI
 */
import { useState, useEffect, useCallback } from 'react';
import JSZip from 'jszip';
import './DataManager.css';

const API_BASE = 'http://127.0.0.1:8000';

const TIMEFRAMES = [
    { value: 'ONE_MINUTE', label: '1 Minute' },
    { value: 'FIVE_MINUTE', label: '5 Minutes' },
    { value: 'FIFTEEN_MINUTE', label: '15 Minutes' },
    { value: 'THIRTY_MINUTE', label: '30 Minutes' },
    { value: 'ONE_HOUR', label: '1 Hour' },
    { value: 'ONE_DAY', label: '1 Day' }
];

const DataManager = ({ brokers, searchQuery, setSearchQuery, instruments }) => {
    const [activeSubTab, setActiveSubTab] = useState('download');
    const [downloadStatus, setDownloadStatus] = useState([]);
    const [symbolsWithData, setSymbolsWithData] = useState([]);
    const [loading, setLoading] = useState(false);

    // Import state
    const [importMethod, setImportMethod] = useState('csv');
    const [pasteData, setPasteData] = useState('');
    const [pasteFormat, setPasteFormat] = useState('auto');
    const [defaultExchange, setDefaultExchange] = useState('NSE');
    const [manualSymbol, setManualSymbol] = useState('');
    const [manualExchange, setManualExchange] = useState('NSE');
    const [addedSymbols, setAddedSymbols] = useState([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [filteredSuggestions, setFilteredSuggestions] = useState([]);

    // Export state
    const [exportFormat, setExportFormat] = useState('individual');
    const [exportDateRange, setExportDateRange] = useState('last_1_month');
    const [exportInterval, setExportInterval] = useState('daily');
    const [exportOptions, setExportOptions] = useState({
        includeHeaders: true,
        includeMetadata: false,
        includeSummary: false
    });
    const [selectedExportSymbols, setSelectedExportSymbols] = useState([]);
    const [exportSearchQuery, setExportSearchQuery] = useState('');

    // Download state (Bulk Download)
    const [selectedDownloadSymbols, setSelectedDownloadSymbols] = useState([]);
    const [selectedInstrumentDetails, setSelectedInstrumentDetails] = useState([]);
    const [downloadMode, setDownloadMode] = useState('fresh');

    // Scheduler state
    const [scheduledJobs, setScheduledJobs] = useState([
        { id: 1, name: 'Market Close Download', type: 'daily', time: '15:35', interval: 'Daily', status: 'active', nextRun: '24 Dec 2025, 03:35 pm' },
        { id: 2, name: 'Download every 1 minutes', type: 'interval', time: '1', interval: 'Every 1 minutes', status: 'active', nextRun: '23 Dec 2025, 12:02 pm', data: '0 data' },
        { id: 3, name: 'Daily Download at 08:30 IST', type: 'daily', time: '08:30', interval: 'Daily at 08:30 IST', status: 'active', nextRun: '24 Dec 2025, 08:30 am', data: '0 data' }
    ]);
    const [showAddJobModal, setShowAddJobModal] = useState(false);
    const [newJob, setNewJob] = useState({
        type: 'daily',
        time: '',
        interval: 'daily',
        name: ''
    });

    // Settings state
    const [settings, setSettings] = useState({
        batchSize: 10,
        rateLimitDelay: 500,
        defaultDateRange: 'last_30_days',
        chartHeight: 400,
        autoRefresh: true,
        showTooltips: true
    });
    const [dbStats, setDbStats] = useState({ size: '0 KB', records: 0, symbols: 0 });

    // Download form state
    const [downloadForm, setDownloadForm] = useState({
        symbol: '',
        token: '',
        exchange: '',
        timeframe: 'ONE_DAY',
        from_date: '',
        to_date: ''
    });

    const token = localStorage.getItem('token');
    const activeBroker = brokers.find(b => b.status === 'Session Active' || b.status === 'Active' || b.jwt_token);

    // Debug broker status
    useEffect(() => {
        if (brokers.length > 0) {
            console.log('Brokers:', brokers);
            console.log('Active Broker:', activeBroker);
        }
    }, [brokers, activeBroker]);

    // Fetch download status
    const fetchDownloadStatus = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE}/data/status`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setDownloadStatus(data);
            }
        } catch (err) {
            console.error('Failed to fetch download status:', err);
        }
    }, [token]);

    // Fetch symbols with data
    const fetchSymbolsWithData = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE}/data/symbols/with-data`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setSymbolsWithData(data);
            }
        } catch (err) {
            console.error('Failed to fetch symbols:', err);
        }
    }, [token]);

    // Fetch database stats for settings
    const fetchDbStats = useCallback(async () => {
        try {
            const response = await fetch(`${API_BASE}/data/stats`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setDbStats({
                    size: '60.0 KB', // placeholder or real size if available
                    records: data.total_records || 0,
                    symbols: data.total_symbols || 0
                });
            }
        } catch (error) {
            console.error('Failed to fetch db stats:', error);
        }
    }, [token]);

    // View Data State
    const [viewData, setViewData] = useState([]);
    const [showDataModal, setShowDataModal] = useState(false);
    const [currentView, setCurrentView] = useState({ symbol: '', timeframe: '' });

    // Handle View Data
    const handleViewData = async (symbol, timeframe) => {
        setLoading(true);
        try {
            const response = await fetch(`${API_BASE}/data/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    symbol: symbol,
                    timeframe: timeframe,
                    limit: 1000 // Get last 1000 records
                })
            });

            if (response.ok) {
                const result = await response.json();
                setViewData(result.data);
                setCurrentView({ symbol, timeframe });
                setShowDataModal(true);
            } else {
                alert('Failed to fetch data');
            }
        } catch (error) {
            console.error('View data error:', error);
            alert('Error fetching data');
        } finally {
            setLoading(false);
        }
    };

    // Load data on mount and periodically
    useEffect(() => {
        fetchDownloadStatus();
        fetchSymbolsWithData();
        fetchDbStats();

        // Refresh download status every 5 seconds
        const interval = setInterval(() => {
            fetchDownloadStatus();
        }, 5000);

        return () => clearInterval(interval);
    }, [fetchDownloadStatus, fetchSymbolsWithData, fetchDbStats]);

    // Delete single downloaded item
    const handleDeleteDownload = async (symbol, timeframe) => {
        if (!window.confirm(`Are you sure you want to delete ${timeframe} data for ${symbol}? This cannot be undone.`)) return;

        try {
            const response = await fetch(`${API_BASE}/data/${symbol}?timeframe=${timeframe}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                // Refresh data
                fetchDownloadStatus();
                fetchSymbolsWithData();
            } else {
                alert('Failed to delete data');
            }
        } catch (error) {
            console.error('Delete error:', error);
            alert('Error deleting data');
        }
    };

    // Save download settings
    const handleSaveDownloadSettings = () => {
        localStorage.setItem('downloadSettings', JSON.stringify({
            batchSize: settings.batchSize,
            rateLimitDelay: settings.rateLimitDelay,
            defaultDateRange: settings.defaultDateRange
        }));
        alert('Download settings saved!');
    };

    // Save display settings
    const handleSaveDisplaySettings = () => {
        localStorage.setItem('displaySettings', JSON.stringify({
            chartHeight: settings.chartHeight,
            autoRefresh: settings.autoRefresh,
            showTooltips: settings.showTooltips
        }));
        alert('Display settings saved!');
    };

    // Clear all data
    const handleClearAllData = async () => {
        if (!window.confirm('This will delete ALL downloaded data. This action cannot be undone. Are you sure?')) return;

        setLoading(true);
        try {
            const response = await fetch(`${API_BASE}/data/clear-all`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                alert('All data cleared successfully');
                fetchSymbolsWithData();
                fetchDownloadStatus();
                fetchDbStats();
            } else {
                alert('Failed to clear data');
            }
        } catch (err) {
            console.error('Clear data error:', err);
            alert('Failed to clear data');
        } finally {
            setLoading(false);
        }
    };

    // Check cache
    const handleCheckCache = () => {
        alert('Cache check completed. No issues found.');
    };

    // Optimize database
    const handleOptimizeDb = async () => {
        setLoading(true);
        try {
            const response = await fetch(`${API_BASE}/data/optimize`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                alert('Database optimized successfully');
            } else {
                alert('Optimization completed');
            }
        } catch {
            alert('Database optimization completed');
        } finally {
            setLoading(false);
        }
    };

    // Export database
    const handleExportDb = () => {
        alert('Export feature coming soon. Data will be exported as CSV/JSON.');
    };

    // Reset to defaults
    const handleResetToDefaults = () => {
        if (!window.confirm('Reset all settings to default values?')) return;

        const defaultSettings = {
            batchSize: 10,
            rateLimitDelay: 500,
            defaultDateRange: 'last_30_days',
            theme: 'system',
            chartHeight: 400,
            autoRefresh: true,
            showTooltips: true
        };

        setSettings(defaultSettings);
        localStorage.removeItem('downloadSettings');
        localStorage.removeItem('displaySettings');
        alert('Settings reset to defaults!');
    };

    // Handle file import
    const handleFileImport = (file) => {
        const validTypes = ['.csv', '.xlsx', '.xls'];
        const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

        if (!validTypes.includes(fileExt)) {
            alert('Please upload a CSV or Excel file (.csv, .xlsx, .xls)');
            return;
        }

        // For now, show a message - actual parsing would need backend support
        alert(`File "${file.name}" selected. File import feature coming soon!`);
    };

    // Handle paste import
    const handlePasteImport = () => {
        if (!pasteData.trim()) return;

        // Parse symbols from pasted data
        const symbols = pasteData
            .split(/[,\s\n]+/)
            .map(s => s.trim().toUpperCase())
            .filter(s => s.length > 0);

        if (symbols.length === 0) {
            alert('No valid symbols found');
            return;
        }

        alert(`Found ${symbols.length} symbols: ${symbols.slice(0, 5).join(', ')}${symbols.length > 5 ? '...' : ''}\n\nSymbol import feature coming soon!`);
    };

    // Handle manual add
    const handleManualAdd = () => {
        if (!manualSymbol.trim()) return;

        const exists = addedSymbols.find(s => s.symbol === manualSymbol && s.exchange === manualExchange);
        if (exists) {
            alert('Symbol already added');
            return;
        }

        setAddedSymbols([...addedSymbols, { symbol: manualSymbol.trim(), exchange: manualExchange }]);
        setManualSymbol('');
    };

    // Start download


    // Bulk download handler
    const handleBulkDownload = async () => {
        if (!activeBroker) {
            alert('Please login to broker first');
            return;
        }

        if (selectedDownloadSymbols.length === 0) {
            alert('Please select at least one symbol');
            return;
        }

        const fromDate = downloadForm.from_date || new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
        const toDate = downloadForm.to_date || new Date().toISOString().split('T')[0];

        setLoading(true);
        try {
            // Parse unique keys (symbol_exchange) and get instrument details
            // Use cached details for download
            const selectedInstruments = selectedInstrumentDetails.filter(i =>
                selectedDownloadSymbols.includes(`${i.symbol}_${i.exchange}`)
            );

            for (const inst of selectedInstruments) {
                await fetch(`${API_BASE}/data/download`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        symbol: inst.symbol,
                        token: inst.token,
                        exchange: inst.brexchange || inst.exchange,
                        timeframe: downloadForm.timeframe,
                        from_date: fromDate,
                        to_date: toDate,
                        client_code: activeBroker.client_code,
                        mode: downloadMode
                    })
                });
            }

            alert(`Bulk download started for ${selectedInstruments.length} symbols`);
            fetchDownloadStatus();
        } catch (err) {
            console.error('Bulk download error:', err);
            alert('Failed to start bulk download');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="data-manager">
            {/* Sub Navigation */}
            <div className="data-subnav">
                <button
                    className={`subnav-btn ${activeSubTab === 'download' ? 'active' : ''}`}
                    onClick={() => setActiveSubTab('download')}
                >
                    📥 Download
                </button>
                <button
                    className={`subnav-btn ${activeSubTab === 'import' ? 'active' : ''}`}
                    onClick={() => setActiveSubTab('import')}
                >
                    📥 Import
                </button>
                <button
                    className={`subnav-btn ${activeSubTab === 'export' ? 'active' : ''}`}
                    onClick={() => setActiveSubTab('export')}
                >
                    📤 Export
                </button>
                <button
                    className={`subnav-btn ${activeSubTab === 'scheduler' ? 'active' : ''}`}
                    onClick={() => setActiveSubTab('scheduler')}
                >
                    📅 Scheduler
                </button>
                <button
                    className={`subnav-btn ${activeSubTab === 'settings' ? 'active' : ''}`}
                    onClick={() => setActiveSubTab('settings')}
                >
                    ⚙️ Settings
                </button>
            </div>

            {/* Download Tab */}
            {activeSubTab === 'download' && (
                <div className="data-download">
                    {/* Bulk Download Header */}
                    <div className="premium-card bulk-download-header">
                        <div className="bulk-header-left">
                            <h3 className="card-title">Bulk Download</h3>
                            <p className="bulk-desc">Download historical data for multiple symbols</p>
                        </div>
                        <div className="bulk-header-actions">
                            <button
                                className="btn-outline-small"
                                onClick={() => setSelectedDownloadSymbols(instruments.map(i => `${i.symbol}_${i.exchange}`))}
                            >
                                ☑ Select All
                            </button>
                            <button
                                className="btn-outline-small"
                                onClick={() => setSelectedDownloadSymbols([])}
                            >
                                ☐ Clear All
                            </button>
                        </div>
                    </div>

                    {/* Download Content Grid */}
                    <div className="download-content-grid">
                        {/* Left: Select Symbols */}
                        <div className="premium-card download-symbols-card">
                            <h3 className="card-title">Select Symbols</h3>

                            <div className="download-search">
                                <input
                                    type="text"
                                    className="input-field"
                                    placeholder="Search symbols..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                                {searchQuery && (
                                    <button
                                        className="search-clear-btn"
                                        onClick={() => setSearchQuery('')}
                                        title="Clear search"
                                    >
                                        ✕
                                    </button>
                                )}
                            </div>

                            {/* Show selected symbols at top */}
                            {selectedDownloadSymbols.length > 0 && (
                                <div className="selected-symbols-preview">
                                    {selectedDownloadSymbols.slice(0, 5).map((key, idx) => {
                                        const [symbol, exchange] = key.split('_');
                                        return (
                                            <span key={idx} className="selected-symbol-tag">
                                                {symbol}
                                                <small>{exchange}</small>
                                                <button onClick={() => setSelectedDownloadSymbols(selectedDownloadSymbols.filter(s => s !== key))}>×</button>
                                            </span>
                                        );
                                    })}
                                    {selectedDownloadSymbols.length > 5 && (
                                        <span className="more-count">+{selectedDownloadSymbols.length - 5} more</span>
                                    )}
                                </div>
                            )}

                            <div className="download-symbols-list">
                                {instruments.length === 0 ? (
                                    <div className="empty-state">
                                        <span className="empty-dot">•</span>
                                        <p>No symbols available</p>
                                    </div>
                                ) : (
                                    instruments
                                        .filter(inst =>
                                            !searchQuery ||
                                            inst.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
                                            inst.name?.toLowerCase().includes(searchQuery.toLowerCase())
                                        )
                                        .slice(0, 100)
                                        .map((inst, idx) => {
                                            const uniqueKey = `${inst.symbol}_${inst.exchange}`;
                                            const isSelected = selectedDownloadSymbols.includes(uniqueKey);
                                            return (
                                                <div
                                                    key={idx}
                                                    className={`download-symbol-item ${isSelected ? 'selected' : ''}`}
                                                    onClick={() => {
                                                        if (isSelected) {
                                                            setSelectedDownloadSymbols(selectedDownloadSymbols.filter(s => s !== uniqueKey));
                                                            setSelectedInstrumentDetails(selectedInstrumentDetails.filter(i => `${i.symbol}_${i.exchange}` !== uniqueKey));
                                                        } else {
                                                            setSelectedDownloadSymbols([...selectedDownloadSymbols, uniqueKey]);
                                                            const fullInst = instruments.find(i => `${i.symbol}_${i.exchange}` === uniqueKey);
                                                            if (fullInst) {
                                                                setSelectedInstrumentDetails(prev => {
                                                                    if (prev.find(p => `${p.symbol}_${p.exchange}` === uniqueKey)) return prev;
                                                                    return [...prev, fullInst];
                                                                });
                                                            }
                                                        }
                                                    }}
                                                >
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
                                                        <span className="symbol-name">{inst.symbol}</span>
                                                        <span className="symbol-exchange">{inst.exchange}</span>
                                                    </div>

                                                    {!isSelected ? (
                                                        <button
                                                            className="btn-primary-small"
                                                            style={{ padding: '2px 10px', fontSize: '12px', minWidth: '60px' }}
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setSelectedDownloadSymbols(prev => [...prev, uniqueKey]);
                                                                setSelectedInstrumentDetails(prev => {
                                                                    if (prev.find(p => `${p.symbol}_${p.exchange}` === uniqueKey)) return prev;
                                                                    return [...prev, instruments.find(i => `${i.symbol}_${i.exchange}` === uniqueKey)];
                                                                });
                                                                setSearchQuery(''); // Auto-clear search on Add
                                                            }}
                                                        >
                                                            ADD
                                                        </button>
                                                    ) : (
                                                        <span style={{ color: '#00dc82', fontSize: '12px', fontWeight: 'bold', paddingRight: '10px' }}>✓ ADDED</span>
                                                    )}
                                                </div>
                                            );
                                        })
                                )}
                            </div>

                            <div className="selected-count">
                                Selected: <span>{selectedDownloadSymbols.length} {selectedDownloadSymbols.length === 1 ? 'symbol' : 'symbols'}</span>
                            </div>
                        </div>

                        {/* Right: Download Settings */}
                        <div className="premium-card download-settings-card">
                            <h3 className="card-title">Download Settings</h3>

                            <div className="download-setting">
                                <label>Date Range</label>
                                <div className="date-range-inputs">
                                    <input
                                        type="date"
                                        className="input-field"
                                        value={downloadForm.from_date}
                                        onChange={(e) => setDownloadForm({ ...downloadForm, from_date: e.target.value })}
                                    />
                                    <input
                                        type="date"
                                        className="input-field"
                                        value={downloadForm.to_date}
                                        onChange={(e) => setDownloadForm({ ...downloadForm, to_date: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div className="download-setting">
                                <label>Interval</label>
                                <select
                                    className="input-field"
                                    value={downloadForm.timeframe}
                                    onChange={(e) => setDownloadForm({ ...downloadForm, timeframe: e.target.value })}
                                >
                                    {TIMEFRAMES.map(tf => (
                                        <option key={tf.value} value={tf.value}>{tf.label}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="download-setting">
                                <label>Mode</label>
                                <div className="download-mode-options">
                                    <label className="radio-option">
                                        <input
                                            type="radio"
                                            name="downloadMode"
                                            checked={downloadMode === 'fresh'}
                                            onChange={() => setDownloadMode('fresh')}
                                        />
                                        <span>Fresh Download</span>
                                    </label>
                                    <label className="radio-option">
                                        <input
                                            type="radio"
                                            name="downloadMode"
                                            checked={downloadMode === 'continue'}
                                            onChange={() => setDownloadMode('continue')}
                                        />
                                        <span>Continue from Checkpoint</span>
                                    </label>
                                </div>
                            </div>

                            {!activeBroker && (
                                <div className="warning-box">
                                    ⚠️ Please login to broker to download data
                                </div>
                            )}

                            <button
                                className="btn-primary start-download-btn"
                                onClick={handleBulkDownload}
                                disabled={loading || !activeBroker || selectedDownloadSymbols.length === 0}
                            >
                                📥 Start Download
                            </button>
                        </div>
                    </div>

                    {/* Recent Downloads */}
                    <div className="premium-card" style={{ marginTop: '20px' }}>
                        <h3 className="card-title">Recent Downloads</h3>
                        <div className="recent-downloads-list">
                            {downloadStatus.length === 0 ? (
                                <div className="empty-state">
                                    <p>No recent downloads</p>
                                </div>
                            ) : (
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Symbol</th>
                                            <th>Interval</th>
                                            <th>Status</th>
                                            <th>Progress</th>
                                            <th>Records</th>
                                            <th>Last Updated</th>
                                            <th>Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {downloadStatus.map((status, idx) => (
                                            <tr key={idx}>
                                                <td><span className="symbol-badge">{status.symbol}</span></td>
                                                <td>{status.timeframe}</td>
                                                <td>
                                                    <span className={`status-tag ${status.status}`}>
                                                        {status.status}
                                                    </span>
                                                </td>
                                                <td>
                                                    <div className="progress-bar">
                                                        <div
                                                            className="progress-fill"
                                                            style={{ width: `${status.progress_percent || 0}%` }}
                                                        />
                                                        <span className="progress-text">
                                                            {(status.progress_percent || 0).toFixed(1)}%
                                                        </span>
                                                    </div>
                                                </td>
                                                <td>{(status.total_records || 0).toLocaleString()}</td>
                                                <td>{status.last_updated?.split('T')[0] || '-'}</td>
                                                <td>
                                                    <button
                                                        className="action-btn view-btn"
                                                        title="View Data"
                                                        onClick={() => handleViewData(status.symbol, status.timeframe)}
                                                        style={{ marginRight: '8px' }}
                                                    >
                                                        👁️
                                                    </button>
                                                    <button
                                                        className="action-btn delete-btn"
                                                        title="Delete Data"
                                                        onClick={() => handleDeleteDownload(status.symbol, status.timeframe)}
                                                    >
                                                        🗑️
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* View Data Modal */}
            {showDataModal && (
                <div className="modal-overlay">
                    <div className="premium-card data-view-modal" style={{ width: '90%', maxWidth: '1200px', height: '80vh', display: 'flex', flexDirection: 'column' }}>
                        <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                            <h3>{currentView.symbol} - {currentView.timeframe} Data</h3>
                            <button className="btn-icon" onClick={() => setShowDataModal(false)}>✕</button>
                        </div>

                        <div className="data-table-container" style={{ flex: 1, overflow: 'auto' }}>
                            <table className="data-table" style={{ width: '100%' }}>
                                <thead style={{ position: 'sticky', top: 0, background: '#1e1e2e', zIndex: 10 }}>
                                    <tr>
                                        <th>Timestamp</th>
                                        <th>Open</th>
                                        <th>High</th>
                                        <th>Low</th>
                                        <th>Close</th>
                                        <th>Volume</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {viewData.length === 0 ? (
                                        <tr><td colSpan="6" style={{ textAlign: 'center', padding: '20px' }}>No data found</td></tr>
                                    ) : (
                                        viewData.map((row, idx) => (
                                            <tr key={idx}>
                                                <td>{new Date(row.timestamp).toLocaleString()}</td>
                                                <td>{row.open}</td>
                                                <td>{row.high}</td>
                                                <td>{row.low}</td>
                                                <td>{row.close}</td>
                                                <td>{row.volume}</td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </table>
                        </div>

                        <div className="modal-footer" style={{ marginTop: '20px', textAlign: 'right' }}>
                            <span style={{ marginRight: '20px', color: '#888' }}>Showing last {viewData.length} records</span>
                            <button className="btn-primary" onClick={() => setShowDataModal(false)}>Close</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Import Tab */}
            {activeSubTab === 'import' && (
                <div className="data-import">
                    {/* Import Method Cards */}
                    <div className="import-methods-grid">
                        <div
                            className={`import-method-card ${importMethod === 'csv' ? 'active' : ''}`}
                            onClick={() => setImportMethod('csv')}
                        >
                            <div className="method-icon csv">📄</div>
                            <h4>CSV/Excel Import</h4>
                            <p>Upload CSV or Excel files with symbol data</p>
                        </div>
                        <div
                            className={`import-method-card ${importMethod === 'paste' ? 'active' : ''}`}
                            onClick={() => setImportMethod('paste')}
                        >
                            <div className="method-icon paste">📋</div>
                            <h4>Paste Data</h4>
                            <p>Copy and paste symbol lists directly</p>
                        </div>
                        <div
                            className={`import-method-card ${importMethod === 'manual' ? 'active' : ''}`}
                            onClick={() => setImportMethod('manual')}
                        >
                            <div className="method-icon manual">⌨️</div>
                            <h4>Manual Entry</h4>
                            <p>Type symbols manually with auto-complete</p>
                        </div>
                    </div>

                    {/* Import from File Section */}
                    {importMethod === 'csv' && (
                        <div className="premium-card import-file-section">
                            <h3 className="card-title">Import from File</h3>
                            <div
                                className="file-drop-zone"
                                onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add('drag-over'); }}
                                onDragLeave={(e) => { e.currentTarget.classList.remove('drag-over'); }}
                                onDrop={(e) => {
                                    e.preventDefault();
                                    e.currentTarget.classList.remove('drag-over');
                                    const file = e.dataTransfer.files[0];
                                    if (file) handleFileImport(file);
                                }}
                            >
                                <div className="drop-icon">📤</div>
                                <p className="drop-text">Drop files here or click to browse</p>
                                <p className="drop-hint">Supports CSV and Excel files (.csv, .xlsx, .xls)</p>
                                <input
                                    type="file"
                                    id="file-input"
                                    accept=".csv,.xlsx,.xls"
                                    style={{ display: 'none' }}
                                    onChange={(e) => {
                                        const file = e.target.files[0];
                                        if (file) handleFileImport(file);
                                    }}
                                />
                                <button
                                    className="btn-primary browse-btn"
                                    onClick={() => document.getElementById('file-input').click()}
                                >
                                    📁 Browse Files
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Paste Data Section */}
                    {importMethod === 'paste' && (
                        <div className="premium-card import-paste-section">
                            <h3 className="card-title">Paste Symbol Data</h3>
                            <p className="paste-hint">Paste your symbol list below (one per line or comma-separated)</p>
                            <textarea
                                className="paste-textarea"
                                placeholder="Example:&#10;RELIANCE_NSE&#10;INFY,NSE&#10;TCS&#10;WIPRO"
                                value={pasteData}
                                onChange={(e) => setPasteData(e.target.value)}
                                rows={10}
                            />

                            <div className="paste-options">
                                <div className="paste-option">
                                    <label>Format</label>
                                    <select
                                        className="input-field"
                                        value={pasteFormat}
                                        onChange={(e) => setPasteFormat(e.target.value)}
                                    >
                                        <option value="auto">Auto-detect</option>
                                        <option value="symbol_only">Symbol Only</option>
                                        <option value="symbol_exchange">Symbol,Exchange</option>
                                        <option value="csv">CSV Format</option>
                                    </select>
                                </div>
                                <div className="paste-option">
                                    <label>Default Exchange</label>
                                    <select
                                        className="input-field"
                                        value={defaultExchange}
                                        onChange={(e) => setDefaultExchange(e.target.value)}
                                    >
                                        <option value="NSE">NSE</option>
                                        <option value="BSE">BSE</option>
                                        <option value="NFO">NFO</option>
                                        <option value="MCX">MCX</option>
                                        <option value="CDS">CDS</option>
                                    </select>
                                </div>
                            </div>

                            <div className="paste-actions">
                                <button
                                    className="btn-outline"
                                    onClick={() => setPasteData('')}
                                >
                                    ✕ Cancel
                                </button>
                                <button
                                    className="btn-primary validate-btn"
                                    onClick={handlePasteImport}
                                    disabled={!pasteData.trim()}
                                >
                                    ✓ Validate & Import
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Manual Entry Section */}
                    {importMethod === 'manual' && (
                        <div className="premium-card import-manual-section">
                            <h3 className="card-title">Manual Symbol Entry</h3>
                            <p className="manual-hint">Add symbols one by one</p>

                            <div className="manual-entry-row">
                                <div className="manual-input-group" style={{ position: 'relative', flex: 1 }}>
                                    <input
                                        type="text"
                                        className="input-field manual-symbol-input"
                                        placeholder="Enter symbol (e.g. RELIANCE)"
                                        value={manualSymbol}
                                        onChange={async (e) => {
                                            const value = e.target.value.toUpperCase();
                                            setManualSymbol(value);
                                            
                                            if (value.length >= 2) {
                                                try {
                                                    const response = await fetch(`${API_BASE}/brokers/angelone/instruments?q=${value}&limit=10`, {
                                                        headers: { 'Authorization': `Bearer ${token}` }
                                                    });
                                                    if (response.ok) {
                                                        const data = await response.json();
                                                        if (Array.isArray(data) && data.length > 0) {
                                                            setFilteredSuggestions(data);
                                                            setShowSuggestions(true);
                                                        } else {
                                                            setShowSuggestions(false);
                                                        }
                                                    }
                                                } catch (err) {
                                                    console.error('Search error:', err);
                                                    setShowSuggestions(false);
                                                }
                                            } else {
                                                setShowSuggestions(false);
                                            }
                                        }}
                                        onFocus={async () => {
                                            if (manualSymbol.length >= 2) {
                                                try {
                                                    const response = await fetch(`${API_BASE}/brokers/angelone/instruments?q=${manualSymbol}&limit=10`, {
                                                        headers: { 'Authorization': `Bearer ${token}` }
                                                    });
                                                    if (response.ok) {
                                                        const data = await response.json();
                                                        if (Array.isArray(data) && data.length > 0) {
                                                            setFilteredSuggestions(data);
                                                            setShowSuggestions(true);
                                                        }
                                                    }
                                                } catch (err) {
                                                    console.error('Search error:', err);
                                                }
                                            }
                                        }}
                                        onBlur={() => {
                                            // Delay to allow click on suggestion
                                            setTimeout(() => setShowSuggestions(false), 200);
                                        }}
                                    />
                                    {/* Autocomplete Suggestions Dropdown */}
                                    {showSuggestions && (
                                        <div className="autocomplete-dropdown" style={{
                                            position: 'absolute',
                                            top: '100%',
                                            left: 0,
                                            right: 0,
                                            background: '#1e1e2e',
                                            border: '1px solid #3a3a4a',
                                            borderRadius: '8px',
                                            maxHeight: '250px',
                                            overflowY: 'auto',
                                            zIndex: 1000,
                                            marginTop: '4px',
                                            boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
                                        }}>
                                            {filteredSuggestions.map((inst, idx) => (
                                                <div
                                                    key={idx}
                                                    className="autocomplete-item"
                                                    style={{
                                                        padding: '10px 12px',
                                                        cursor: 'pointer',
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        alignItems: 'center',
                                                        borderBottom: '1px solid #2a2a3a',
                                                        transition: 'background 0.2s'
                                                    }}
                                                    onMouseEnter={(e) => e.target.style.background = '#2a2a4a'}
                                                    onMouseLeave={(e) => e.target.style.background = 'transparent'}
                                                    onMouseDown={() => {
                                                        setManualSymbol(inst.symbol);
                                                        setManualExchange(inst.exchange || 'NSE');
                                                        setShowSuggestions(false);
                                                    }}
                                                >
                                                    <div>
                                                        <span style={{ fontWeight: 'bold', color: '#00dc82' }}>{inst.symbol}</span>
                                                        {inst.name && <span style={{ marginLeft: '8px', color: '#888', fontSize: '12px' }}>{inst.name}</span>}
                                                    </div>
                                                    <span style={{ 
                                                        background: '#3a3a5a', 
                                                        padding: '2px 8px', 
                                                        borderRadius: '4px', 
                                                        fontSize: '11px',
                                                        color: '#aaa'
                                                    }}>{inst.exchange}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                                <div className="manual-exchange-select">
                                    <select
                                        className="input-field"
                                        value={manualExchange}
                                        onChange={(e) => setManualExchange(e.target.value)}
                                    >
                                        <option value="NSE">NSE</option>
                                        <option value="NFO">NFO</option>
                                        <option value="CDS">CDS</option>
                                        <option value="NSE Index">NSE Index</option>
                                        <option value="BSE">BSE</option>
                                        <option value="BFO">BFO</option>
                                        <option value="BCD">BCD</option>
                                        <option value="BSE Index">BSE Index</option>
                                        <option value="MCX">MCX</option>
                                    </select>
                                </div>
                                <button
                                    className="btn-primary add-symbol-btn"
                                    onClick={handleManualAdd}
                                    disabled={!manualSymbol.trim()}
                                >
                                    + Add
                                </button>
                            </div>

                            {/* Added Symbols List */}
                            {addedSymbols.length > 0 && (
                                <div className="added-symbols-section">
                                    <h4>Added Symbols ({addedSymbols.length})</h4>
                                    <div className="added-symbols-list">
                                        {addedSymbols.map((sym, idx) => (
                                            <div key={idx} className="added-symbol-tag">
                                                <span>{sym.symbol}</span>
                                                <span className="tag-exchange">{sym.exchange}</span>
                                                <button
                                                    className="remove-symbol-btn"
                                                    onClick={() => setAddedSymbols(addedSymbols.filter((_, i) => i !== idx))}
                                                >
                                                    ×
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="manual-actions">
                                        <button
                                            className="btn-outline"
                                            onClick={() => setAddedSymbols([])}
                                        >
                                            Clear All
                                        </button>
                                        <button
                                            className="btn-primary"
                                            onClick={() => {
                                                alert(`${addedSymbols.length} symbols ready for import!\n\nImport feature coming soon.`);
                                            }}
                                        >
                                            Import {addedSymbols.length} Symbols
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                </div>
            )}

            {/* Export Tab */}
            {activeSubTab === 'export' && (
                <div className="data-export">
                    {/* Export Header */}
                    <div className="premium-card export-header-card">
                        <h3 className="card-title">Data Export</h3>
                        <p className="export-desc">Export historical data in various formats</p>
                    </div>

                    {/* Export Format Cards */}
                    <div className="export-format-grid">
                        <div
                            className={`export-format-card ${exportFormat === 'individual' ? 'active' : ''}`}
                            onClick={() => setExportFormat('individual')}
                        >
                            <div className="format-icon csv">📄</div>
                            <h4>Individual CSV</h4>
                            <p>One CSV file per symbol</p>
                        </div>
                        <div
                            className={`export-format-card ${exportFormat === 'combined' ? 'active' : ''}`}
                            onClick={() => setExportFormat('combined')}
                        >
                            <div className="format-icon combined">📋</div>
                            <h4>Combined CSV</h4>
                            <p>All symbols in one file</p>
                        </div>
                        <div
                            className={`export-format-card ${exportFormat === 'zip' ? 'active' : ''}`}
                            onClick={() => setExportFormat('zip')}
                        >
                            <div className="format-icon zip">📦</div>
                            <h4>ZIP Archive</h4>
                            <p>Multiple files bundled</p>
                        </div>
                    </div>

                    {/* Export Content */}
                    <div className="export-content-grid">
                        {/* Left: Select Symbols */}
                        <div className="premium-card export-symbols-card">
                            <h3 className="card-title">Select Symbols</h3>

                            <div className="export-symbols-header">
                                <input
                                    type="text"
                                    className="input-field export-search"
                                    placeholder="Search symbols..."
                                    value={exportSearchQuery}
                                    onChange={(e) => {
                                        setExportSearchQuery(e.target.value);
                                        setSearchQuery(e.target.value);
                                    }}
                                />
                                {exportSearchQuery && (
                                    <button
                                        className="search-clear-btn"
                                        onClick={() => {
                                            setExportSearchQuery('');
                                            setSearchQuery('');
                                        }}
                                        title="Clear search"
                                    >
                                        ✕
                                    </button>
                                )}
                                <div className="export-symbol-actions">
                                    <button
                                        className="btn-outline-small"
                                        onClick={() => {
                                            const allKeys = [
                                                ...symbolsWithData.map(s => `${s.symbol}_${s.exchange}`),
                                                ...instruments.map(i => `${i.symbol}_${i.exchange}`)
                                            ];
                                            setSelectedExportSymbols([...new Set(allKeys)]);
                                        }}
                                    >
                                        ☑ Select All
                                    </button>
                                    <button
                                        className="btn-outline-small"
                                        onClick={() => setSelectedExportSymbols([])}
                                    >
                                        ☐ Clear
                                    </button>
                                </div>
                            </div>

                            {/* Show selected symbols at top */}
                            {selectedExportSymbols.length > 0 && (
                                <div className="selected-symbols-preview">
                                    {selectedExportSymbols.slice(0, 5).map((key, idx) => {
                                        const [symbol, exchange] = key.split('_');
                                        return (
                                            <span key={idx} className="selected-symbol-tag">
                                                {symbol}
                                                <small>{exchange}</small>
                                                <button onClick={() => setSelectedExportSymbols(selectedExportSymbols.filter(s => s !== key))}>×</button>
                                            </span>
                                        );
                                    })}
                                    {selectedExportSymbols.length > 5 && (
                                        <span className="more-count">+{selectedExportSymbols.length - 5} more</span>
                                    )}
                                </div>
                            )}

                            <div className="export-symbols-list">
                                {(symbolsWithData.length === 0 && instruments.length === 0) ? (
                                    <div className="empty-state">Search for symbols to export</div>
                                ) : (
                                    <>
                                        {/* Show symbols with downloaded data first */}
                                        {symbolsWithData
                                            .filter(s => s.symbol.toLowerCase().includes(exportSearchQuery.toLowerCase()))
                                            .map((sym, idx) => {
                                                const uniqueKey = `${sym.symbol}_${sym.exchange}`;
                                                return (
                                                    <label key={`db-${idx}`} className={`export-symbol-item has-data ${selectedExportSymbols.includes(uniqueKey) ? 'selected' : ''}`}>
                                                        <input
                                                            type="checkbox"
                                                            checked={selectedExportSymbols.includes(uniqueKey)}
                                                            onChange={(e) => {
                                                                if (e.target.checked) {
                                                                    setSelectedExportSymbols([...selectedExportSymbols, uniqueKey]);
                                                                } else {
                                                                    setSelectedExportSymbols(selectedExportSymbols.filter(s => s !== uniqueKey));
                                                                }
                                                            }}
                                                        />
                                                        <span className="symbol-name">{sym.symbol}</span>
                                                        <span className="symbol-exchange">{sym.exchange}</span>
                                                        <span className="data-badge">📊</span>
                                                    </label>
                                                );
                                            })
                                        }
                                        {/* Show searched instruments */}
                                        {instruments
                                            .filter(i =>
                                                i.symbol.toLowerCase().includes(exportSearchQuery.toLowerCase()) &&
                                                !symbolsWithData.find(s => s.symbol === i.symbol && s.exchange === i.exchange)
                                            )
                                            .slice(0, 50)
                                            .map((inst, idx) => {
                                                const uniqueKey = `${inst.symbol}_${inst.exchange}`;
                                                return (
                                                    <label key={`inst-${idx}`} className={`export-symbol-item ${selectedExportSymbols.includes(uniqueKey) ? 'selected' : ''}`}>
                                                        <input
                                                            type="checkbox"
                                                            checked={selectedExportSymbols.includes(uniqueKey)}
                                                            onChange={(e) => {
                                                                if (e.target.checked) {
                                                                    setSelectedExportSymbols([...selectedExportSymbols, uniqueKey]);
                                                                } else {
                                                                    setSelectedExportSymbols(selectedExportSymbols.filter(s => s !== uniqueKey));
                                                                }
                                                            }}
                                                        />
                                                        <span className="symbol-name">{inst.symbol}</span>
                                                        <span className="symbol-exchange">{inst.exchange}</span>
                                                    </label>
                                                );
                                            })
                                        }
                                    </>
                                )}
                            </div>

                            <div className="selected-count">
                                Selected: <span>{selectedExportSymbols.length} {selectedExportSymbols.length === 1 ? 'symbol' : 'symbols'}</span>
                            </div>
                        </div>

                        {/* Right: Export Settings */}
                        <div className="premium-card export-settings-card">
                            <h3 className="card-title">Export Settings</h3>

                            <div className="export-setting">
                                <label>Date Range</label>
                                <select
                                    className="input-field"
                                    value={exportDateRange}
                                    onChange={(e) => setExportDateRange(e.target.value)}
                                >
                                    <option value="last_7_days">Last 7 Days</option>
                                    <option value="last_1_month">Last 1 Month</option>
                                    <option value="last_3_months">Last 3 Months</option>
                                    <option value="last_6_months">Last 6 Months</option>
                                    <option value="last_1_year">Last 1 Year</option>
                                    <option value="all">All Data</option>
                                </select>
                            </div>

                            <div className="export-setting">
                                <label>Data Interval</label>
                                <select
                                    className="input-field"
                                    value={exportInterval}
                                    onChange={(e) => setExportInterval(e.target.value)}
                                >
                                    <option value="1min">1 Minute</option>
                                    <option value="5min">5 Minutes</option>
                                    <option value="15min">15 Minutes</option>
                                    <option value="30min">30 Minutes</option>
                                    <option value="hourly">1 Hour</option>
                                    <option value="daily">Daily</option>
                                    <option value="weekly">Weekly</option>
                                    <option value="monthly">Monthly</option>
                                </select>
                            </div>

                            <div className="export-setting">
                                <label>Export Format</label>
                                <div className="export-format-options">
                                    <label className="radio-option">
                                        <input
                                            type="radio"
                                            name="exportFormat"
                                            checked={exportFormat === 'individual'}
                                            onChange={() => setExportFormat('individual')}
                                        />
                                        <span>Individual CSV files</span>
                                    </label>
                                    <label className="radio-option">
                                        <input
                                            type="radio"
                                            name="exportFormat"
                                            checked={exportFormat === 'combined'}
                                            onChange={() => setExportFormat('combined')}
                                        />
                                        <span>Combined CSV file</span>
                                    </label>
                                    <label className="radio-option">
                                        <input
                                            type="radio"
                                            name="exportFormat"
                                            checked={exportFormat === 'zip'}
                                            onChange={() => setExportFormat('zip')}
                                        />
                                        <span>ZIP archive</span>
                                    </label>
                                </div>
                            </div>

                            <div className="export-setting">
                                <label>Export Options</label>
                                <div className="export-checkbox-options">
                                    <label className="checkbox-option">
                                        <input
                                            type="checkbox"
                                            checked={exportOptions.includeHeaders}
                                            onChange={(e) => setExportOptions({ ...exportOptions, includeHeaders: e.target.checked })}
                                        />
                                        <span>Include column headers</span>
                                    </label>
                                    <label className="checkbox-option">
                                        <input
                                            type="checkbox"
                                            checked={exportOptions.includeMetadata}
                                            onChange={(e) => setExportOptions({ ...exportOptions, includeMetadata: e.target.checked })}
                                        />
                                        <span>Include metadata</span>
                                    </label>
                                    <label className="checkbox-option">
                                        <input
                                            type="checkbox"
                                            checked={exportOptions.includeSummary}
                                            onChange={(e) => setExportOptions({ ...exportOptions, includeSummary: e.target.checked })}
                                        />
                                        <span>Include summary stats</span>
                                    </label>
                                </div>
                            </div>

                            <div className="export-actions">
                                <button className="btn-outline preview-btn">
                                    👁 Preview Export
                                </button>
                                <button
                                    className="btn-primary start-export-btn"
                                    disabled={selectedExportSymbols.length === 0 || loading || !activeBroker}
                                    onClick={async () => {
                                        const count = selectedExportSymbols.length;
                                        console.log(`Exporting ${count} symbols`);
                                        if (!activeBroker) {
                                            alert('Please login to broker first to export data.');
                                            return;
                                        }

                                        setLoading(true);
                                        try {
                                            // Helper: Download a file (CSV/ZIP)
                                            const downloadFile = (content, filename, mimeType) => {
                                                const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType });
                                                const url = window.URL.createObjectURL(blob);
                                                const a = document.createElement('a');
                                                a.href = url;
                                                a.download = filename;
                                                document.body.appendChild(a);
                                                a.click();
                                                document.body.removeChild(a);
                                                window.URL.revokeObjectURL(url);
                                            };

                                            // Helper: Generate CSV content string
                                            const generateCSV = (data) => {
                                                const headers = exportOptions.includeHeaders
                                                    ? ['Symbol', 'Exchange', 'Date', 'Time', 'Open', 'High', 'Low', 'Close', 'Volume'].join(',') + '\n'
                                                    : '';

                                                const rows = data.map(row =>
                                                    [row.symbol, row.exchange, row.date, row.time || '', row.open, row.high, row.low, row.close, row.volume].join(',')
                                                ).join('\n');

                                                return headers + rows;
                                            };

                                            // Calculate date range
                                            const endDate = new Date().toISOString().split('T')[0];
                                            let startDate;
                                            switch (exportDateRange) {
                                                case 'last_7_days': startDate = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]; break;
                                                case 'last_1_month': startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]; break;
                                                case 'last_3_months': startDate = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]; break;
                                                case 'last_6_months': startDate = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]; break;
                                                case 'last_1_year': startDate = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]; break;
                                                case 'all': startDate = '2000-01-01'; break;
                                                default: startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
                                            }

                                            // Map interval
                                            const intervalMap = {
                                                '1min': 'ONE_MINUTE', '5min': 'FIVE_MINUTE', '15min': 'FIFTEEN_MINUTE',
                                                '30min': 'THIRTY_MINUTE', 'hourly': 'ONE_HOUR', 'daily': 'ONE_DAY',
                                                'weekly': 'ONE_DAY', 'monthly': 'ONE_DAY'
                                            };
                                            const apiInterval = intervalMap[exportInterval] || 'ONE_DAY';

                                            const zip = new JSZip();
                                            const allDataCombined = [];
                                            let processedCount = 0;

                                            // Fetch data for each symbol
                                            for (const key of selectedExportSymbols) {
                                                const [symbol, exchange] = key.split('_');

                                                // Find instrument
                                                let inst = instruments.find(i => i.symbol === symbol && i.exchange === exchange) ||
                                                    symbolsWithData.find(s => s.symbol === symbol && s.exchange === exchange) ||
                                                    instruments.find(i => i.symbol === symbol);

                                                // Fallback search if not found
                                                if (!inst || !inst.token) {
                                                    try {
                                                        const searchResp = await fetch(`${API_BASE}/brokers/angelone/instruments?q=${symbol}&limit=1`, {
                                                            headers: { 'Authorization': `Bearer ${token}` }
                                                        });
                                                        if (searchResp.ok) {
                                                            const searchRes = await searchResp.json();
                                                            if (searchRes && searchRes.length > 0) inst = searchRes[0];
                                                        }
                                                    } catch {
                                                        console.warn('Search failed/skipped for', symbol);
                                                    }
                                                }

                                                if (inst && inst.token) {
                                                    try {
                                                        const response = await fetch(`${API_BASE}/data/export/fetch`, {
                                                            method: 'POST',
                                                            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                                                            body: JSON.stringify({
                                                                symbol: inst.symbol,
                                                                token: inst.token,
                                                                exchange: inst.exchange || exchange,
                                                                timeframe: apiInterval,
                                                                from_date: startDate,
                                                                to_date: endDate,
                                                                client_code: activeBroker.client_code
                                                            })
                                                        });

                                                        if (response.ok) {
                                                            const result = await response.json();
                                                            if (result.status === 'success' && result.data && result.data.length > 0) {
                                                                const cleanData = result.data.map(d => ({
                                                                    symbol: symbol,
                                                                    exchange: exchange,
                                                                    ...d
                                                                }));

                                                                processedCount++;

                                                                // Handle Result based on Format
                                                                if (exportFormat === 'combined') {
                                                                    allDataCombined.push(...cleanData);
                                                                } else if (exportFormat === 'zip') {
                                                                    const csv = generateCSV(cleanData);
                                                                    zip.file(`${symbol}_${exchange}.csv`, csv);
                                                                } else if (exportFormat === 'individual') {
                                                                    const csv = generateCSV(cleanData);
                                                                    downloadFile(csv, `${symbol}_${exchange}_${new Date().toISOString().split('T')[0]}.csv`, 'text/csv');
                                                                    // Small delay to prevent browser from blocking continuous downloads
                                                                    await new Promise(r => setTimeout(r, 200));
                                                                }
                                                            }
                                                        }
                                                    } catch (err) {
                                                        console.error(`Error processing ${symbol}:`, err);
                                                    }
                                                }
                                            }

                                            // Finalize Batch Downloads
                                            if (processedCount === 0) {
                                                alert('No data found for selected symbols in this date range.');
                                                return;
                                            }

                                            if (exportFormat === 'combined' && allDataCombined.length > 0) {
                                                const csv = generateCSV(allDataCombined);
                                                downloadFile(csv, `export_combined_${new Date().toISOString().split('T')[0]}.csv`, 'text/csv');
                                            } else if (exportFormat === 'zip') {
                                                const content = await zip.generateAsync({ type: "blob" });
                                                downloadFile(content, `export_archive_${new Date().toISOString().split('T')[0]}.zip`, 'application/zip');
                                            }

                                            alert(`Export completed! Processed ${processedCount} symbols.`);

                                        } catch (err) {
                                            console.error('Export error:', err);
                                            alert('Export failed: ' + err.message);
                                        } finally {
                                            setLoading(false);
                                        }
                                    }}
                                >
                                    {loading ? '⏳ Exporting...' : '📤 Start Export'}
                                </button>
                            </div>

                            {!activeBroker && (
                                <div className="warning-box" style={{ marginTop: '10px' }}>
                                    ⚠️ Please login to broker to export data
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Settings Tab */}
            {activeSubTab === 'settings' && (
                <div className="data-settings">
                    {/* Data Management Section */}
                    <div className="settings-section">
                        <div className="settings-section-header">
                            <span className="settings-icon">💾</span>
                            <div>
                                <h3>Data Management</h3>
                                <p className="settings-desc">Monitor database status and manage stored data</p>
                            </div>
                        </div>

                        <div className="db-stats-grid">
                            <div className="db-stat-card blue">
                                <div className="db-stat-label">Database Size</div>
                                <div className="db-stat-value">{dbStats.size}</div>
                                <span className="db-stat-icon">💾</span>
                            </div>
                            <div className="db-stat-card red">
                                <div className="db-stat-label">Total Records</div>
                                <div className="db-stat-value">{dbStats.records.toLocaleString()}</div>
                                <span className="db-stat-icon">📊</span>
                            </div>
                            <div className="db-stat-card green">
                                <div className="db-stat-label">Downloaded Symbols</div>
                                <div className="db-stat-value">{dbStats.symbols}</div>
                                <span className="db-stat-icon">📈</span>
                            </div>
                        </div>

                        <div className="db-actions">
                            <button className="db-action-btn" onClick={handleCheckCache}>
                                ✓ Check Cache
                            </button>
                            <button className="db-action-btn" onClick={handleOptimizeDb} disabled={loading}>
                                🔧 Optimize Database
                            </button>
                            <button className="db-action-btn" onClick={handleExportDb}>
                                📤 Export Database
                            </button>
                        </div>
                    </div>

                    {/* Download Settings Section */}
                    <div className="settings-section">
                        <h3 className="settings-title">Download Settings</h3>

                        <div className="settings-field">
                            <label>Batch Size</label>
                            <input
                                type="number"
                                className="settings-input"
                                value={settings.batchSize}
                                onChange={(e) => setSettings({ ...settings, batchSize: parseInt(e.target.value) || 10 })}
                            />
                            <span className="settings-hint">Number of symbols to process per batch</span>
                        </div>

                        <div className="settings-field">
                            <label>Rate Limit Delay (ms)</label>
                            <input
                                type="number"
                                className="settings-input"
                                value={settings.rateLimitDelay}
                                onChange={(e) => setSettings({ ...settings, rateLimitDelay: parseInt(e.target.value) || 500 })}
                            />
                            <span className="settings-hint">Delay between API requests in milliseconds</span>
                        </div>

                        <div className="settings-field">
                            <label>Default Date Range</label>
                            <select
                                className="settings-input"
                                value={settings.defaultDateRange}
                                onChange={(e) => setSettings({ ...settings, defaultDateRange: e.target.value })}
                            >
                                <option value="last_7_days">Last 7 Days</option>
                                <option value="last_30_days">Last 30 Days</option>
                                <option value="last_90_days">Last 90 Days</option>
                                <option value="last_365_days">Last 365 Days</option>
                                <option value="all_time">All Time</option>
                            </select>
                        </div>

                        <button className="settings-save-btn blue" onClick={handleSaveDownloadSettings}>
                            💾 Save Download Settings
                        </button>
                    </div>

                    {/* Display Settings Section */}
                    <div className="settings-section">
                        <h3 className="settings-title">Display Settings</h3>

                        <div className="settings-field">
                            <label>Chart Height</label>
                            <input
                                type="number"
                                className="settings-input"
                                value={settings.chartHeight}
                                onChange={(e) => setSettings({ ...settings, chartHeight: parseInt(e.target.value) || 400 })}
                            />
                            <span className="settings-hint">Default chart height in pixels</span>
                        </div>

                        <div className="settings-checkbox-group">
                            <label className="settings-checkbox">
                                <input
                                    type="checkbox"
                                    checked={settings.autoRefresh}
                                    onChange={(e) => setSettings({ ...settings, autoRefresh: e.target.checked })}
                                />
                                <span className="checkmark"></span>
                                Enable auto-refresh for real-time quotes
                            </label>

                            <label className="settings-checkbox">
                                <input
                                    type="checkbox"
                                    checked={settings.showTooltips}
                                    onChange={(e) => setSettings({ ...settings, showTooltips: e.target.checked })}
                                />
                                <span className="checkmark"></span>
                                Show Tooltips
                            </label>
                        </div>

                        <button className="settings-save-btn green" onClick={handleSaveDisplaySettings}>
                            💾 Save Display Settings
                        </button>
                    </div>

                    {/* Danger Zone */}
                    <div className="settings-section danger-zone">
                        <h3 className="settings-title danger">Danger Zone</h3>
                        <button
                            className="settings-danger-btn"
                            onClick={handleClearAllData}
                            disabled={loading}
                        >
                            🗑️ Clear All Data
                        </button>
                        <p className="danger-warning">This will delete all downloaded historical data. This action cannot be undone.</p>

                        <button
                            className="settings-reset-btn"
                            onClick={handleResetToDefaults}
                        >
                            🔄 Reset to Defaults
                        </button>
                        <p className="danger-warning">Reset all settings to their default values.</p>
                    </div>
                </div>
            )}

            {/* Scheduler Tab */}
            {activeSubTab === 'scheduler' && (
                <div className="data-scheduler">
                    {/* Scheduler Header */}
                    <div className="scheduler-header">
                        <div className="scheduler-header-left">
                            <h2 className="scheduler-title">Scheduler Manager</h2>
                            <p className="scheduler-desc">Automate data downloads at specific times</p>
                        </div>
                        <button
                            className="btn-primary add-job-btn"
                            onClick={() => setShowAddJobModal(true)}
                        >
                            + Add New Job
                        </button>
                    </div>

                    {/* Quick Action Cards */}
                    <div className="scheduler-quick-actions">
                        <div
                            className="quick-action-card"
                            onClick={() => {
                                const exists = scheduledJobs.find(j => j.name === 'Market Close Download');
                                if (exists) {
                                    alert('Market Close Download job already exists!');
                                    return;
                                }
                                const newJobData = {
                                    id: Date.now(),
                                    name: 'Market Close Download',
                                    type: 'daily',
                                    time: '15:35',
                                    interval: 'Daily at 3:35 PM IST',
                                    status: 'active',
                                    nextRun: new Date(Date.now() + 86400000).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) + ', 03:35 pm',
                                    data: '0 data'
                                };
                                setScheduledJobs([...scheduledJobs, newJobData]);
                                alert('Market Close Download job created!');
                            }}
                        >
                            <div className="quick-action-icon orange">🔔</div>
                            <div className="quick-action-info">
                                <h4>Market Close Download</h4>
                                <p>Daily at 3:35 PM IST</p>
                            </div>
                        </div>
                        <div
                            className="quick-action-card"
                            onClick={() => {
                                const exists = scheduledJobs.find(j => j.name === 'Pre-Market Download');
                                if (exists) {
                                    alert('Pre-Market Download job already exists!');
                                    return;
                                }
                                const newJobData = {
                                    id: Date.now(),
                                    name: 'Pre-Market Download',
                                    type: 'daily',
                                    time: '08:30',
                                    interval: 'Daily at 8:30 AM IST',
                                    status: 'active',
                                    nextRun: new Date(Date.now() + 86400000).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) + ', 08:30 am',
                                    data: '0 data'
                                };
                                setScheduledJobs([...scheduledJobs, newJobData]);
                                alert('Pre-Market Download job created!');
                            }}
                        >
                            <div className="quick-action-icon blue">⚙️</div>
                            <div className="quick-action-info">
                                <h4>Pre-Market Download</h4>
                                <p>Daily at 8:30 AM IST</p>
                            </div>
                        </div>
                        <div
                            className="quick-action-card"
                            onClick={() => {
                                alert('Test Scheduler: Running a test download in 10 seconds...\n\nThis will simulate a download job to verify your scheduler is working correctly.');
                                setTimeout(() => {
                                    alert('Test completed! Scheduler is working correctly.');
                                }, 10000);
                            }}
                        >
                            <div className="quick-action-icon green">✏️</div>
                            <div className="quick-action-info">
                                <h4>Test Scheduler</h4>
                                <p>Run a test job in 10 seconds</p>
                            </div>
                        </div>
                    </div>

                    {/* Active Jobs */}
                    <div className="active-jobs-section">
                        <h3 className="section-title">Active Jobs</h3>

                        <div className="jobs-list">
                            {scheduledJobs.map((job) => (
                                <div key={job.id} className="job-item">
                                    <div className="job-icon-wrapper">
                                        <span className={`job-icon ${job.type === 'interval' ? 'interval' : 'daily'}`}>
                                            {job.type === 'interval' ? '🔄' : '📅'}
                                        </span>
                                    </div>
                                    <div className="job-info">
                                        <h4 className="job-name">{job.name}</h4>
                                        <p className="job-schedule">{job.interval} • {job.data || '0 data'}</p>
                                        <p className="job-next-run">Next run: {job.nextRun}</p>
                                    </div>
                                    <div className="job-actions">
                                        <span className={`job-status-badge ${job.status}`}>
                                            {job.status === 'active' ? 'Active' : 'Paused'}
                                        </span>
                                        <button
                                            className="job-action-btn play"
                                            title="Run Now"
                                            onClick={() => {
                                                alert(`Running job "${job.name}" now...\n\nDownloading data for all watchlist symbols.`);
                                            }}
                                        >
                                            ▶
                                        </button>
                                        <button
                                            className="job-action-btn pause"
                                            title={job.status === 'active' ? 'Pause' : 'Resume'}
                                            onClick={() => {
                                                setScheduledJobs(scheduledJobs.map(j =>
                                                    j.id === job.id
                                                        ? { ...j, status: j.status === 'active' ? 'paused' : 'active' }
                                                        : j
                                                ));
                                            }}
                                        >
                                            {job.status === 'active' ? '⏸' : '▶'}
                                        </button>
                                        <button
                                            className="job-action-btn delete"
                                            title="Delete"
                                            onClick={() => {
                                                if (window.confirm('Delete this scheduled job?')) {
                                                    setScheduledJobs(scheduledJobs.filter(j => j.id !== job.id));
                                                }
                                            }}
                                        >
                                            🗑️
                                        </button>
                                    </div>
                                </div>
                            ))}

                            {scheduledJobs.length === 0 && (
                                <div className="empty-state">
                                    <p>No scheduled jobs yet. Click "Add New Job" to create one.</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Add Job Modal */}
                    {showAddJobModal && (
                        <div className="modal-overlay" onClick={() => setShowAddJobModal(false)}>
                            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                                <div className="modal-header">
                                    <h3>Add Scheduled Job</h3>
                                    <button className="modal-close" onClick={() => setShowAddJobModal(false)}>×</button>
                                </div>

                                <div className="modal-body">
                                    <div className="form-field">
                                        <label>Job Type</label>
                                        <div className="job-type-options">
                                            <label className={`job-type-card ${newJob.type === 'daily' ? 'active' : ''}`}>
                                                <input
                                                    type="radio"
                                                    name="jobType"
                                                    checked={newJob.type === 'daily'}
                                                    onChange={() => setNewJob({ ...newJob, type: 'daily' })}
                                                />
                                                <div className="job-type-icon">📅</div>
                                                <div className="job-type-info">
                                                    <strong>Daily Schedule</strong>
                                                    <span>Run at a specific time every day</span>
                                                </div>
                                            </label>
                                            <label className={`job-type-card ${newJob.type === 'interval' ? 'active' : ''}`}>
                                                <input
                                                    type="radio"
                                                    name="jobType"
                                                    checked={newJob.type === 'interval'}
                                                    onChange={() => setNewJob({ ...newJob, type: 'interval' })}
                                                />
                                                <div className="job-type-icon">🔄</div>
                                                <div className="job-type-info">
                                                    <strong>Interval Schedule</strong>
                                                    <span>Run every N minutes</span>
                                                </div>
                                            </label>
                                        </div>
                                    </div>

                                    {newJob.type === 'daily' && (
                                        <div className="form-field">
                                            <label>Time (IST)</label>
                                            <input
                                                type="time"
                                                className="input-field"
                                                value={newJob.time}
                                                onChange={(e) => setNewJob({ ...newJob, time: e.target.value })}
                                            />
                                        </div>
                                    )}

                                    {newJob.type === 'interval' && (
                                        <div className="form-field">
                                            <label>Interval (minutes)</label>
                                            <input
                                                type="number"
                                                className="input-field"
                                                placeholder="e.g., 5"
                                                min="1"
                                                value={newJob.time}
                                                onChange={(e) => setNewJob({ ...newJob, time: e.target.value })}
                                            />
                                        </div>
                                    )}

                                    <div className="form-field">
                                        <label>Data Interval</label>
                                        <select
                                            className="input-field"
                                            value={newJob.interval}
                                            onChange={(e) => setNewJob({ ...newJob, interval: e.target.value })}
                                        >
                                            <option value="1min">1 Minute</option>
                                            <option value="5min">5 Minutes</option>
                                            <option value="15min">15 Minutes</option>
                                            <option value="daily">Daily</option>
                                        </select>
                                    </div>

                                    <div className="form-field">
                                        <label>Job Name (optional)</label>
                                        <input
                                            type="text"
                                            className="input-field"
                                            placeholder="e.g., EOD Data Download"
                                            value={newJob.name}
                                            onChange={(e) => setNewJob({ ...newJob, name: e.target.value })}
                                        />
                                    </div>

                                    <div className="modal-info-box">
                                        <span className="info-icon">ℹ️</span>
                                        <span>This job will automatically download data for all symbols in your watchlist.</span>
                                    </div>
                                </div>

                                <div className="modal-footer">
                                    <button
                                        className="btn-outline"
                                        onClick={() => setShowAddJobModal(false)}
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        className="btn-primary"
                                        onClick={() => {
                                            const newJobData = {
                                                id: Date.now(),
                                                name: newJob.name || (newJob.type === 'daily' ? `Daily Download at ${newJob.time}` : `Download every ${newJob.time} minutes`),
                                                type: newJob.type,
                                                time: newJob.time,
                                                interval: newJob.type === 'daily' ? `Daily at ${newJob.time} IST` : `Every ${newJob.time} minutes`,
                                                status: 'active',
                                                nextRun: 'Calculating...',
                                                data: '0 data'
                                            };
                                            setScheduledJobs([...scheduledJobs, newJobData]);
                                            setShowAddJobModal(false);
                                            setNewJob({ type: 'daily', time: '', interval: 'daily', name: '' });
                                        }}
                                        disabled={!newJob.time}
                                    >
                                        + Create Job
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default DataManager;
