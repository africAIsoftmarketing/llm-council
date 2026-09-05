import { useTranslation } from 'react-i18next';
import './CouncilProgress.css';

const STEP_KEYS = ['stage1', 'stage2', 'stage3'];

/**
 * Live per-stage progress for a council debate. Driven entirely by the existing
 * SSE events (stageN_start / stageN_complete / complete / error) via the
 * `progress` prop: { steps: ['pending'|'active'|'done'|'error' x3], done, errorStep }.
 */
export default function CouncilProgress({ progress }) {
  const { t } = useTranslation();
  if (!progress) return null;
  const { steps = ['pending', 'pending', 'pending'], done = false } = progress;

  const completed = steps.filter((s) => s === 'done').length;
  const hasError = steps.includes('error');
  const percent = done ? 100 : Math.round((completed / STEP_KEYS.length) * 100);

  return (
    <div
      className={`council-progress ${hasError ? 'has-error' : ''} ${done ? 'is-done' : ''}`}
      data-testid="council-progress"
    >
      <div className="cp-head">
        <span className="cp-title">
          {hasError ? t('progress.stopped') : done ? t('progress.complete') : t('progress.inSession')}
        </span>
        <span className="cp-percent" data-testid="council-progress-percent">{percent}%</span>
      </div>

      <div className="cp-steps">
        {STEP_KEYS.map((key, i) => {
          const state = steps[i] || 'pending';
          return (
            <div
              key={key}
              className={`cp-step cp-${state}`}
              data-testid={`council-step-${key}`}
              data-state={state}
            >
              <div className="cp-step-bar">
                <div className="cp-step-fill" />
              </div>
              <div className="cp-step-meta">
                <span className="cp-step-icon" aria-hidden="true">
                  {state === 'done' ? '✓' : state === 'error' ? '!' : i + 1}
                </span>
                <span className="cp-step-labels">
                  <span className="cp-step-label">{t(`progress.${key}.label`)}</span>
                  <span className="cp-step-sub">{t(`progress.${key}.sub`)}</span>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
