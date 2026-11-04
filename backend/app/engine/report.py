"""Monta o `AnalysisResult` (item 12.9) a partir da luta do jogador e das lutas dos tops.

Passo 4.3 do motor. Não conhece Warcraft Logs, cache nem rotas: quem chama (o `EngineAnalyzer`
em `services/analyzer.py`) já entrega as lutas no formato de `wcl.fetch.fetch_fight`, os dados
de cabeçalho (`FightInfo`, `PlayerInfo`) e a `Comparison` (tops na ordem do ranking, RF21 já
aplicado, RF25 com os pseudônimos).

Textos ao jogador: nunca o nome de outro jogador (RF25), só "os tops". A sorte do Prismatic
Bolt nunca vira erro: fica só em `gap.luck_pct`.
"""

from collections.abc import Iterable
from statistics import fmean, median
from typing import Any

from app.engine.abilities import ability_table
from app.engine.checks import STATUS_ORDER, Check, gap, pct, run_checks
from app.engine.fight import PhaseSpan, fight_s, phase_spans
from app.engine.measures import FightMeasures, measure
from app.engine.names import spell_name
from app.engine.rules import load_spec_rules
from app.engine.targets import target_table
from app.schemas import (
    AbilityRow,
    AbilityTable,
    AnalysisResult,
    Coach,
    Comparison,
    FightInfo,
    Gap,
    Mistake,
    Number,
    Phase,
    PlayerInfo,
    RuleCheck,
    Summary,
    TargetRow,
    TargetTable,
    TimelineTrack,
)

SURGE, TOUCH, SOUL, POTION, PI, BOLT = 365350, 321507, 451038, 1236616, 10060, 1295924

# Diferença não explicada (RF23) acima disso vira hipótese para a IA investigar.
UNEXPLAINED_MIN_PCT = 1.0

# Regras que ficam só no quadro de regras, nunca como card de erro: o Prismatic Bolt mistura
# decisão e sorte (os números ficam no quadro, com o aviso de RNG; o hábito que tira procs já é
# cobrado em `barrage_low_salvo` e `soul_entry`) e buffs externos são contexto.
RULES_ONLY = frozenset({"prismatic_bolt", "power_infusion"})

