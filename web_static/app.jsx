const { useState, useEffect, useCallback, useMemo, useRef } = React;
const { Button, Modal } = window.UIComponents;

// 等待components.jsx加载后，从window获取业务组件
const ProxyManager = window.ProxyManager;
const EmailConfig = window.EmailConfig;

// ====== 进度条组件 (悬浮窗) ======
const ProgressBar = ({ progress, total, logs, visible, onClose }) => {
    const [minimized, setMinimized] = useState(false);
    const [position, setPosition] = useState({ x: window.innerWidth - 470, y: 20 });
    const [dragging, setDragging] = useState(false);
    const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
    const logsEndRef = useRef(null);
    
    // 自动滚动到底部
    useEffect(() => {
        if (logsEndRef.current && !minimized) {
            logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs, minimized]);
    
    // 拖动处理
    const handleMouseDown = (e) => {
        if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
            return; // 点击按钮时不触发拖动
        }
        setDragging(true);
        setDragOffset({
            x: e.clientX - position.x,
            y: e.clientY - position.y
        });
    };
    
    useEffect(() => {
        const handleMouseMove = (e) => {
            if (dragging) {
                const newX = Math.max(0, Math.min(e.clientX - dragOffset.x, window.innerWidth - (minimized ? 300 : 450)));
                const newY = Math.max(0, Math.min(e.clientY - dragOffset.y, window.innerHeight - 100));
                setPosition({ x: newX, y: newY });
            }
        };
        
        const handleMouseUp = () => {
            setDragging(false);
        };
        
        if (dragging) {
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
            return () => {
                document.removeEventListener('mousemove', handleMouseMove);
                document.removeEventListener('mouseup', handleMouseUp);
            };
        }
    }, [dragging, dragOffset, minimized]);
    
    if (!visible) return null;
    
    const percentage = total > 0 ? Math.round((progress / total) * 100) : 0;
    const isRunning = progress < total && total > 0;
    
    return (
        <div 
            className={`floating-window ${minimized ? 'minimized' : ''} ${dragging ? 'dragging' : ''}`}
            style={{
                top: `${position.y}px`,
                left: `${position.x}px`
            }}
        >
            {/* 标题栏 */}
            <div className="floating-header" onMouseDown={handleMouseDown}>
                <div className="floating-title">
                    {isRunning && <div className="pulse-indicator" />}
                    <span>任务进度 {percentage}%</span>
                </div>
                <div className="floating-controls">
                    <button
                        onClick={() => setMinimized(!minimized)}
                        className="floating-btn"
                        title={minimized ? '展开' : '最小化'}
                    >
                        {minimized ? '□' : '_'}
                    </button>
                    {!isRunning && onClose && (
                        <button onClick={onClose} className="floating-btn" title="关闭">
                            ×
                        </button>
                    )}
                </div>
            </div>
            
            {/* 内容区 */}
            {!minimized && (
                <div className="floating-content">
                    {/* 进度条 */}
                    <div className="progress-container">
                        <div className="progress-bar" style={{ width: `${percentage}%` }}>
                            {percentage > 10 && `${percentage}%`}
                        </div>
                    </div>
                    
                    {/* 统计信息 */}
                    <div className="progress-stats">
                        <span>进度: {progress} / {total}</span>
                        <span className="text-green">
                            {isRunning ? '进行中...' : '已完成'}
                        </span>
                    </div>
                    
                    {/* 日志区 */}
                    <div className="log-container">
                        {logs.length === 0 ? (
                            <div className="log-empty">等待任务开始...</div>
                        ) : (
                            <>
                                {logs.map((log, idx) => (
                                    <div 
                                        key={idx} 
                                        className={`log-line ${
                                            log.includes('✓') ? 'log-success' : 
                                            log.includes('✗') ? 'log-error' : 'log-info'
                                        }`}
                                    >
                                        {log}
                                    </div>
                                ))}
                                <div ref={logsEndRef} />
                            </>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

// ====== 账号表格组件 ======
const AccountsTable = ({ accounts, filter, onCheckAccount, onMarkAccount, onDeleteAccount, onShowDetails, accountType = 'normal' }) => {
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(20);
    const [checkingIndex, setCheckingIndex] = useState(null);
    
    const filtered = useMemo(() => {
        if (filter === 'available') return accounts.filter(a => !a.used);
        if (filter === 'used') return accounts.filter(a => a.used);
        return accounts;
    }, [accounts, filter]);
    
    // 重置页码当筛选改变时
    useEffect(() => {
        setCurrentPage(1);
    }, [filter]);
    
    // 计算分页
    const totalPages = Math.ceil(filtered.length / pageSize);
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, filtered.length);
    const pageData = filtered.slice(startIndex, endIndex);
    
    if (filtered.length === 0) {
        return (
            <div className="empty-state">
                <div className="empty-icon">📦</div>
                <p>暂无账号数据</p>
            </div>
        );
    }
    
    const maskEmail = (email) => {
        if (!email || email === 'N/A') return email;
        const [name, domain] = email.split('@');
        if (!name || !domain) return email;
        return name.slice(0, 3) + '***@' + domain.slice(0, 2) + '***';
    };
    
    const formatDateTime = (timestamp) => {
        if (!timestamp) return '-';
        try {
            const date = new Date(timestamp);
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            return `${year}-${month}-${day} ${hours}:${minutes}`;
        } catch (e) {
            return '-';
        }
    };
    
    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
    };
    
    const changePage = (page) => {
        setCurrentPage(page);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };
    
    const changePageSize = (size) => {
        setPageSize(size);
        setCurrentPage(1);
    };
    
    const handleCheckAccount = async (index) => {
        setCheckingIndex(index);
        try {
            await onCheckAccount(index);
        } finally {
            setCheckingIndex(null);
        }
    };
    
    return (
        <>
            <table className="table">
                <thead>
                    <tr>
                        <th className="table-header" style={{ width: '40px' }}>#</th>
                        <th className="table-header" style={{ width: '160px' }}>邮箱</th>
                        {accountType === 'outlook' && (
                            <th className="table-header" style={{ width: '140px' }}>账号密码</th>
                        )}
                        <th className="table-header" style={{ width: '90px' }}>IP类型</th>
                        <th className="table-header" style={{ width: '130px' }}>注册时间</th>
                        {accountType !== 'outlook' && (
                            <>
                                <th className="table-header" style={{ width: '130px' }}>检查时间</th>
                                <th className="table-header" style={{ width: '200px' }}>SessionKey</th>
                                <th className="table-header" style={{ width: '70px' }}>健康</th>
                                <th className="table-header" style={{ width: '70px' }}>状态</th>
                            </>
                        )}
                        <th className="table-header" style={{ width: '180px' }}>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {pageData.map((account, idx) => {
                        const sessionKey = account.cookies?.sessionKey || 'N/A';
                        const health = account.health || 'unknown';
                        const healthIcon = health === 'healthy' ? '✓' : health === 'expired' ? '✗' : '?';
                        const healthColor = health === 'healthy' ? '#00ff88' : health === 'expired' ? '#ff4444' : '#888';
                        const healthText = health === 'healthy' ? '健康' : health === 'expired' ? '失效' : '未知';
                        
                        // 获取IP类型
                        const ipInfo = account.ip_info || {};
                        const ipType = ipInfo.type || '-';
                        const ipTypeColor = ipType === '住宅IP' || ipType === '移动网络' ? '#00ff88' :
                                          ipType === '数据中心' || ipType === '代理/VPN' ? '#ff8800' : '#888';
                        
                        const accountIndex = accounts.indexOf(account);
                        const isChecking = checkingIndex === accountIndex;
                        
                        return (
                            <tr key={idx} className={account.used ? 'row-used' : ''}>
                                <td className="table-cell">{startIndex + idx + 1}</td>
                                <td className="table-cell">{maskEmail(account.email)}</td>
                                {accountType === 'outlook' && (
                                    <td className="table-cell">
                                        <div className="session-key-row">
                                            <button
                                                className="copy-btn"
                                                onClick={() => {
                                                    const fullEmail = account.email || account.email_address || 'N/A';
                                                    copyToClipboard(fullEmail);
                                                }}
                                                title="复制完整邮箱"
                                                style={{ marginRight: '5px' }}
                                            >
                                                📧
                                            </button>
                                            <button
                                                className="copy-btn"
                                                onClick={() => {
                                                    const password = account.password || 'N/A';
                                                    copyToClipboard(password);
                                                }}
                                                title="复制密码"
                                            >
                                                🔑
                                            </button>
                                            <button
                                                className="copy-btn"
                                                onClick={() => {
                                                    const fullEmail = account.email || account.email_address || 'N/A';
                                                    const password = account.password || 'N/A';
                                                    copyToClipboard(`${fullEmail}\n${password}`);
                                                }}
                                                title="复制账号密码(两行)"
                                                style={{ marginLeft: '5px' }}
                                            >
                                                📋
                                            </button>
                                        </div>
                                    </td>
                                )}
                                <td 
                                    className="table-cell text-sm" 
                                    style={{ 
                                        color: ipTypeColor, 
                                        cursor: 'pointer',
                                        textDecoration: 'underline'
                                    }}
                                    onClick={() => onShowDetails('IP信息', account.ip_info)}
                                    title="点击查看详细IP信息"
                                >
                                    {ipType}
                                </td>
                                <td className="table-cell text-sm text-gray">
                                    {formatDateTime(account.saved_at)}
                                </td>
                                {accountType !== 'outlook' && (
                                    <>
                                        <td className="table-cell text-sm text-gray">
                                            {formatDateTime(account.checked_at)}
                                        </td>
                                        <td className="table-cell">
                                            <div className="session-key-row">
                                                <span
                                                    className="session-key-text"
                                                    onClick={() => onShowDetails('SessionKey', sessionKey)}
                                                    title="点击查看完整SessionKey"
                                                >
                                                    {sessionKey.slice(0, 12)}...
                                                </span>
                                                <button
                                                    className="copy-btn"
                                                    onClick={() => copyToClipboard('sessionKey=' + sessionKey)}
                                                    title="复制完整SessionKey"
                                                >
                                                    📋
                                                </button>
                                            </div>
                                        </td>
                                        <td className="table-cell" style={{ color: healthColor }}>
                                            {healthIcon} {healthText}
                                        </td>
                                        <td className="table-cell">
                                            {account.used ? (
                                                <span 
                                                    className="badge badge-used clickable" 
                                                    onClick={() => onMarkAccount(accountIndex, false)}
                                                    title="点击切换为未使用"
                                                >
                                                    已使用
                                                </span>
                                            ) : (
                                                <span 
                                                    className="badge badge-available clickable"
                                                    onClick={() => onMarkAccount(accountIndex, true)}
                                                    title="点击切换为已使用"
                                                >
                                                    未使用
                                                </span>
                                            )}
                                        </td>
                                    </>
                                )}
                                <td className="table-cell">
                                    <div className="action-buttons">
                                        {accountType !== 'outlook' && (
                                            <Button
                                                variant="secondary"
                                                style={{ padding: '6px 12px', fontSize: '0.85em' }}
                                                onClick={() => handleCheckAccount(accountIndex)}
                                                disabled={isChecking}
                                            >
                                                {isChecking ? '检查中...' : '检查'}
                                            </Button>
                                        )}
                                        <Button
                                            variant="danger"
                                            style={{ padding: '6px 12px', fontSize: '0.85em' }}
                                            onClick={() => onDeleteAccount(accountIndex)}
                                        >
                                            删除
                                        </Button>
                                    </div>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
            
            {/* 分页控制 */}
            <div className="pagination">
                <div className="pagination-info">
                    显示 {startIndex + 1}-{endIndex} / 共 {filtered.length} 条
                </div>
                <div className="pagination-controls">
                    <Button
                        variant="secondary"
                        className="pagination-btn"
                        onClick={() => changePage(1)}
                        disabled={currentPage === 1}
                    >
                        首页
                    </Button>
                    <Button
                        variant="secondary"
                        className="pagination-btn"
                        onClick={() => changePage(currentPage - 1)}
                        disabled={currentPage === 1}
                    >
                        上一页
                    </Button>
                    <div className="pagination-current">
                        {currentPage} / {totalPages}
                    </div>
                    <Button
                        variant="secondary"
                        className="pagination-btn"
                        onClick={() => changePage(currentPage + 1)}
                        disabled={currentPage === totalPages}
                    >
                        下一页
                    </Button>
                    <Button
                        variant="secondary"
                        className="pagination-btn"
                        onClick={() => changePage(totalPages)}
                        disabled={currentPage === totalPages}
                    >
                        末页
                    </Button>
                    <select
                        value={pageSize}
                        onChange={(e) => changePageSize(parseInt(e.target.value))}
                        className="page-size-select"
                    >
                        <option value={10}>10条/页</option>
                        <option value={20}>20条/页</option>
                        <option value={50}>50条/页</option>
                        <option value={100}>100条/页</option>
                    </select>
                </div>
            </div>
        </>
    );
};

// ====== 主应用组件 ======
const App = () => {
    const [accounts, setAccounts] = useState([]);
    const [config, setConfig] = useState({});
    const [filter, setFilter] = useState('all');
    const [taskStatus, setTaskStatus] = useState({
        running: false,
        progress: 0,
        total: 0,
        logs: []
    });
    const [modalVisible, setModalVisible] = useState(false);
    const [modalContent, setModalContent] = useState({ title: '', body: '' });
    const [registerCount, setRegisterCount] = useState(1);
    const [concurrent, setConcurrent] = useState(1);
    const [proxyManagerVisible, setProxyManagerVisible] = useState(false);
    const [emailConfigVisible, setEmailConfigVisible] = useState(false);
    const [progressVisible, setProgressVisible] = useState(false);
    
    // 新增: 标签页状态
    const [activeTab, setActiveTab] = useState('auto'); // auto(自动注册+账号列表) / outlook(Outlook)
    const [outlookConfig, setOutlookConfig] = useState(''); // Outlook配置文本框内容
    
    // 新增: Outlook账号列表
    const [outlookAccounts, setOutlookAccounts] = useState([]);
    const [outlookAccountsFilter, setOutlookAccountsFilter] = useState('all');
    const [outlookAccountsView, setOutlookAccountsView] = useState('list'); // list或accounts
    
    // 加载配置
    const loadConfig = useCallback(async () => {
        try {
            const response = await fetch('/api/config');
            const result = await response.json();
            if (result.success) {
                setConfig(result.data);
                setRegisterCount(result.data.default_count);
                setConcurrent(result.data.default_concurrent);
            }
        } catch (error) {
            console.error('加载配置失败:', error);
        }
    }, []);
    
    // 加载账号列表
    const loadAccounts = useCallback(async () => {
        try {
            const response = await fetch('/api/accounts');
            const result = await response.json();
            if (result.success) {
                setAccounts(result.data);
            }
        } catch (error) {
            console.error('加载账号失败:', error);
        }
    }, []);
    
    // 加载Outlook账号列表
    const loadOutlookAccounts = useCallback(async () => {
        try {
            const response = await fetch('/api/accounts/outlook');
            const result = await response.json();
            if (result.success) {
                setOutlookAccounts(result.data || []);
            }
        } catch (error) {
            console.error('加载Outlook账号失败:', error);
        }
    }, []);
    
    // 开始注册
    const startRegister = useCallback(async () => {
        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ count: registerCount, concurrent })
            });
            const result = await response.json();
            if (result.success) {
                // 开始轮询任务状态
                pollTaskStatus();
            }
        } catch (error) {
            console.error('开始注册失败:', error);
        }
    }, [registerCount, concurrent]);
    
    // 新增: Outlook批量注册
    const startOutlookRegister = useCallback(async () => {
        if (!outlookConfig.trim()) {
            alert('请输入Outlook配置');
            return;
        }
        
        // 解析配置行
        const lines = outlookConfig.trim().split('\n')
            .map(line => line.trim())
            .filter(line => line && !line.startsWith('#'));
        
        if (lines.length === 0) {
            alert('没有有效的Outlook配置');
            return;
        }
        
        try {
            const response = await fetch('/api/register/outlook', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    outlook_lines: lines,
                    concurrent: 1  // Outlook建议单线程
                })
            });
            const result = await response.json();
            if (result.success) {
                pollTaskStatus();
            } else {
                alert('启动失败: ' + result.error);
            }
        } catch (error) {
            console.error('开始Outlook注册失败:', error);
            alert('请求失败: ' + error.message);
        }
    }, [outlookConfig]);
    
    // 轮询任务状态
    const pollTaskStatus = useCallback(() => {
        const interval = setInterval(async () => {
            try {
                const response = await fetch('/api/register/status');
                const result = await response.json();
                if (result.success) {
                    setTaskStatus(result.data);
                    // 显示进度窗口
                    if (result.data.running || result.data.logs.length > 0) {
                        setProgressVisible(true);
                    }
                    if (!result.data.running) {
                        clearInterval(interval);
                        loadAccounts();
                        loadOutlookAccounts();  // 同时刷新Outlook账号
                    }
                }
            } catch (error) {
                console.error('轮询任务状态失败:', error);
                clearInterval(interval);
            }
        }, 1000);
    }, [loadAccounts, loadOutlookAccounts]);
    
    // 检查所有账号
    const checkAccounts = useCallback(async () => {
        try {
            const response = await fetch('/api/check', { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                pollTaskStatus();
            }
        } catch (error) {
            console.error('检查账号失败:', error);
        }
    }, [pollTaskStatus]);
    
    // 检查所有Outlook账号
    const checkOutlookAccounts = useCallback(async () => {
        try {
            const response = await fetch('/api/check/outlook', { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                pollTaskStatus();
            }
        } catch (error) {
            console.error('检查Outlook账号失败:', error);
        }
    }, [pollTaskStatus]);
    
    // 检查单个账号
    const checkAccount = useCallback(async (index) => {
        try {
            const response = await fetch(`/api/accounts/${index}/check`, { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                loadAccounts();
            }
        } catch (error) {
            console.error('检查账号失败:', error);
        }
    }, [loadAccounts]);
    
    // 标记账号
    const markAccount = useCallback(async (index, used) => {
        try {
            const url = used ? `/api/accounts/${index}/mark` : `/api/accounts/${index}/unmark`;
            const response = await fetch(url, { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                loadAccounts();
            }
        } catch (error) {
            console.error('标记账号失败:', error);
        }
    }, [loadAccounts]);
    
    // 删除账号
    const deleteAccount = useCallback(async (index) => {
        if (!confirm('确定要删除这个账号吗?')) return;
        try {
            const response = await fetch(`/api/accounts/${index}`, { method: 'DELETE' });
            const result = await response.json();
            if (result.success) {
                loadAccounts();
            }
        } catch (error) {
            console.error('删除账号失败:', error);
        }
    }, [loadAccounts]);
    
    // ========== Outlook账号操作 ==========
    
    // 检查Outlook账号
    const checkOutlookAccount = useCallback(async (index) => {
        try {
            const response = await fetch(`/api/accounts/outlook/${index}/check`, { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                loadOutlookAccounts();
            }
        } catch (error) {
            console.error('检查Outlook账号失败:', error);
        }
    }, [loadOutlookAccounts]);
    
    // 标记Outlook账号
    const markOutlookAccount = useCallback(async (index, used) => {
        try {
            const url = used ? `/api/accounts/outlook/${index}/mark` : `/api/accounts/outlook/${index}/unmark`;
            const response = await fetch(url, { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                loadOutlookAccounts();
            }
        } catch (error) {
            console.error('标记Outlook账号失败:', error);
        }
    }, [loadOutlookAccounts]);
    
    // 删除Outlook账号
    const deleteOutlookAccount = useCallback(async (index) => {
        if (!confirm('确定要删除这个Outlook账号吗?')) return;
        try {
            const response = await fetch(`/api/accounts/outlook/${index}`, { method: 'DELETE' });
            const result = await response.json();
            if (result.success) {
                loadOutlookAccounts();
            }
        } catch (error) {
            console.error('删除Outlook账号失败:', error);
        }
    }, [loadOutlookAccounts]);
    
    // 删除失效账号
    const deleteExpiredAccounts = useCallback(async () => {
        const expiredCount = accounts.filter(a => a.health === 'expired').length;
        
        if (expiredCount === 0) {
            alert('没有失效的账号需要删除');
            return;
        }
        
        const message = `确定要删除所有失效的账号吗？共 ${expiredCount} 个\n\n失效账号是指健康状态为"失效"的账号`;
        
        if (!confirm(message)) return;
        
        try {
            const response = await fetch('/api/accounts/delete-expired', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            if (result.success) {
                alert(`成功删除 ${result.count} 个失效账号`);
                loadAccounts();
            } else {
                alert('删除失败: ' + result.error);
            }
        } catch (error) {
            console.error('删除失效账号失败:', error);
            alert('删除失败: ' + error.message);
        }
    }, [accounts, loadAccounts]);
    
    // 删除已使用账号
    const deleteUsedAccounts = useCallback(async () => {
        const usedCount = accounts.filter(a => a.used === true).length;
        
        if (usedCount === 0) {
            alert('没有已使用的账号需要删除');
            return;
        }
        
        const message = `确定要删除所有已使用的账号吗？共 ${usedCount} 个\n\n已使用账号是指状态为"已使用"的账号`;
        
        if (!confirm(message)) return;
        
        try {
            const response = await fetch('/api/accounts/delete-used', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            if (result.success) {
                alert(`成功删除 ${result.count} 个已使用账号`);
                loadAccounts();
            } else {
                alert('删除失败: ' + result.error);
            }
        } catch (error) {
            console.error('删除已使用账号失败:', error);
            alert('删除失败: ' + error.message);
        }
    }, [accounts, loadAccounts]);
    
    // 批量删除所有账号
    const deleteAllAccounts = useCallback(async () => {
        const count = accounts.length;
        
        if (count === 0) {
            alert('没有账号需要删除');
            return;
        }
        
        const message = `⚠️ 危险操作！\n\n确定要删除所有账号吗？共 ${count} 个\n\n此操作不可恢复！`;
        
        if (!confirm(message)) return;
        
        // 二次确认
        if (!confirm('再次确认：真的要删除所有账号吗？')) return;
        
        try {
            const response = await fetch('/api/accounts/delete-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            if (result.success) {
                alert(`成功删除 ${result.count} 个账号`);
                loadAccounts();
            } else {
                alert('删除失败: ' + result.error);
            }
        } catch (error) {
            console.error('批量删除账号失败:', error);
            alert('删除失败: ' + error.message);
        }
    }, [accounts, loadAccounts]);
    
    // 批量删除失效的Outlook账号
    const deleteExpiredOutlookAccounts = useCallback(async () => {
        const expiredCount = outlookAccounts.filter(a => a.health === 'expired').length;
        
        if (expiredCount === 0) {
            alert('没有失效的Outlook账号需要删除');
            return;
        }
        
        const message = `确定要删除所有失效的Outlook账号吗？共 ${expiredCount} 个\n\n失效账号是指健康状态为"失效"的账号`;
        
        if (!confirm(message)) return;
        
        try {
            const response = await fetch('/api/accounts/outlook/delete-expired', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            if (result.success) {
                alert(`成功删除 ${result.count} 个失效的Outlook账号`);
                loadOutlookAccounts();
            } else {
                alert('删除失败: ' + result.error);
            }
        } catch (error) {
            console.error('删除失效Outlook账号失败:', error);
            alert('删除失败: ' + error.message);
        }
    }, [outlookAccounts, loadOutlookAccounts]);
    
    // 导出Outlook账号（email、password、sessionKey）
    const exportOutlookAccounts = useCallback(async () => {
        try {
            const response = await fetch('/api/accounts/outlook/export');
            const result = await response.json();
            
            if (result.success) {
                // 生成JSON文件并下载
                const dataStr = JSON.stringify(result.data, null, 2);
                const blob = new Blob([dataStr], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `outlook_accounts_export_${new Date().getTime()}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                alert(`成功导出 ${result.count} 个账号`);
            } else {
                alert('导出失败: ' + result.error);
            }
        } catch (error) {
            console.error('导出Outlook账号失败:', error);
            alert('导出失败: ' + error.message);
        }
    }, []);
    
    // 批量删除所有Outlook账号
    const deleteAllOutlookAccounts = useCallback(async () => {
        const count = outlookAccounts.length;
        
        if (count === 0) {
            alert('没有Outlook账号需要删除');
            return;
        }
        
        const message = `⚠️ 危险操作！\n\n确定要删除所有Outlook账号吗？共 ${count} 个\n\n此操作不可恢复！`;
        
        if (!confirm(message)) return;
        
        // 二次确认
        if (!confirm('再次确认：真的要删除所有Outlook账号吗？')) return;
        
        try {
            const response = await fetch('/api/accounts/outlook/delete-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();
            if (result.success) {
                alert(`成功删除 ${result.count} 个Outlook账号`);
                loadOutlookAccounts();
            } else {
                alert('删除失败: ' + result.error);
            }
        } catch (error) {
            console.error('批量删除Outlook账号失败:', error);
            alert('删除失败: ' + error.message);
        }
    }, [outlookAccounts, loadOutlookAccounts]);
    
    // 显示详情
    const showDetails = useCallback((title, content) => {
        let displayContent = content;
        
        // 如果是SessionKey,添加前缀
        if (title === 'SessionKey' && typeof content === 'string') {
            displayContent = 'sessionKey=' + content;
        } else if (typeof content === 'object') {
            displayContent = JSON.stringify(content, null, 2);
        }
        
        setModalContent({
            title,
            body: displayContent
        });
        setModalVisible(true);
    }, []);
    
    // 页面加载时初始化
    useEffect(() => {
        loadConfig();
        loadAccounts();
        loadOutlookAccounts();  // 同时加载Outlook账号
    }, [loadConfig, loadAccounts, loadOutlookAccounts]);
    
    // 统计数据
    const stats = useMemo(() => {
        const total = accounts.length;
        const used = accounts.filter(a => a.used).length;
        const available = total - used;
        return { total, used, available };
    }, [accounts]);
    
    return (
        <div className="container">
            {/* 头部 */}
            <header className="header">
                <h1 className="title">🦅 ClaudeX 管理面板</h1>
                <div className="stats-row">
                    <div className="text-green" style={{ fontSize: '1.2em' }}>
                        <strong>{stats.total}</strong> 个账号
                        <span className="text-gray" style={{ marginLeft: '10px' }}>
                            未使用 <strong className="text-green">{stats.available}</strong>
                        </span>
                        <span className="text-gray" style={{ marginLeft: '10px' }}>
                            已用 <strong className="text-gray">{stats.used}</strong>
                        </span>
                    </div>
                    <div className="text-gray" style={{ fontSize: '0.9em' }}>
                        代理: <strong className="text-green">{config.proxy_count || 0}</strong> 个
                    </div>
                </div>
            </header>
            
            {/* 控制面板 */}
            <div className="controls">
                {/* 标签导航 */}
                <div className="tab-navigation" style={{ 
                    display: 'flex', 
                    gap: '10px', 
                    marginBottom: '15px',
                    borderBottom: '2px solid #2d3748'
                }}>
                    <button
                        onClick={() => setActiveTab('auto')}
                        style={{
                            padding: '10px 20px',
                            border: 'none',
                            background: activeTab === 'auto' ? '#38a169' : 'transparent',
                            color: activeTab === 'auto' ? '#fff' : '#a0aec0',
                            cursor: 'pointer',
                            fontSize: '14px',
                            fontWeight: 'bold',
                            borderBottom: activeTab === 'auto' ? '3px solid #38a169' : 'none',
                            transition: 'all 0.3s'
                        }}
                    >
                        🤖 自动注册
                    </button>
                    <button
                        onClick={() => setActiveTab('outlook')}
                        style={{
                            padding: '10px 20px',
                            border: 'none',
                            background: activeTab === 'outlook' ? '#38a169' : 'transparent',
                            color: activeTab === 'outlook' ? '#fff' : '#a0aec0',
                            cursor: 'pointer',
                            fontSize: '14px',
                            fontWeight: 'bold',
                            borderBottom: activeTab === 'outlook' ? '3px solid #38a169' : 'none',
                            transition: 'all 0.3s'
                        }}
                    >
                        📧 Outlook
                    </button>
                </div>
                
                {/* 自动注册面板 */}
                {activeTab === 'auto' && (
                    <>
                        <div className="controls-row">
                            <div className="flex flex-center gap-10">
                                <label className="text-gray">注册数量</label>
                                <input
                                    type="number"
                                    className="input"
                                    value={registerCount}
                                    onChange={(e) => setRegisterCount(parseInt(e.target.value))}
                                    min="1"
                                    max="100"
                                    style={{ width: '80px' }}
                                />
                            </div>
                            <div className="flex flex-center gap-10">
                                <label className="text-gray">并发</label>
                                <input
                                    type="number"
                                    className="input"
                                    value={concurrent}
                                    onChange={(e) => setConcurrent(parseInt(e.target.value))}
                                    min="1"
                                    max="20"
                                    style={{ width: '60px' }}
                                />
                            </div>
                            <Button variant="primary" onClick={startRegister} disabled={taskStatus.running}>
                                开始注册
                            </Button>
                            <Button variant="secondary" onClick={checkAccounts} disabled={taskStatus.running}>
                                检查状态
                            </Button>
                            <Button variant="secondary" onClick={() => setEmailConfigVisible(true)}>
                                📧 邮箱配置
                            </Button>
                            <Button variant="secondary" onClick={() => setProxyManagerVisible(true)} className="ml-auto">
                                🔧 代理管理
                            </Button>
                        </div>
                    </>
                )}
                
            </div>
            
            {/* 悬浮进度窗口 */}
            <ProgressBar
                progress={taskStatus.progress}
                total={taskStatus.total}
                logs={taskStatus.logs}
                visible={progressVisible}
                onClose={() => setProgressVisible(false)}
            />
            
            {/* 账号列表页面 */}
            {activeTab === 'auto' && (
                <div className="accounts-container" style={{ marginTop: '30px' }}>
                    <div className="accounts-header">
                        <h2 className="text-green">📋 账号列表</h2>
                        <div className="filter-buttons">
                            {['all', 'available', 'used'].map(f => (
                                <button
                                    key={f}
                                    className={`filter-btn ${filter === f ? 'active' : ''}`}
                                    onClick={() => setFilter(f)}
                                >
                                    {f === 'all' ? '全部' : f === 'available' ? '未使用' : '已使用'}
                                </button>
                            ))}
                            <Button 
                                variant="danger" 
                                onClick={deleteExpiredAccounts}
                                style={{ marginLeft: '20px' }}
                            >
                                🗑️ 删除失效
                            </Button>
                            <Button 
                                variant="danger" 
                                onClick={deleteUsedAccounts}
                                style={{ marginLeft: '10px' }}
                            >
                                🗑️ 删除已使用
                            </Button>
                            <Button 
                                variant="danger" 
                                onClick={deleteAllAccounts}
                                style={{ marginLeft: '10px', backgroundColor: '#dc143c' }}
                            >
                                ⚠️ 批量删除
                            </Button>
                        </div>
                    </div>
                    <AccountsTable
                        accounts={accounts}
                        filter={filter}
                        onCheckAccount={checkAccount}
                        onMarkAccount={markAccount}
                        onDeleteAccount={deleteAccount}
                        onShowDetails={showDetails}
                    />
                </div>
            )}
            
            {/* Outlook页面(注册+账号列表) */}
            {activeTab === 'outlook' && (
                <div>
                    {/* Outlook注册面板 */}
                    <div className="controls" style={{ marginBottom: '30px' }}>
                        <h2 className="text-green" style={{ marginBottom: '15px' }}>📧 Outlook 注册</h2>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                            <textarea
                                className="input"
                                value={outlookConfig}
                                onChange={(e) => setOutlookConfig(e.target.value)}
                                placeholder="# 推荐: 完整格式(智能选择)&#10;test@hotmail.com----password123----client-id----refresh-token&#10;&#10;# 简化: 仅IMAP&#10;simple@outlook.com----mypassword"
                                rows="8"
                                style={{
                                    width: '100%',
                                    fontFamily: 'monospace',
                                    fontSize: '12px',
                                    resize: 'vertical'
                                }}
                            />
                            <div className="controls-row">
                                <Button 
                                    variant="primary" 
                                    onClick={startOutlookRegister} 
                                    disabled={taskStatus.running || !outlookConfig.trim()}
                                >
                                    开始Outlook注册
                                </Button>
                                <div className="text-gray" style={{ fontSize: '0.85em', marginLeft: '10px' }}>
                                    将注册 {outlookConfig.trim().split('\n').filter(l => l.trim() && !l.startsWith('#')).length} 个账号
                                </div>
                                <Button variant="secondary" onClick={() => setProxyManagerVisible(true)} style={{ marginLeft: 'auto' }}>
                                    🔧 代理管理
                                </Button>
                            </div>
                        </div>
                    </div>
                    
                    {/* Outlook账号列表 */}
                    <div className="accounts-container">
                        <div className="accounts-header">
                            <h2 className="text-green">📧 Outlook 账号列表</h2>
                            <div className="filter-buttons">
                                <Button 
                                    variant="secondary" 
                                    onClick={checkOutlookAccounts}
                                    disabled={taskStatus.running}
                                >
                                    🔍 批量检查
                                </Button>
                                <Button 
                                    variant="danger" 
                                    onClick={deleteExpiredOutlookAccounts}
                                    style={{ marginLeft: '10px' }}
                                >
                                    🗑️ 删除失效
                                </Button>
                                <Button 
                                    variant="primary" 
                                    onClick={exportOutlookAccounts}
                                    style={{ marginLeft: '10px' }}
                                >
                                    📥 导出账号
                                </Button>
                                <Button 
                                    variant="danger" 
                                    onClick={deleteAllOutlookAccounts}
                                    style={{ marginLeft: '10px', backgroundColor: '#dc143c' }}
                                >
                                    ⚠️ 批量删除
                                </Button>
                            </div>
                        </div>
                        <AccountsTable
                            accounts={outlookAccounts}
                            filter="all"
                            onCheckAccount={checkOutlookAccount}
                            onMarkAccount={markOutlookAccount}
                            onDeleteAccount={deleteOutlookAccount}
                            onShowDetails={showDetails}
                            accountType="outlook"
                        />
                    </div>
                </div>
            )}
            
            {/* 模态框 */}
            <Modal
                visible={modalVisible}
                title={modalContent.title}
                onClose={() => setModalVisible(false)}
                onAction={() => {
                    navigator.clipboard.writeText(modalContent.body);
                }}
                actionText="复制"
            >
                <pre className="code-block">
                    {modalContent.body}
                </pre>
            </Modal>
            
            {/* 代理管理 */}
            <ProxyManager
                visible={proxyManagerVisible}
                onClose={() => setProxyManagerVisible(false)}
                onRefresh={loadConfig}
            />
            
            {/* 邮箱配置 */}
            <EmailConfig
                visible={emailConfigVisible}
                onClose={() => setEmailConfigVisible(false)}
                config={config}
                onRefresh={loadConfig}
            />
        </div>
    );
};

// 渲染到DOM
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
