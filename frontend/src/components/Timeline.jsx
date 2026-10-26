import { formatClock } from "../lib/format.js";

// Linha do tempo dos cooldowns (RF11): a sua linha em cima, a dos melhores embaixo,
// no mesmo eixo de tempo, com as fases da luta ao fundo.
export default function Timeline({ duration, phases, tracks }) {
  const pct = (seconds) => `${(Math.min(Math.max(seconds, 0), duration) / duration) * 100}%`;
  const ticks = [];
  for (let t = 0; t <= duration; t += 60) ticks.push(t);

  return (
    <div className="timeline">
      <div className="timeline-legend">
        <span>
          <i className="mark mark-player" aria-hidden="true" /> Você
        </span>
        <span>
          <i className="mark mark-top" aria-hidden="true" /> Referência dos melhores
        </span>
        <span>
          <i className="swatch swatch-intermission" aria-hidden="true" /> Intermissão
        </span>
      </div>

      <div className="timeline-grid">
        <div className="timeline-label" />
        <div className="timeline-axis timeline-phases">
          {phases.map((phase) => (
            <span
              key={phase.id}
              className="timeline-phase-name"
              style={{ left: pct(phase.start_s), width: pct(phase.end_s - phase.start_s) }}
            >
              {phase.name}
            </span>
          ))}
        </div>

        {tracks.map((track) => (
          <TimelineRow key={track.ability_id} track={track} phases={phases} pct={pct} />
        ))}

        <div className="timeline-label" />
        <div className="timeline-axis timeline-ticks" aria-hidden="true">
          {ticks.map((t) => (
            <span key={t} style={{ left: pct(t) }}>
              {formatClock(t)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function TimelineRow({ track, phases, pct }) {
  const describe = (times) => times.map(formatClock).join(", ") || "nenhum uso";
  return (
    <>
      <div className="timeline-label">{track.name}</div>
      <div
        className="timeline-track"
        role="img"
        aria-label={`${track.name}. Você: ${describe(track.player_s)}. Melhores: ${describe(track.top_s)}.`}
      >
        {phases
          .filter((phase) => phase.intermission)
          .map((phase) => (
            <span
              key={phase.id}
              className="timeline-band"
              style={{ left: pct(phase.start_s), width: pct(phase.end_s - phase.start_s) }}
            />
          ))}
        {phases.slice(1).map((phase) => (
          <span key={phase.id} className="timeline-divider" style={{ left: pct(phase.start_s) }} />
        ))}
        {track.player_s.map((t, index) => (
          <span
            key={`p${index}`}
            className="mark mark-player"
            style={{ left: pct(t) }}
            title={`Você: ${formatClock(t)}`}
          />
        ))}
        {track.top_s.map((t, index) => (
          <span
            key={`t${index}`}
            className="mark mark-top"
            style={{ left: pct(t) }}
            title={`Melhores: ${formatClock(t)}`}
          />
        ))}
      </div>
    </>
  );
}