# Textos por regra: título, explicação (o porquê, no jogo) e o que fazer. Tom e conteúdo do
# resultado de exemplo que o Arthur escreveu à mão em 28/10 e das decisões do CLAUDE.md. Os
# números do jogador e dos tops entram depois, pelo `_explanation`.
TEXTS: dict[str, tuple[str, str, str]] = {
    "surge_touch_combo": (
        "Surto Arcano fora do Toque dos Magos",
        "O Toque dos Magos guarda parte do dano feito enquanto está no alvo e explode no fim: "
        "ele tem de sair logo depois do Surto Arcano (até 3,5 s) para pegar o burst inteiro. "
        "O Surto que ficou sem Toque logo depois não ganhou esse dano extra.",
        "Use o Surto assim que ele voltar e solte o Toque logo em seguida (dá para soltar antes "
        "uma Salva ou a Seta Prismática). Atrasar o Surto dessincroniza o Toque.",
    ),
    "touch_uses": (
        "Toques dos Magos a menos",
        "Cada Toque dos Magos que deixa de sair é dano que não volta. Possível = usar na recarga "
        "desde o pull até o fim da luta.",
        "Use o Toque na recarga, sempre casado com o Surto quando ele estiver pronto.",
    ),
    "touch_drift": (
        "Toque dos Magos atrasado",
        "Cada segundo de atraso no Toque dos Magos empurra o próximo e pode tirar um uso no fim "
        "da luta; também dessincroniza o Toque do Surto Arcano.",
        "Solte o Toque assim que ele voltar. Se estiver esperando o Surto, não passe de poucos "
        "segundos.",
    ),
    "surge_uses": (
        "Surtos Arcanos a menos",
        "Cada janela de Surto Arcano é o maior pico de dano do Arcano. Possível = usar na "
        "recarga desde o pull até o fim da luta.",
        "Use o Surto na recarga. Segurar só vale para casar com poção, lust ou fase do chefe.",
    ),
    "surge_hold": (
        "Surto Arcano segurado",
        "Segurar o Surto mais de 10 s atrasa todos os seguintes e o Toque junto. Às vezes vale "
        "(poção, lust, Infusão de Poder ou volta do chefe); mais de 15 s sem nada disso é erro.",
        "Use o Surto assim que ele voltar. Só vale segurar até uns 15 s para casar com a poção, "
        "o lust ou uma fase do chefe.",
    ),
    "barrage_low_salvo": (
        "Salva Arcana com poucos acúmulos de Salvo",
        "Todo acerto de magia arcana pode dar Abstração, e a Salva com mais Salvo derruba mais "
        "meteoros (1 a cada 5 acúmulos): mais acertos, mais Abstração, mais Mísseis, mais "
        "Salvo. Soltar a Salva com menos de 12 quebra esse ciclo (efeito bola de neve).",
        "Segure a Salva até ter pelo menos 12 acúmulos. Antes de soltar, gaste 1 Mísseis "
        "Arcanos e a Seta Prismática. Chegar no máximo (25) não é erro.",
    ),
    "soul_entry": (
        "Entrada na Alma Arcana com pouco Salvo",
        "Depois do Surto vem a Alma Arcana: ali a Salva não gasta o Salvo, então cada Salva "
        "rola Seta Prismática e meteoros de graça. Entrar com menos de 12 acúmulos perde esse "
        "ganho; o ideal é 20 ou mais.",
        "Chegue na Alma Arcana com 20 de Salvo ou mais. Nos dois últimos GCDs antes dela (uns "
        "2,5 s), não lance Salva; se vier Mísseis Sobrecarregados, o Salvo sobe para 25 na hora.",
    ),
    "surge_empty_handed": (
        "Surto Arcano começado de mão vazia",
        "Começar o Surto com menos de 12 de Salvo e nenhuma Abstração enche a janela de "
        "Impacto Arcano, a magia mais fraca do burst. O custo já aparece nos Impactos dentro "
        "do Surto.",
        "Entre no Surto com uma Abstração guardada ou com Salvo razoável. Com 1 Abstração e 11 "
        "de Salvo o fluxo já anda: não precisa segurar o Surto à toa.",
    ),
    "surge_blasts": (
        "Impactos Arcanos demais dentro do Surto",
        "Dentro do Surto, cada Impacto Arcano no lugar de Mísseis Arcanos é dano a menos. Sem "
        "Abstração às vezes não tem jeito, por isso a referência são os tops.",
        "Entre no Surto com uma Abstração guardada e Salvo razoável, e dentro dele mantenha o "
        "ciclo de Mísseis e Salvas cheias. O Impacto fica para completar o Salvo fora do burst.",
    ),
    "prismatic_bolt": (
        "Poucos procs esperados de Seta Prismática",
        "A chance de Seta Prismática cresce com o Salvo de cada Salva (2% por acúmulo). Aqui "
        "conta só a decisão (procs esperados pelos acúmulos); o azar não é cobrado.",
        "Solte as Salvas com 12 acúmulos ou mais e entre na Alma Arcana com Salvo alto.",
    ),
    "bolt_munch": (
        "Seta Prismática perdida por Salva com proc ativo",
        "Lançar Salva com a Seta Prismática pronta e ganhar outro proc apaga o anterior: um "
        "proc perdido. Os tops também perdem alguns.",
        "Com a Seta Prismática pronta, lance a Seta antes da próxima Salva.",
    ),
    "potion": (
        "Poção fora do lust ou do Surto",
        "A 1ª poção vai junto do primeiro lust da luta; a 2ª, junto de um Surto Arcano (rende "
        "mais que na recarga). Poção fora disso ou não usada é dano a menos.",
        "Tome a 1ª poção junto do lust e segure a 2ª para um Surto, se a luta durar o bastante.",
    ),
    "active_time": (
        "Tempo ativo abaixo dos tops",
        "Tempo sem lançar nada é dano perdido.",
        "Mantenha algo sendo lançado o tempo todo; ao se mover, use magias instantâneas.",
    ),
    "damage_peaks": (
        "Picos de dano sem defensivo ou com dano evitável",
        "Nos picos de dano (muita vida perdida em poucos segundos), o motor separa o que veio "
        "de mecânica evitável, onde um defensivo cabia e onde faltou cura (aí não é erro do "
        "Mago). É risco, não perda de dano.",
        "Deixe a Barreira Prismática (ou outro defensivo) pronta para os picos e saia das "
        "mecânicas de posicionamento.",
    ),
    "avoidable_damage": (
        "Dano evitável recebido",
        "Dano de mecânica de posicionamento (ex.: poças) gasta cura da raide e põe a vida em "
        "risco.",
        "Saia das mecânicas evitáveis; vale mover antes e lançar instantâneas no caminho.",
    ),
    "power_infusion": (
        "Infusão de Poder recebida",
        "Buff de outro jogador: contexto, não erro.",
        "Combine com o Sacerdote para receber a Infusão junto do Surto.",
    ),
    "deaths": (
        "Morte na luta",
        "Morto não causa dano: o tempo morto sai inteiro do seu dano.",
        "Veja nos picos de dano o que levou à morte e guarde um defensivo para ali.",
    ),
}


