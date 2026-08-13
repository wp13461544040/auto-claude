// ====== UI基础组件 ======
const { useState } = React;

// Button组件
const Button = ({ children, variant = 'secondary', disabled, onClick, style, className = '' }) => {
    const variantClass = variant === 'primary' ? 'btn-primary' : 
                        variant === 'danger' ? 'btn-danger' : 'btn-secondary';
    
    return (
        <button
            className={`btn ${variantClass} ${className}`}
            style={style}
            onClick={onClick}
            disabled={disabled}
        >
            {children}
        </button>
    );
};

// Modal组件
const Modal = ({ visible, title, children, onClose, onAction, actionText = '确定' }) => {
    const [copySuccess, setCopySuccess] = useState(false);
    
    if (!visible) return null;
    
    const handleCopy = () => {
        if (onAction) {
            onAction();
            setCopySuccess(true);
            setTimeout(() => setCopySuccess(false), 1000);
        }
    };
    
    return (
        <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
            <div className="modal-content">
                <div className="modal-header">
                    <h3 className="modal-title">{title}</h3>
                    <button className="modal-close" onClick={onClose}>×</button>
                </div>
                <div className="modal-body">{children}</div>
                {onAction && (
                    <div className="modal-footer">
                        <button
                            className={`btn btn-primary ${copySuccess ? 'btn-success' : ''}`}
                            onClick={handleCopy}
                        >
                            {copySuccess ? '✓ 已复制' : actionText}
                        </button>
                        <Button variant="secondary" onClick={onClose}>
                            取消
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
};


// 导出到全局
window.UIComponents = {
    Button,
    Modal
};
