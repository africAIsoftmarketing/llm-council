import './CouncilProgress.css';

const STEPS = [
  { key: 'stage1', label: 'Stage 1', sub: 'Individual responses' },
  { key: 'stage2', label: 'Stage 2', sub: 'Peer review / ranking' },
  { key: 'stage3', label: 'Stage 3', sub: 'Chairman synthesis' },
];

/**
 * Live per-stage progress for a council debate. Driven entirely by the existing
 * SSE events (stageN_start / stageN_complete / complete / error) via the
 * `progress` prop: { steps: ['pending'|'active'|'done'|'error' x3], done, errorStep }.
 */
export default function CouncilProgress({ progress }) {
  if (!progress) return null;
  const { steps = ['pending', 'pending', 'pending'], done = false } = progress;

  const completed = steps.filter((s) => s === 'done').length;
  const hasError = steps.includes('error');
  const percent = done ? 100 : Math.round((completed / STEPS.length) * 100);

  return (
    <div
      className={`council-progress ${hasError ? 'has-error' : ''} ${done ? 'is-done' : ''}`}
      data-testid="council-progress"
    >
      <div className="cp-head">
        <span className="cp-title">
          {hasError ? 'Council stopped' : done ? 'Council complete' : 'Council in session…'}
        </span>
        <span className="cp-percent" data-testid="council-progress-percent">{percent}%</span>
      </div>

      <div className="cp-steps">
        {STEPS.map((step, i) => {
          const state = steps[i] || 'pending';
          return (
            <div
              key={step.key}
              className={`cp-step cp-${state}`}
              data-testid={`council-step-${step.key}`}
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
                  <span className="cp-step-label">{step.label}</span>
                  <span className="cp-step-sub">{step.sub}</span>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