def _explanation(check: Check, base: str) -> str:
    # Você × tops já está em `numbers`; a referência só quando diz algo além do valor dos tops.
    parts = [base]
    if check.reference and check.top_value not in check.reference:
        parts.append(f"Referência: {check.reference}.")
    if check.details:
        parts.append("Detalhes: " + "; ".join(check.details) + ".")
    if check.note and check.id != "damage_peaks":  # a nota dos picos repete o texto base
        parts.append(check.note)
    return " ".join(parts)


def _phase_of(spans: list[PhaseSpan], fight_start_ms: float, times_s: list[float]) -> str | None:
    """Nome da fase quando todos os momentos caem na mesma; senão None."""
    names = set()
    for t in times_s:
        ms = fight_start_ms + 1000 * t
        span = next((s for s in spans if s.start_ms <= ms < s.end_ms), spans[-1] if spans else None)
        if span is not None:
            names.add(span.name)
    return names.pop() if len(names) == 1 else None


def _check_times(check: Check, p: FightMeasures) -> list[float]:
    if check.id == "surge_touch_combo":
        return [c.surge_s for c in p.combos if not c.aligned]
    if check.id == "surge_hold":
        return [h.time_s for h in p.surge_holds]
    if check.id == "soul_entry":
        return [e.start_s for e in p.soul if e.mistake]
    if check.id == "deaths":
        return [d.time_s for d in p.deaths]
    return []


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _mistake(check: Check, phase: str | None) -> Mistake:
    title, base, what_to_do = TEXTS.get(check.id, (check.name, "", "Veja os detalhes da regra."))
    return Mistake(
        id=check.id,
        title=title,
        # Impacto que arredonda para zero não vira "custou 0%": fica sem custo calculado.
        impact_pct=_r(check.impact_pct) or None,
        severity=check.status,  # type: ignore[arg-type]  # só atencao/erro chegam aqui
        kind="regra",
        phase=phase,
        explanation=_explanation(check, base),
        what_to_do=what_to_do,
        numbers=[Number(label=check.name, player=check.player_value, top=check.top_value)],
    )


def _sort_key(m: Mistake) -> tuple:
    # Com impacto, do maior para o menor; sem impacto (risco) no fim, erro antes de atenção.
    if m.impact_pct is not None:
        return (0, -m.impact_pct, 0)
    return (1, 0.0, -STATUS_ORDER[m.severity])


