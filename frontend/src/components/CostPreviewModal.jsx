import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import './CostPreviewModal.css';

/**
 * Pre-flight cost confirmation modal. Shown before a message is actually sent.
 * Reuses the look & feel of the insufficient-credits modal.
 */
export default function CostPreviewModal({ estimate, onConfirm, onGoToSettings, onCancel }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const {
    cost,
    balance,
    balance_after: balanceAfter,
    can_afford: canAfford,
    council_models: councilModels = [],
    chairman_model: chairmanModel,
    cost_type: costType,
  } = estimate;

  const costTypeLabel = costType === 'vision'
    ? t('costPreview.costTypeVision')
    : t('costPreview.costTypeStandard');

  return (
    <div className="credits-modal-overlay" data-testid="cost-preview-modal">
      <div className="credits-modal cost-preview-modal">
        <h3 data-testid="cost-preview-title">{t('costPreview.title')}</h3>

        <div className="cost-preview-rows">
          <div className="cost-preview-row">
            <span className="cpr-label">{t('costPreview.costLabel')}</span>
            <span className="cpr-value" data-testid="cost-preview-cost">
              <strong>{cost}</strong> {t('costPreview.credits')} <em>({costTypeLabel})</em>
            </span>
          </div>

          <div className="cost-preview-row">
            <span className="cpr-label">{t('costPreview.balanceLabel')}</span>
            <span className="cpr-value" data-testid="cost-preview-balance">
              <strong>{balance}</strong> {t('costPreview.credits')}
            </span>
          </div>

          <div className="cost-preview-row">
            <span className="cpr-label">{t('costPreview.balanceAfterLabel')}</span>
            <span
              className={`cpr-value ${balanceAfter <= 0 ? 'cpr-negative' : ''}`}
              data-testid="cost-preview-balance-after"
            >
              <strong>{balanceAfter}</strong> {t('costPreview.credits')}
            </span>
          </div>

          <div className="cost-preview-divider" />

          <div className="cost-preview-row cost-preview-row--stack">
            <span className="cpr-label">
              {t('costPreview.councilLabel')} · {t('costPreview.modelsCount', { count: councilModels.length })}
            </span>
            <ul className="cost-preview-models" data-testid="cost-preview-models">
              {councilModels.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>

          <div className="cost-preview-row">
            <span className="cpr-label">{t('costPreview.chairmanLabel')}</span>
            <span className="cpr-value" data-testid="cost-preview-chairman">{chairmanModel}</span>
          </div>

          {estimate.pricing && (
            <>
              <div className="cost-preview-divider" />
              <div className="cost-preview-row">
                <span className="cpr-label">{t('costPreview.apiCalls')}</span>
                <span className="cpr-value">{estimate.pricing.total_api_calls}</span>
              </div>
              <div className="cost-preview-row">
                <span className="cpr-label">{t('costPreview.estimatedUsd')}</span>
                <span className="cpr-value">
                  ~${estimate.pricing.estimated_usd.toFixed(4)} USD
                </span>
              </div>

              <div className="cost-preview-row cost-preview-row--stack">
                <span className="cpr-label">{t('costPreview.perModelCost')}</span>
                <div className="cost-preview-model-costs" data-testid="cost-preview-per-model">
                  {estimate.pricing.per_model_credits.map((m) => (
                    <div key={m.model} className="model-cost-row">
                      <span className="model-cost-name">{m.model}</span>
                      <span className="model-cost-credits">
                        {m.credits} {t('costPreview.credits')}
                        <em>(~${m.usd.toFixed(6)})</em>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {!canAfford && (
          <p className="cost-preview-insufficient" data-testid="cost-preview-insufficient">
            {t('costPreview.insufficientBalance')}
          </p>
        )}

        <div className="credits-modal-actions cost-preview-actions">
          <button
            className="cm-link"
            onClick={onCancel}
            data-testid="cost-preview-cancel"
          >
            {t('costPreview.cancel')}
          </button>
          <button
            className="cm-secondary"
            onClick={onGoToSettings}
            data-testid="cost-preview-settings"
          >
            {t('costPreview.modifyConfig')}
          </button>
          {canAfford ? (
            <button
              className="cm-confirm"
              onClick={onConfirm}
              data-testid="cost-preview-confirm"
            >
              {t('costPreview.confirm')}
            </button>
          ) : (
            <button
              className="cm-primary"
              onClick={() => navigate('/credits')}
              data-testid="cost-preview-buy"
            >
              {t('costPreview.buyCredits')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
