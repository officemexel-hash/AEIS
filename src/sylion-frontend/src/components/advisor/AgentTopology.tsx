"use client";

export function AgentTopology() {
  return (
    <div className="topology-wrap">
      <svg
        className="topology-svg"
        viewBox="0 0 600 346"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <marker
            id="cv4-arrow-cyan"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(85,228,255,.55)" />
          </marker>
          <marker
            id="cv4-arrow-violet"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(169,141,255,.55)" />
          </marker>
          <marker
            id="cv4-arrow-green"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(85,243,169,.55)" />
          </marker>
        </defs>

        {/* Planner → Workers */}
        <line
          x1="300" y1="68" x2="155" y2="168"
          stroke="rgba(85,228,255,.32)" strokeWidth="1.5"
          markerEnd="url(#cv4-arrow-cyan)"
        />
        {/* Planner → Critic */}
        <line
          x1="300" y1="68" x2="447" y2="168"
          stroke="rgba(169,141,255,.32)" strokeWidth="1.5"
          markerEnd="url(#cv4-arrow-violet)"
        />
        {/* Workers → Verifier */}
        <line
          x1="155" y1="182" x2="280" y2="200"
          stroke="rgba(85,228,255,.32)" strokeWidth="1.5"
          markerEnd="url(#cv4-arrow-cyan)"
        />
        {/* Critic → Verifier */}
        <line
          x1="447" y1="182" x2="322" y2="200"
          stroke="rgba(169,141,255,.32)" strokeWidth="1.5"
          markerEnd="url(#cv4-arrow-violet)"
        />
        {/* Verifier → Council */}
        <line
          x1="300" y1="214" x2="300" y2="284"
          stroke="rgba(85,243,169,.32)" strokeWidth="1.5"
          markerEnd="url(#cv4-arrow-green)"
        />
      </svg>

      <div className="topology-label t-planner">
        <b>Planner</b>
        <span>planowanie · SoT</span>
      </div>
      <div className="topology-label t-workers">
        <b>Workers</b>
        <span>wykonanie · drafty</span>
      </div>
      <div className="topology-label t-verifier">
        <b>Verifier</b>
        <span>testy · golden set</span>
      </div>
      <div className="topology-label t-critic">
        <b>Critic</b>
        <span>ocena · korekta</span>
      </div>
      <div className="topology-label t-council">
        <b>Council / HG</b>
        <span>decyzję D3+</span>
      </div>
    </div>
  );
}
