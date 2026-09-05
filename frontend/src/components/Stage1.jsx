import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import MarkdownView from './MarkdownView';
import './Stage1.css';

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);
  const { t } = useTranslation();

  if (!responses || responses.length === 0) {
    return null;
  }

  return (
    <div className="stage stage1">
      <h3 className="stage-title">{t('stage1.title')}</h3>

      <div className="tabs">
        {responses.map((resp, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {resp.model.split('/')[1] || resp.model}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="model-name">{responses[activeTab].model}</div>
        <MarkdownView className="response-text markdown-content">
          {responses[activeTab].response}
        </MarkdownView>
      </div>
    </div>
  );
}