def _hypothesis(
    unexplained: float, abilities: list[AbilityTable], targets: list[TargetTable]
) -> Mistake:
    """Diferença que nenhuma regra mede (RF23), com pistas das tabelas para a IA (RF24). A
    Seta Prismática fica fora das pistas: a diferença dela já está na sorte (`gap.luck_pct`)."""
    rows = [
        (t.phase, r)
        for t in abilities
        for r in t.rows
        if r.player_dmg_pct is not None and r.top_dmg_pct is not None and r.name != spell_name(BOLT)
    ]
    rows.sort(key=lambda x: abs(x[1].player_dmg_pct - x[1].top_dmg_pct), reverse=True)
    numbers = [
        Number(
            label=f"{r.name} ({phase}), % do dano",
            player=pct(r.player_dmg_pct),
            top=pct(r.top_dmg_pct),
        )
        for phase, r in rows[:3]
    ]
    clues = [
        f"{r.name} na {phase} ({pct(r.player_dmg_pct)} do seu dano; tops: {pct(r.top_dmg_pct)})"
        for phase, r in rows[:3]
    ]
    padding = [
        (t.phase, r)
        for t in targets
        for r in t.rows
        if r.boss and r.top_pct is not None and r.top_pct - r.player_pct > 5
    ]
    for phase, r in padding:
        numbers.append(
            Number(label=f"Dano no chefe ({phase})", player=pct(r.player_pct), top=pct(r.top_pct))
        )
    text = (
        f"As regras não explicam {pct(unexplained)} da diferença para os tops (já descontados "
        "os erros e a sorte da Seta Prismática). Nenhuma regra mede essa parte; é hipótese, "
        "não fato."
    )
    if clues:
        text += " Maiores diferenças na tabela por habilidade: " + "; ".join(clues) + "."
    if padding:
        text += (
            " Você deu menos dano no chefe que os tops em "
            + ", ".join(phase for phase, _ in padding)
            + ": pode ter largado o chefe por adds."
        )
    return Mistake(
        id="unexplained_gap",
        title="O que as regras não explicam (hipótese)",
        impact_pct=round(unexplained, 1),
        severity="atencao",
        kind="hipotese",
        phase=None,
        explanation=text,
        what_to_do="Compare a sua rotação com a dos tops nas habilidades acima. Na próxima "
        "versão, o coach (IA) vai investigar essas pistas.",
        numbers=numbers,
    )


def _active(p: FightMeasures, tops: list[FightMeasures]) -> tuple[float, float]:
    """A mesma régua do check `active_time` (checks.py): a do WCL se todos a têm."""
    wcl = all(m.active_wcl_pct is not None for m in [p, *tops])
    value = p.active_wcl_pct if wcl else p.active_own_pct
    values = [t.active_wcl_pct if wcl else t.active_own_pct for t in tops]
    return value, (median(values) if values else value)


def _tracks(p: FightMeasures, top: FightMeasures | None) -> list[TimelineTrack]:
    def track(ability_id: int, name: str, get) -> TimelineTrack:
        return TimelineTrack(
            ability_id=ability_id,
            name=name,
            player_s=[round(t, 1) for t in get(p)],
            top_s=[round(t, 1) for t in get(top)] if top else [],
        )

    return [
        track(SURGE, spell_name(SURGE), lambda m: [u.time_s for u in m.surge.uses]),
        track(TOUCH, spell_name(TOUCH), lambda m: [u.time_s for u in m.touch.uses]),
        track(SOUL, spell_name(SOUL), lambda m: [e.start_s for e in m.soul]),
        track(
            POTION, f"{spell_name(POTION)} (poção)", lambda m: [u.time_s for u in m.potions.uses]
        ),
        track(
            PI,
            f"{spell_name(PI)} (de outro jogador)",
            lambda m: [b.time_s for b in m.externals if b.name == "power_infusion"],
        ),
    ]


def _phases(fight: dict[str, Any], encounter: dict[str, Any] | None) -> list[Phase]:
    marked = {p["id"] for p in (encounter or {}).get("phases") or [] if p.get("intermission")}
    return [
        Phase(
            id=s.id,
            name=s.name,
            start_s=round(fight_s(fight, s.start_ms), 1),
            end_s=round(fight_s(fight, s.end_ms), 1),
            intermission=s.intermission or s.id in marked,
        )
        for s in phase_spans(fight)
    ]


