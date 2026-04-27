import { useState, useEffect } from 'react';
import axios from 'axios';

const API = 'http://127.0.0.1:8000/api/v1';

function App() {
  const [merchantId, setMerchantId] = useState(1);
  const [balance, setBalance] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [amount, setAmount] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    try {
      const [bal, pays] = await Promise.all([
        axios.get(`${API}/merchants/${merchantId}/balance/`),
        axios.get(`${API}/merchants/${merchantId}/payouts/`),
      ]);
      setBalance(bal.data);
      setPayouts(pays.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [merchantId]);

  const requestPayout = async () => {
    if (!amount) {
      setMessage('Please enter an amount');
      return;
    }
    setLoading(true);
    const idempotencyKey = crypto.randomUUID();
    try {
      const bankRes = await axios.get(`${API}/merchants/${merchantId}/balance/`);
      const response = await axios.post(
        `${API}/payouts/`,
        {
          amount_paise: parseInt(amount),
          merchant_id: merchantId,
          bank_account_id: 1,
        },
        {
          headers: { 'Idempotency-Key': idempotencyKey },
        }
      );
      setMessage(`✅ Payout created! ID: ${response.data.id}`);
      setAmount('');
      fetchData();
    } catch (err) {
      setMessage(`❌ Error: ${err.response?.data?.error || 'Something went wrong'}`);
    }
    setLoading(false);
  };

  const formatPaise = (paise) => {
    if (paise === null || paise === undefined) return '₹0.00';
    return `₹${(paise / 100).toFixed(2)}`;
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return '#22c55e';
      case 'failed': return '#ef4444';
      case 'processing': return '#f59e0b';
      default: return '#6366f1';
    }
  };

  return (
    <div style={{ fontFamily: 'Arial, sans-serif', maxWidth: '900px', margin: '0 auto', padding: '20px' }}>
      
      {/* Header */}
      <div style={{ background: '#1e293b', color: 'white', padding: '20px', borderRadius: '10px', marginBottom: '20px' }}>
        <h1 style={{ margin: 0 }}>🏦 Playto Payout Engine</h1>
        <p style={{ margin: '5px 0 0', color: '#94a3b8' }}>Merchant Dashboard</p>
      </div>

      {/* Merchant Selector */}
      <div style={{ marginBottom: '20px' }}>
        <label style={{ fontWeight: 'bold', marginRight: '10px' }}>Select Merchant:</label>
        <select
          value={merchantId}
          onChange={(e) => setMerchantId(Number(e.target.value))}
          style={{ padding: '8px', borderRadius: '5px', border: '1px solid #ccc' }}
        >
          <option value={1}>Merchant 1 - Rahul Designs</option>
          <option value={2}>Merchant 2 - Priya Consulting</option>
        </select>
      </div>

      {/* Balance Cards */}
      {balance && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '15px', marginBottom: '20px' }}>
          <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '10px', padding: '20px' }}>
            <p style={{ margin: 0, color: '#166534', fontSize: '13px', fontWeight: 'bold' }}>AVAILABLE BALANCE</p>
            <p style={{ margin: '5px 0 0', fontSize: '24px', fontWeight: 'bold', color: '#15803d' }}>
              {formatPaise(balance.available_balance_paise)}
            </p>
          </div>
          <div style={{ background: '#fff7ed', border: '1px solid #fdba74', borderRadius: '10px', padding: '20px' }}>
            <p style={{ margin: 0, color: '#9a3412', fontSize: '13px', fontWeight: 'bold' }}>HELD BALANCE</p>
            <p style={{ margin: '5px 0 0', fontSize: '24px', fontWeight: 'bold', color: '#c2410c' }}>
              {formatPaise(balance.held_balance_paise)}
            </p>
          </div>
          <div style={{ background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '10px', padding: '20px' }}>
            <p style={{ margin: 0, color: '#1e40af', fontSize: '13px', fontWeight: 'bold' }}>TOTAL BALANCE</p>
            <p style={{ margin: '5px 0 0', fontSize: '24px', fontWeight: 'bold', color: '#1d4ed8' }}>
              {formatPaise(balance.total_balance_paise)}
            </p>
          </div>
        </div>
      )}

      {/* Payout Request Form */}
      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '20px', marginBottom: '20px' }}>
        <h2 style={{ margin: '0 0 15px' }}>Request Payout</h2>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <input
            type="number"
            placeholder="Amount in paise (e.g. 10000 = ₹100)"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            style={{ flex: 1, padding: '10px', borderRadius: '5px', border: '1px solid #ccc', fontSize: '14px' }}
          />
          <button
            onClick={requestPayout}
            disabled={loading}
            style={{
              background: loading ? '#94a3b8' : '#6366f1',
              color: 'white',
              border: 'none',
              padding: '10px 20px',
              borderRadius: '5px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: 'bold'
            }}
          >
            {loading ? 'Processing...' : 'Request Payout'}
          </button>
        </div>
        {message && (
          <p style={{ margin: '10px 0 0', padding: '10px', background: '#f8fafc', borderRadius: '5px', fontSize: '14px' }}>
            {message}
          </p>
        )}
      </div>

      {/* Payout History Table */}
      <div style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '20px' }}>
        <h2 style={{ margin: '0 0 15px' }}>Payout History</h2>
        {payouts.length === 0 ? (
          <p style={{ color: '#94a3b8' }}>No payouts yet. Request your first payout above!</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f8fafc' }}>
                <th style={{ padding: '10px', textAlign: 'left', fontSize: '13px', color: '#64748b' }}>ID</th>
                <th style={{ padding: '10px', textAlign: 'left', fontSize: '13px', color: '#64748b' }}>AMOUNT</th>
                <th style={{ padding: '10px', textAlign: 'left', fontSize: '13px', color: '#64748b' }}>STATUS</th>
                <th style={{ padding: '10px', textAlign: 'left', fontSize: '13px', color: '#64748b' }}>DATE</th>
              </tr>
            </thead>
            <tbody>
              {payouts.map((payout) => (
                <tr key={payout.id} style={{ borderTop: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '10px', fontSize: '12px', color: '#94a3b8' }}>
                    {payout.id.substring(0, 8)}...
                  </td>
                  <td style={{ padding: '10px', fontWeight: 'bold' }}>
                    {formatPaise(payout.amount_paise)}
                  </td>
                  <td style={{ padding: '10px' }}>
                    <span style={{
                      background: getStatusColor(payout.status) + '20',
                      color: getStatusColor(payout.status),
                      padding: '3px 10px',
                      borderRadius: '20px',
                      fontSize: '12px',
                      fontWeight: 'bold'
                    }}>
                      {payout.status.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px', fontSize: '13px', color: '#64748b' }}>
                    {new Date(payout.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p style={{ margin: '10px 0 0', fontSize: '12px', color: '#94a3b8' }}>
          🔄 Auto-refreshes every 5 seconds
        </p>
      </div>
    </div>
  );
}

export default App;