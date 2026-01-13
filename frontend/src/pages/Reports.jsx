import React, { useState, useEffect } from 'react';
import './Reports.css';

const API_BASE = import.meta.env.VITE_API_URL || 'https://store-feedback.tarsyer.com';

// Simple bar chart component
const BarChart = ({ data, labelKey, valueKey, maxBars = 10, color = '#EF4444' }) => {
  const maxValue = Math.max(...data.map(d => d[valueKey]), 1);

  return (
    <div className="bar-chart">
      {data.slice(0, maxBars).map((item, i) => (
        <div key={i} className="bar-row">
          <span className="bar-label">{item[labelKey]}</span>
          <div className="bar-container">
            <div
              className="bar-fill"
              style={{
                width: `${(item[valueKey] / maxValue) * 100}%`,
                backgroundColor: color
              }}
            />
          </div>
          <span className="bar-value">{item[valueKey]}</span>
        </div>
      ))}
    </div>
  );
};

// Tone distribution chart
const ToneChart = ({ data }) => {
  const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
  const colors = {
    positive: '#34a853',
    neutral: '#fbbc04',
    negative: '#ea4335'
  };

  return (
    <div className="tone-chart">
      <div className="tone-bars">
        {Object.entries(data).map(([tone, count]) => {
          const percent = (count / total) * 100;
          return (
            <div key={tone} className="tone-bar-row">
              <div className="tone-label-row">
                <span className="tone-name" style={{ color: colors[tone] }}>
                  {tone.charAt(0).toUpperCase() + tone.slice(1)}
                </span>
                <span className="tone-count">{count} ({percent.toFixed(0)}%)</span>
              </div>
              <div className="tone-bar-container">
                <div
                  className="tone-bar-fill"
                  style={{
                    width: `${percent}%`,
                    backgroundColor: colors[tone]
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="tone-summary">
        <div className="tone-total">
          <span className="total-number">{total}</span>
          <span className="total-label">Total Analyzed</span>
        </div>
      </div>
    </div>
  );
};

// Daily trend chart
const TrendChart = ({ data }) => {
  if (!data.length) return <div className="no-data">No data available</div>;

  const maxCount = Math.max(...data.map(d => d.count), 1);

  return (
    <div className="trend-chart">
      <div className="trend-bars">
        {data.map((day, i) => (
          <div key={i} className="trend-bar-wrapper">
            <div
              className="trend-bar"
              style={{ height: `${(day.count / maxCount) * 100}%` }}
              title={`${day.date}: ${day.count} feedbacks`}
            >
              <span className="trend-count">{day.count > 0 ? day.count : ''}</span>
            </div>
            <span className="trend-date">{day.date.slice(5)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

function Reports() {
  const [stats, setStats] = useState(null);
  const [stores, setStores] = useState([]);
  const [feedbacks, setFeedbacks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedStore, setSelectedStore] = useState('');
  const [days, setDays] = useState(15);
  const [detailView, setDetailView] = useState(null);

  useEffect(() => {
    fetchData();
  }, [selectedStore, days]);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch dashboard stats
      const statsUrl = new URL(`${API_BASE}/api/v1/dashboard/stats`);
      statsUrl.searchParams.set('days', days);
      if (selectedStore) statsUrl.searchParams.set('store_code', selectedStore);

      const statsRes = await fetch(statsUrl);
      const statsData = await statsRes.json();
      setStats(statsData);

      // Fetch stores list
      const storesRes = await fetch(`${API_BASE}/api/v1/stores`);
      const storesData = await storesRes.json();
      setStores(storesData);

      // Fetch recent feedbacks
      const feedbacksUrl = new URL(`${API_BASE}/api/v1/feedbacks`);
      feedbacksUrl.searchParams.set('limit', 50);
      feedbacksUrl.searchParams.set('status', 'completed');
      if (selectedStore) feedbacksUrl.searchParams.set('store_code', selectedStore);

      const feedbacksRes = await fetch(feedbacksUrl);
      const feedbacksData = await feedbacksRes.json();
      setFeedbacks(feedbacksData);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    // Simple CSV export
    const headers = ['Date', 'Store', 'Tone', 'Summary', 'Products', 'Issues', 'Actions'];
    const rows = feedbacks.map(fb => [
      fb.recorded_date,
      fb.store_code,
      fb.analysis?.tone || '',
      fb.analysis?.summary || '',
      (fb.analysis?.products || []).join('; '),
      (fb.analysis?.issues || []).join('; '),
      (fb.analysis?.actions || []).join('; ')
    ]);

    const csv = [headers, ...rows].map(row =>
      row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
    ).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `feedback-report-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  if (loading && !stats) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading reports...</p>
      </div>
    );
  }

  return (
    <div className="reports-page">
      {/* Header */}
      <header className="reports-header">
        <div className="reports-title">
          <img src="/logo.svg" alt="Logo" className="reports-logo" />
          <h1>Analytics & Reports</h1>
        </div>
        <div className="header-controls">
          <select
            value={selectedStore}
            onChange={e => setSelectedStore(e.target.value)}
            className="control-select"
          >
            <option value="">All Stores</option>
            {stores.map(s => (
              <option key={s.store_code} value={s.store_code}>
                {s.store_code} ({s.feedback_count})
              </option>
            ))}
          </select>
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="control-select"
          >
            <option value={7}>Last 7 days</option>
            <option value={15}>Last 15 days</option>
            <option value={30}>Last 30 days</option>
            <option value={60}>Last 60 days</option>
          </select>
          <button onClick={handleExport} className="export-btn">
            📥 Export CSV
          </button>
        </div>
      </header>

      {/* Stats Overview */}
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-icon">📊</span>
          <span className="stat-value">{stats?.total_feedbacks || 0}</span>
          <span className="stat-label">Total Feedbacks</span>
        </div>
        <div className="stat-card">
          <span className="stat-icon">🏪</span>
          <span className="stat-value">{stores.length}</span>
          <span className="stat-label">Active Stores</span>
        </div>
        <div className="stat-card positive">
          <span className="stat-icon">😊</span>
          <span className="stat-value">{stats?.tone_distribution?.positive || 0}</span>
          <span className="stat-label">Positive</span>
        </div>
        <div className="stat-card negative">
          <span className="stat-icon">😟</span>
          <span className="stat-value">{stats?.tone_distribution?.negative || 0}</span>
          <span className="stat-label">Negative</span>
        </div>
      </div>

      {/* Charts Row */}
      <div className="charts-section">
        {/* Daily Trend */}
        <div className="chart-card wide">
          <h3>📈 Daily Submissions (Last {days} Days)</h3>
          <TrendChart data={stats?.feedbacks_by_day || []} />
        </div>

        {/* Tone Distribution */}
        <div className="chart-card">
          <h3>😊 Sentiment Analysis</h3>
          <ToneChart data={stats?.tone_distribution || {}} />
        </div>
      </div>

      {/* Insights Row */}
      <div className="insights-grid">
        {/* Top Products */}
        <div className="insight-card">
          <h3>🏷️ Top Products Discussed</h3>
          {stats?.top_products?.length ? (
            <BarChart
              data={stats.top_products}
              labelKey="name"
              valueKey="count"
              maxBars={10}
              color="#4285f4"
            />
          ) : (
            <div className="no-data">No product data yet</div>
          )}
        </div>

        {/* Top Issues */}
        <div className="insight-card">
          <h3>⚠️ Top Issues Reported</h3>
          {stats?.top_issues?.length ? (
            <BarChart
              data={stats.top_issues}
              labelKey="name"
              valueKey="count"
              maxBars={10}
              color="#ea4335"
            />
          ) : (
            <div className="no-data">No issues reported</div>
          )}
        </div>

        {/* Top Actions */}
        <div className="insight-card">
          <h3>✅ Top Action Items</h3>
          {stats?.top_actions?.length ? (
            <BarChart
              data={stats.top_actions}
              labelKey="name"
              valueKey="count"
              maxBars={10}
              color="#34a853"
            />
          ) : (
            <div className="no-data">No actions identified</div>
          )}
        </div>
      </div>

      {/* Store-wise Breakdown */}
      <div className="breakdown-section">
        <h3>🏪 Feedbacks by Store</h3>
        <div className="breakdown-card">
          <BarChart
            data={stats?.feedbacks_by_store || []}
            labelKey="store"
            valueKey="count"
            maxBars={20}
            color="#EF4444"
          />
        </div>
      </div>

      {/* Recent Feedbacks Table */}
      <div className="table-section">
        <h3>📝 Recent Analyzed Feedbacks</h3>
        <div className="table-wrapper">
          <table className="feedbacks-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Store</th>
                <th>Sentiment</th>
                <th>Summary</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {feedbacks.map(fb => (
                <tr key={fb.id} onClick={() => setDetailView(fb)}>
                  <td className="date-cell">{fb.recorded_date}</td>
                  <td className="store-cell"><strong>{fb.store_code}</strong></td>
                  <td className="tone-cell">
                    {fb.analysis?.tone && (
                      <span className={`tone-badge ${fb.analysis.tone}`}>
                        {fb.analysis.tone}
                      </span>
                    )}
                  </td>
                  <td className="summary-cell">
                    {fb.analysis?.summary?.slice(0, 150)}
                    {fb.analysis?.summary?.length > 150 && '...'}
                  </td>
                  <td className="action-cell">
                    <button className="view-btn">View</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Modal */}
      {detailView && (
        <div className="modal-overlay" onClick={() => setDetailView(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setDetailView(null)}>×</button>

            <h2>Feedback Details</h2>

            <div className="detail-header">
              <span className="detail-store">{detailView.store_code}</span>
              <span className="detail-date">{detailView.recorded_date}</span>
              {detailView.analysis?.tone && (
                <span className={`tone-badge ${detailView.analysis.tone}`}>
                  {detailView.analysis.tone}
                </span>
              )}
            </div>

            {detailView.media_url && (
              <div className="detail-section">
                <h4>🎵 Audio Recording</h4>
                <audio controls src={detailView.media_url} style={{ width: '100%' }} />
              </div>
            )}

            {detailView.transcription && (
              <div className="detail-section">
                <h4>📄 Transcription</h4>
                <p className="transcription-text">{detailView.transcription}</p>
              </div>
            )}

            {detailView.analysis && (
              <>
                <div className="detail-section">
                  <h4>📊 Analysis Summary</h4>
                  <p className="analysis-summary">{detailView.analysis.summary}</p>
                  <p className="tone-score">
                    <strong>Sentiment Score:</strong> {(detailView.analysis.tone_score * 100).toFixed(0)}%
                  </p>
                </div>

                {detailView.analysis.products?.length > 0 && (
                  <div className="detail-section">
                    <h4>🏷️ Products Mentioned</h4>
                    <div className="tag-list">
                      {detailView.analysis.products.map((p, i) => (
                        <span key={i} className="tag product">{p}</span>
                      ))}
                    </div>
                  </div>
                )}

                {detailView.analysis.issues?.length > 0 && (
                  <div className="detail-section">
                    <h4>⚠️ Issues</h4>
                    <div className="tag-list">
                      {detailView.analysis.issues.map((p, i) => (
                        <span key={i} className="tag issue">{p}</span>
                      ))}
                    </div>
                  </div>
                )}

                {detailView.analysis.actions?.length > 0 && (
                  <div className="detail-section">
                    <h4>✅ Suggested Actions</h4>
                    <div className="tag-list">
                      {detailView.analysis.actions.map((p, i) => (
                        <span key={i} className="tag action">{p}</span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default Reports;