def build_analysis(
    *,
    report_code: str,
    fight_info: FightInfo,
    player_info: PlayerInfo,
    comparison: Comparison,
    player_fight: dict[str, Any],
    top_fights: Iterable[tuple[dict[str, Any], float]],
    encounter: dict[str, Any] | None,
    rules: dict[str, Any] | None = None,
) -> AnalysisResult:
    """`top_fights`: (luta do top, DPS do ranking), na ordem de `comparison.players`. Pode ser
    um gerador: cada luta é medida e largada antes da próxima (uma luta tem ~4,5 MB na
    memória). Lista vazia vale (bracket sem tops): as regras usam a reserva do YAML."""
    rules = rules or load_spec_rules()
    p = measure(player_fight, rules, encounter)
    tops = [measure(f, rules, encounter, dps=dps) for f, dps in top_fights]

    checks = run_checks(p, tops, rules, encounter)
    parts = gap(p, tops, checks)

    top_avg_dps = fmean(t.dps for t in tops) if tops else p.dps
    active, top_active = _active(p, tops)
    summary = Summary(
        dps=round(p.dps, 1),
        top_avg_dps=round(top_avg_dps, 1),
        dps_gap_pct=round(100 * (p.dps / top_avg_dps - 1), 1) if top_avg_dps else 0.0,
        active_time_pct=round(active, 1),
        top_active_time_pct=round(top_active, 1),
    )

    abilities = [
        AbilityTable(
            phase=t.phase_name,
            rows=[
                AbilityRow(
                    name=line.name,
                    player_cpm=_r(line.player_cpm),
                    top_cpm=_r(line.top_cpm),
                    player_dmg_pct=_r(line.player_dmg_pct),
                    top_dmg_pct=_r(line.top_dmg_pct),
                )
                for line in t.lines
            ],
        )
        for t in ability_table(p.abilities, [t.abilities for t in tops])
    ]
    boss_ids = frozenset({encounter["boss_npc_id"]}) if encounter else frozenset()
    targets = [
        TargetTable(
            phase=t.phase_name,
            rows=[
                TargetRow(
                    name=line.name,
                    boss=line.boss,
                    player_pct=round(line.player_pct, 1),
                    top_pct=_r(line.top_pct),
                )
                for line in t.lines
            ],
        )
        for t in target_table(p.targets, [t.targets for t in tops], boss_ids=boss_ids)
    ]

    spans = phase_spans(player_fight)
    start = player_fight["meta"]["fight"]["startTime"]
    mistakes = sorted(
        (
            _mistake(c, _phase_of(spans, start, _check_times(c, p)))
            for c in checks
            if c.status != "ok" and c.id not in RULES_ONLY
        ),
        key=_sort_key,
    )
    if parts.unexplained_pct > UNEXPLAINED_MIN_PCT:
        mistakes.append(_hypothesis(parts.unexplained_pct, abilities, targets))

    return AnalysisResult(
        source="motor",
        report_code=report_code,
        fight=fight_info,
        player=player_info,
        comparison=comparison,
        summary=summary,
        coach=Coach(available=False, headline=None),
        mistakes=mistakes,
        rules=[
            RuleCheck(
                id=c.id,
                name=c.name,
                player_value=c.player_value,
                top_value=c.top_value,
                status=c.status,
                note=c.note,
                reference=c.reference,
                impact_pct=_r(c.impact_pct),
                details=list(c.details),
            )
            for c in checks
        ],
        phases=_phases(player_fight, encounter),
        timeline=_tracks(p, tops[0] if tops else None),
        abilities=abilities,
        gap=Gap(
            total_pct=round(parts.total_pct, 1),
            mistakes_pct=round(parts.mistakes_pct, 1),
            luck_pct=round(parts.luck_pct, 1),
            unexplained_pct=round(parts.unexplained_pct, 1),
        ),
        targets=targets,
    )
