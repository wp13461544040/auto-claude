const { useState, useEffect, useCallback } = React;
const { Button, Modal } = window.UIComponents;

// ====== 代理管理组件 ======
const ProxyManager = ({ visible, onClose, onRefresh }) => {
    const [proxies, setProxies] = useState([]);
    const [proxyInput, setProxyInput] = useState('');
    const [testing, setTesting] = useState(false);
    
    // 加载代理列表
    const loadProxies = useCallback(async () => {
        try {
            const response = await fetch('/api/proxies');
            const result = await response.json();
            if (result.success) {
                setProxies(result.data);
            }
        } catch (error) {
            console.error('加载代理失败:', error);
        }
    }, []);
    
    // 上传代理
    const uploadProxies = useCallback(async () => {
        const lines = proxyInput.trim().split('\n').filter(line => line.trim());
        if (lines.length === 0) {
            alert('请输入代理地址');
            return;
        }
        
        try {
            const response = await fetch('/api/proxies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ proxies: lines })
            });
            const result = await response.json();
            if (result.success) {
                alert(`已上传 ${result.count} 个代理`);
                setProxyInput('');
                loadProxies();
                onRefresh && onRefresh();
            }
        } catch (error) {
            console.error('上传代理失败:', error);
        }
    }, [proxyInput, loadProxies, onRefresh]);
    
    // 切换代理状态
    const toggleProxy = useCallback(async (proxy, enable) => {
        try {
            const response = await fetch('/api/proxies/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ proxy, enable })
            });
            const result = await response.json();
            if (result.success) {
                loadProxies();
                onRefresh && onRefresh();
            }
        } catch (error) {
            console.error('切换代理失败:', error);
        }
    }, [loadProxies, onRefresh]);
    
    // 测试所有代理
    const testAllProxies = useCallback(async () => {
        setTesting(true);
        try {
            const response = await fetch('/api/proxies/check', { method: 'POST' });
            const result = await response.json();
            if (result.success) {
                // 更新代理列表,添加测试结果
                setProxies(prevProxies => {
                    return prevProxies.map(p => {
                        const testResult = result.data.find(r => r.proxy === p.proxy);
                        return testResult ? { ...p, ...testResult } : p;
                    });
                });
            }
        } catch (error) {
            console.error('测试代理失败:', error);
        } finally {
            setTesting(false);
        }
    }, []);
    
    // 删除代理
    const deleteProxy = useCallback(async (proxy) => {
        if (!confirm(`确定要删除代理 ${proxy} 吗?`)) return;
        try {
            const response = await fetch('/api/proxies/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ proxy })
            });
            const result = await response.json();
            if (result.success) {
                loadProxies();
                onRefresh && onRefresh();
            } else {
                alert('删除失败: ' + result.error);
            }
        } catch (error) {
            console.error('删除代理失败:', error);
            alert('删除失败: ' + error.message);
        }
    }, [loadProxies, onRefresh]);
    
    useEffect(() => {
        if (visible) {
            loadProxies();
        }
    }, [visible, loadProxies]);
    
    if (!visible) return null;
    
    const enabledCount = proxies.filter(p => p.enabled).length;
    
    return (
        <Modal visible={visible} title="🔧 代理管理" onClose={onClose}>
            <div className="proxy-manager">
                <div className="proxy-input-section">
                    <textarea
                        value={proxyInput}
                        onChange={(e) => setProxyInput(e.target.value)}
                        placeholder="每行一个代理&#10;格式: socks5h://user:pass@host:port"
                        className="proxy-textarea"
                    />
                </div>
                <div className="proxy-controls">
                    <Button variant="primary" onClick={uploadProxies} style={{ padding: '6px 12px', fontSize: '0.85em' }}>
                        上传代理
                    </Button>
                    <Button variant="secondary" onClick={loadProxies} style={{ padding: '6px 12px', fontSize: '0.85em' }}>
                        刷新列表
                    </Button>
                    <Button
                        variant="secondary"
                        onClick={testAllProxies}
                        disabled={testing}
                        style={{ padding: '6px 12px', fontSize: '0.85em' }}
                    >
                        {testing ? '测试中...' : '测试代理'}
                    </Button>
                    <span className="proxy-count">
                        当前启用: <strong className="text-green">{enabledCount}</strong> 个
                    </span>
                </div>
            </div>
            <div className="proxy-list">
                {proxies.length === 0 ? (
                    <p className="text-center text-gray">暂无代理</p>
                ) : (
                    <table className="table">
                        <thead>
                            <tr>
                                <th className="table-header" style={{ width: '60px' }}>状态</th>
                                <th className="table-header">代理地址</th>
                                <th className="table-header" style={{ width: '100px' }}>可用性</th>
                                <th className="table-header" style={{ width: '120px' }}>IP</th>
                                <th className="table-header" style={{ width: '100px' }}>位置</th>
                                <th className="table-header" style={{ width: '100px' }}>类型</th>
                                <th className="table-header" style={{ width: '80px' }}>延迟</th>
                                <th className="table-header" style={{ width: '100px' }}>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {proxies.map((proxy, idx) => (
                                <tr key={idx}>
                                    <td className="table-cell">
                                        <span className={`status-dot ${proxy.enabled ? 'active' : ''}`} />
                                    </td>
                                    <td className="table-cell">
                                        <span 
                                            className="proxy-address" 
                                            title={proxy.proxy}
                                        >
                                            {proxy.proxy.length > 40 ? proxy.proxy.slice(0, 40) + '...' : proxy.proxy}
                                        </span>
                                    </td>
                                    <td className="table-cell">
                                        {proxy.available !== undefined ? (
                                            <span className={`badge ${proxy.available ? 'badge-available' : 'badge-used'}`}>
                                                {proxy.available ? '✓ 可用' : '✗ 不可用'}
                                            </span>
                                        ) : '-'}
                                    </td>
                                    <td className="table-cell text-sm">{proxy.ip || '-'}</td>
                                    <td className="table-cell text-sm">
                                        {proxy.country && proxy.city ? `${proxy.country} ${proxy.city}` : '-'}
                                    </td>
                                    <td className="table-cell text-sm">{proxy.type || '-'}</td>
                                    <td className="table-cell text-sm">
                                        {proxy.latency ? `${proxy.latency}ms` : '-'}
                                    </td>
                                    <td className="table-cell">
                                        <div className="action-buttons">
                                            <Button
                                                variant="secondary"
                                                onClick={() => toggleProxy(proxy.proxy, !proxy.enabled)}
                                                style={{ padding: '4px 8px', fontSize: '0.8em' }}
                                            >
                                                {proxy.enabled ? '禁用' : '启用'}
                                            </Button>
                                            <Button
                                                variant="danger"
                                                onClick={() => deleteProxy(proxy.proxy)}
                                                style={{ padding: '4px 8px', fontSize: '0.8em' }}
                                            >
                                                删除
                                            </Button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </Modal>
    );
};

// ====== 邮箱配置组件 ======
const EmailConfig = ({ visible, onClose, config, onRefresh }) => {
    const [service, setService] = useState('moemail');
    const [moEmailApiKey, setMoEmailApiKey] = useState('');
    const [moEmailBaseUrl, setMoEmailBaseUrl] = useState('');
    const [remailApiKey, setRemailApiKey] = useState('');
    const [remailApiUrl, setRemailApiUrl] = useState('https://remail.aishop6.com');
    const [remailProjectId, setRemailProjectId] = useState('');
    const [remailProductId, setRemailProductId] = useState('');
    const [remailMode, setRemailMode] = useState('package');
    const [remailSuffix, setRemailSuffix] = useState('');
    const [remailProjects, setRemailProjects] = useState([]);
    const [remailProducts, setRemailProducts] = useState([]);
    const [loadingProjects, setLoadingProjects] = useState(false);
    const [testResult, setTestResult] = useState('');
    
    // 加载配置(使用完整的API Key,不再截断)
    useEffect(() => {
        if (visible && config) {
            setService(config.email_service || 'moemail');
            if (config.moemail) {
                // 使用完整的API Key(后端已经不截断了)
                setMoEmailApiKey(config.moemail.api_key || '');
                setMoEmailBaseUrl(config.moemail.base_url || '');
            }
            if (config.remail) {
                // 使用完整的API Key
                setRemailApiKey(config.remail.api_key || '');
                setRemailApiUrl(config.remail.api_url || 'https://remail.aishop6.com');
                setRemailProjectId(config.remail.project_id || '');
                setRemailProductId(config.remail.product_id || '');
                setRemailMode(config.remail.mode || 'package');
                setRemailSuffix(config.remail.suffix || '');
            }
        }
    }, [visible, config]);
    
    // 加载Remail项目
    const loadRemailProjects = useCallback(async () => {
        if (!remailApiKey) {
            alert('请先输入API Key');
            return;
        }
        
        setLoadingProjects(true);
        try {
            const response = await fetch('/api/remail/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: remailApiKey,
                    api_url: remailApiUrl
                })
            });
            const result = await response.json();
            if (result.success) {
                setRemailProjects(result.data.projects);
                alert(`成功加载 ${result.data.projects.length} 个项目`);
            } else {
                alert('加载项目失败: ' + result.error);
            }
        } catch (error) {
            alert('加载项目失败: ' + error.message);
        } finally {
            setLoadingProjects(false);
        }
    }, [remailApiKey, remailApiUrl]);
    
    // 当选择项目时,加载产品列表
    const handleProjectChange = useCallback((projectId) => {
        setRemailProjectId(projectId);
        const project = remailProjects.find(p => p.id == projectId);
        if (project) {
            setRemailProducts(project.products || []);
        } else {
            setRemailProducts([]);
        }
        setRemailProductId('');
    }, [remailProjects]);
    
    // 测试Remail连接
    const testRemail = useCallback(async () => {
        if (!remailApiKey || !remailProjectId || !remailProductId) {
            alert('请填写完整的Remail配置');
            return;
        }
        
        setTestResult('测试中...');
        try {
            const response = await fetch('/api/remail/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: remailApiKey,
                    api_url: remailApiUrl,
                    project_id: parseInt(remailProjectId),
                    product_id: parseInt(remailProductId),
                    mode: remailMode,
                    suffix: remailSuffix
                })
            });
            const result = await response.json();
            if (result.success) {
                setTestResult(`✓ ${result.message} (${result.data.email})`);
            } else {
                setTestResult(`✗ ${result.error}`);
            }
        } catch (error) {
            setTestResult(`✗ ${error.message}`);
        }
    }, [remailApiKey, remailApiUrl, remailProjectId, remailProductId, remailMode, remailSuffix]);
    
    // 保存配置
    const saveConfig = useCallback(async () => {
        try {
            const configData = service === 'moemail' ? {
                api_key: moEmailApiKey,
                base_url: moEmailBaseUrl
            } : {
                api_key: remailApiKey,
                api_url: remailApiUrl,
                project_id: parseInt(remailProjectId),
                product_id: parseInt(remailProductId),
                mode: remailMode,
                suffix: remailSuffix
            };
            
            const response = await fetch('/api/email-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    service,
                    config: configData
                })
            });
            const result = await response.json();
            if (result.success) {
                alert(result.message);
                onRefresh && onRefresh();
                onClose();
            } else {
                alert('保存失败: ' + result.error);
            }
        } catch (error) {
            alert('保存失败: ' + error.message);
        }
    }, [service, moEmailApiKey, moEmailBaseUrl, remailApiKey, remailApiUrl, remailProjectId, remailProductId, remailMode, remailSuffix, onRefresh, onClose]);
    
    if (!visible) return null;
    
    return (
        <Modal visible={visible} title="📧 邮箱服务配置" onClose={onClose}>
            {/* 服务选择 */}
            <div className="email-service-selector">
                <label className="form-label">当前邮箱服务</label>
                <div className="service-buttons">
                    <button
                        className={`service-btn ${service === 'moemail' ? 'active' : ''}`}
                        onClick={() => {
                            console.log('切换到 Moemail');
                            setService('moemail');
                        }}
                    >
                        Moemail
                    </button>
                    <button
                        className={`service-btn ${service === 'remail' ? 'active' : ''}`}
                        onClick={() => {
                            console.log('切换到 Remail');
                            setService('remail');
                        }}
                    >
                        Remail
                    </button>
                    <span className="service-current">
                        当前: <strong className="text-green">{config?.email_service || 'moemail'}</strong>
                    </span>
                </div>
            </div>
            
            {/* Moemail配置 */}
            {service === 'moemail' && (
                <div className="config-section">
                    <h4 className="config-title">Moemail 配置</h4>
                    <div className="form-group">
                        <label className="form-label-sm">API Key</label>
                        <input
                            type="text"
                            value={moEmailApiKey}
                            onChange={(e) => setMoEmailApiKey(e.target.value)}
                            placeholder="mk_your_api_key_here"
                            className="input"
                        />
                    </div>
                    <div className="form-group">
                        <label className="form-label-sm">Base URL</label>
                        <input
                            type="text"
                            value={moEmailBaseUrl}
                            onChange={(e) => setMoEmailBaseUrl(e.target.value)}
                            placeholder="https://your-moemail-instance.example.com"
                            className="input"
                        />
                    </div>
                    <div className="config-hint">
                        ℹ️ Moemail 是默认邮箱服务,配置后可直接使用
                    </div>
                </div>
            )}
            
            {/* Remail配置 */}
            {service === 'remail' && (
                <div className="config-section">
                    <h4 className="config-title">Remail 配置</h4>
                    <div className="form-group">
                        <label className="form-label-sm">
                            API Key <span className="text-danger">*</span>
                        </label>
                        <div className="input-group">
                            <input
                                type="text"
                                value={remailApiKey}
                                onChange={(e) => setRemailApiKey(e.target.value)}
                                placeholder="your_remail_api_key_here"
                                className="input flex-1"
                            />
                            <Button
                                variant="secondary"
                                onClick={loadRemailProjects}
                                disabled={loadingProjects}
                                style={{ padding: '6px 12px', fontSize: '0.85em' }}
                            >
                                {loadingProjects ? '加载中...' : '加载项目'}
                            </Button>
                        </div>
                    </div>
                    <div className="form-group">
                        <label className="form-label-sm">API URL</label>
                        <input
                            type="text"
                            value={remailApiUrl}
                            onChange={(e) => setRemailApiUrl(e.target.value)}
                            className="input"
                        />
                    </div>
                    <div className="form-row">
                        <div className="form-group flex-1">
                            <label className="form-label-sm">
                                项目 <span className="text-danger">*</span>
                            </label>
                            <select
                                value={remailProjectId}
                                onChange={(e) => handleProjectChange(e.target.value)}
                                className="input"
                            >
                                <option value="">-- 请先加载项目 --</option>
                                {remailProjects.map(p => (
                                    <option key={p.id} value={p.id}>
                                        {p.name} (ID: {p.id})
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="form-group flex-1">
                            <label className="form-label-sm">
                                产品 <span className="text-danger">*</span>
                            </label>
                            <select
                                value={remailProductId}
                                onChange={(e) => setRemailProductId(e.target.value)}
                                className="input"
                            >
                                <option value="">-- 请先选择项目 --</option>
                                {remailProducts.map(p => (
                                    <option key={p.id} value={p.id}>
                                        {p.name} (ID: {p.id})
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <div className="form-row">
                        <div className="form-group flex-1">
                            <label className="form-label-sm">服务模式</label>
                            <select
                                value={remailMode}
                                onChange={(e) => setRemailMode(e.target.value)}
                                className="input"
                            >
                                <option value="package">接包模式 (package)</option>
                                <option value="purchase">购买模式 (purchase)</option>
                            </select>
                        </div>
                        <div className="form-group flex-1">
                            <label className="form-label-sm">邮箱后缀(可选)</label>
                            <input
                                type="text"
                                value={remailSuffix}
                                onChange={(e) => setRemailSuffix(e.target.value)}
                                placeholder="com.cn"
                                className="input"
                            />
                        </div>
                    </div>
                    <div className="test-section">
                        <Button variant="secondary" onClick={testRemail} style={{ padding: '6px 12px', fontSize: '0.85em' }}>
                            测试连接
                        </Button>
                        <span className="test-result">{testResult}</span>
                    </div>
                </div>
            )}
            
            {/* 底部按钮 */}
            <div className="modal-actions">
                <Button variant="primary" onClick={saveConfig}>
                    保存配置
                </Button>
                <Button variant="secondary" onClick={onClose}>
                    取消
                </Button>
            </div>
        </Modal>
    );
};


// 导出到全局
window.ProxyManager = ProxyManager;
window.EmailConfig = EmailConfig;
