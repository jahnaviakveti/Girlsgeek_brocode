import React from 'react';
import { NAV_ITEMS } from '../../types';

export default function Navigation({ activeView, onViewChange }) {
  return (
    <nav className="coach-nav" aria-label="Main Navigation">
      <div className="coach-nav-track">
        {NAV_ITEMS.map((item) => {
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              className={`coach-nav-tab ${isActive ? 'active' : ''} ${item.id === 'recruiter_portal' ? 'tab-recruiter' : ''}`}
              onClick={() => onViewChange(item.id)}
            >
              <span className="tab-icon">{item.icon}</span>
              <span className="tab-label">{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
