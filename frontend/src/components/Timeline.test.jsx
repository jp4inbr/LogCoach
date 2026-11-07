import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { axeViolations } from "../test/axe.js";
import { phases, result, timeline } from "../test/fixtures/components.js";
import Timeline from "./Timeline.jsx";

const duration = result.fight.duration_s;

function renderTimeline(props = {}) {
  return render(<Timeline duration={duration} phases={phases} tracks={timeline} {...props} />);
}

describe("Timeline", () => {
  it("mostra a legenda com você, os melhores e a intermissão", () => {
    renderTimeline();
    expect(screen.getByText("Você")).toBeInTheDocument();
    expect(screen.getByText("Referência dos melhores")).toBeInTheDocument();
    // "Intermissão" aparece na legenda e no nome da fase.
    expect(screen.getAllByText("Intermissão")).toHaveLength(2);
  });

  it("descreve cada linha para o leitor de tela com os tempos em mm:ss", () => {
    renderTimeline();
    const surge = screen.getByRole("img", { name: /^Surto Arcano\./ });
    expect(surge).toHaveAccessibleName(
      "Surto Arcano. Você: 0:03, 1:39, 3:11, 4:49, 6:24. Melhores: 0:03, 1:35, 3:08, 4:41.",
    );
  });

  it("linha sem usos dos melhores diz ‘nenhum uso’", () => {
    renderTimeline();
    expect(
      screen.getByRole("img", { name: /^Infusão de Poder \(de outro jogador\)\./ }),
    ).toHaveAccessibleName(
      "Infusão de Poder (de outro jogador). Você: 2:12, 6:22. Melhores: nenhum uso.",
    );
  });

  it("uma marca por uso, do jogador e dos melhores, com o tempo no title", () => {
    const { container } = renderTimeline({
      tracks: [{ ability_id: 1, name: "Habilidade", player_s: [30, 90], top_s: [45] }],
    });
    expect(container.querySelectorAll(".mark-player[title]")).toHaveLength(2);
    expect(container.querySelectorAll(".mark-top[title]")).toHaveLength(1);
    expect(screen.getByTitle("Você: 0:30")).toBeInTheDocument();
    expect(screen.getByTitle("Você: 1:30")).toBeInTheDocument();
    expect(screen.getByTitle("Melhores: 0:45")).toBeInTheDocument();
  });

  it("posiciona as marcas em % da duração da luta", () => {
    renderTimeline({
      duration: 400,
      tracks: [{ ability_id: 1, name: "Habilidade", player_s: [100], top_s: [300] }],
    });
    expect(screen.getByTitle("Você: 1:40").style.left).toBe("25%");
    expect(screen.getByTitle("Melhores: 5:00").style.left).toBe("75%");
  });

  it("limita marcas fora da luta às pontas da linha", () => {
    renderTimeline({
      duration: 400,
      tracks: [{ ability_id: 1, name: "Habilidade", player_s: [-5, 500], top_s: [] }],
    });
    expect(screen.getByTitle("Você: 0:00").style.left).toBe("0%");
    expect(screen.getByTitle("Você: 8:20").style.left).toBe("100%");
  });

  it("mostra o nome de cada fase com posição e largura proporcionais", () => {
    renderTimeline({
      duration: 400,
      phases: [
        { id: 1, name: "Fase 1", start_s: 0, end_s: 100, intermission: false },
        { id: 2, name: "Intermissão", start_s: 100, end_s: 200, intermission: true },
      ],
      tracks: [],
    });
    const p1 = screen.getByText("Fase 1");
    expect(p1.style.left).toBe("0%");
    expect(p1.style.width).toBe("25%");
    const p2 = screen
      .getAllByText("Intermissão")
      .find((el) => el.classList.contains("timeline-phase-name"));
    expect(p2.style.left).toBe("25%");
    expect(p2.style.width).toBe("25%");
  });

  it("marca a faixa da intermissão e os divisores entre fases em cada linha", () => {
    const { container } = renderTimeline();
    // 3 fases: 1 faixa de intermissão e 2 divisores por linha; 5 linhas.
    expect(container.querySelectorAll(".timeline-band")).toHaveLength(timeline.length);
    expect(container.querySelectorAll(".timeline-divider")).toHaveLength(2 * timeline.length);
  });

  it("sem fases de intermissão não desenha faixa", () => {
    const { container } = renderTimeline({
      phases: [{ id: 1, name: "Fase 1", start_s: 0, end_s: duration, intermission: false }],
    });
    expect(container.querySelector(".timeline-band")).toBeNull();
    expect(container.querySelector(".timeline-divider")).toBeNull();
  });

  it("o eixo tem uma marca por minuto, de 0:00 até o último minuto completo", () => {
    const { container } = renderTimeline();
    const ticks = [...container.querySelectorAll(".timeline-ticks span")].map((s) => s.textContent);
    expect(ticks).toEqual(["0:00", "1:00", "2:00", "3:00", "4:00", "5:00", "6:00"]);
    expect(container.querySelector(".timeline-ticks")).toHaveAttribute("aria-hidden", "true");
  });

  it("mostra o nome de cada habilidade", () => {
    renderTimeline();
    for (const track of timeline) {
      expect(screen.getByText(track.name)).toBeInTheDocument();
    }
  });

  it("sem linhas ainda desenha o eixo", () => {
    const { container } = renderTimeline({ tracks: [] });
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(container.querySelectorAll(".timeline-ticks span").length).toBeGreaterThan(0);
  });

  it("não tem violações de acessibilidade", async () => {
    const { container } = renderTimeline();
    expect(await axeViolations(container)).toEqual([]);
  });
});
